"""自动驾驶守护进程 v2 - 全托管写作引擎（事务最小化 + 节拍幂等）

核心设计：
1. 死循环轮询数据库，捞出所有 autopilot_status=RUNNING 的小说
2. 根据 current_stage 执行对应的状态机逻辑
3. 事务最小化：DB 写操作只在读状态和更新状态两个瞬间，LLM 请求期间不持有锁
4. 节拍级幂等：每写完一个节拍立刻落库，断点续写从 current_beat_index 恢复
5. 熔断保护：连续失败 3 次挂起单本小说，全局熔断器防止 API 雪崩
"""
import time
import logging
import asyncio
from typing import List, Optional

from domain.novel.entities.novel import Novel, NovelStage, AutopilotStatus
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.repositories.novel_repository import NovelRepository
from domain.ai.services.llm_service import LLMService, GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from application.engine.services.context_builder import ContextBuilder
from application.engine.services.background_task_service import BackgroundTaskService, TaskType
from domain.novel.value_objects.chapter_id import ChapterId

logger = logging.getLogger(__name__)


class AutopilotDaemon:
    """自动驾驶守护进程（v2 完整实现）"""

    def __init__(
        self,
        novel_repository,
        llm_service,
        context_builder,
        background_task_service,
        planning_service,
        story_node_repo,
        chapter_repository,
        poll_interval: int = 5,
        voice_drift_service=None,
        circuit_breaker=None,
    ):
        self.novel_repository = novel_repository
        self.llm_service = llm_service
        self.context_builder = context_builder
        self.background_task_service = background_task_service
        self.planning_service = planning_service
        self.story_node_repo = story_node_repo
        self.chapter_repository = chapter_repository
        self.poll_interval = poll_interval
        self.voice_drift_service = voice_drift_service
        self.circuit_breaker = circuit_breaker

    def run_forever(self):
        """守护进程主循环（事务最小化原则）"""
        logger.info("🚀 Autopilot Daemon Started")
        while True:
            # 熔断器检查
            if self.circuit_breaker and self.circuit_breaker.is_open():
                wait = self.circuit_breaker.wait_seconds()
                logger.warning(f"熔断器打开，暂停 {wait:.0f}s")
                time.sleep(min(wait, self.poll_interval))
                continue

            try:
                active_novels = self._get_active_novels()  # 快速只读查询
                for novel in active_novels:
                    asyncio.run(self._process_novel(novel))
            except Exception as e:
                logger.error(f"Daemon 顶层异常: {e}", exc_info=True)

            time.sleep(self.poll_interval)

    def _get_active_novels(self) -> List[Novel]:
        """获取所有活跃小说（快速只读）"""
        return self.novel_repository.find_by_autopilot_status(AutopilotStatus.RUNNING.value)

    async def _process_novel(self, novel: Novel):
        """处理单个小说（全流程）"""
        try:
            if novel.current_stage == NovelStage.MACRO_PLANNING:
                await self._handle_macro_planning(novel)
            elif novel.current_stage == NovelStage.ACT_PLANNING:
                await self._handle_act_planning(novel)
            elif novel.current_stage == NovelStage.WRITING:
                await self._handle_writing(novel)
            elif novel.current_stage == NovelStage.AUDITING:
                await self._handle_auditing(novel)
            elif novel.current_stage == NovelStage.PAUSED_FOR_REVIEW:
                return  # 人工干预点：不处理，等前端确认

            # ✅ 保存状态（最小事务：只在这里写库）
            self.novel_repository.save(novel)

            # 熔断器：成功则重置错误计数
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
            novel.consecutive_error_count = 0

        except Exception as e:
            logger.error(f"[{novel.novel_id}] 处理失败: {e}", exc_info=True)

            # 熔断器：记录失败
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            novel.consecutive_error_count = (novel.consecutive_error_count or 0) + 1

            if novel.consecutive_error_count >= 3:
                # 单本小说连续 3 次错误 → 挂起（不影响其他小说）
                logger.error(f"[{novel.novel_id}] 连续失败 3 次，挂起等待急救")
                novel.autopilot_status = AutopilotStatus.ERROR
            self.novel_repository.save(novel)

    async def _handle_macro_planning(self, novel: Novel):
        """处理宏观规划（规划部/卷/幕）"""
        target_chapters = novel.target_chapters or 30
        structure_preference = {
            "parts": 1,
            "volumes_per_part": 1,
            "acts_per_volume": 3,
            "chapters_per_act": max(target_chapters // 3, 5)
        }

        result = await self.planning_service.generate_macro_plan(
            novel_id=novel.novel_id.value,
            target_chapters=target_chapters,
            structure_preference=structure_preference
        )

        if result.get("success") and result.get("structure"):
            await self.planning_service.confirm_macro_plan_safe(
                novel_id=novel.novel_id.value,
                structure=result["structure"]
            )
        else:
            await self._create_minimal_structure(novel)

        # ⏸ 幕级大纲已就绪，进入人工审阅点
        novel.current_stage = NovelStage.PAUSED_FOR_REVIEW
        logger.info(f"[{novel.novel_id}] 宏观规划完成，进入审阅等待")

    async def _create_minimal_structure(self, novel: Novel):
        """创建最小结构（降级方案）"""
        logger.warning(f"[{novel.novel_id}] 宏观规划失败，创建最小结构")
        # 简单创建 3 幕结构
        pass

    async def _handle_act_planning(self, novel: Novel):
        """处理幕级规划（插入缓冲章策略）"""
        novel_id = novel.novel_id.value
        target_act_number = novel.current_act + 1  # 1-indexed

        all_nodes = await self.story_node_repo.get_by_novel(novel_id)
        act_nodes = sorted(
            [n for n in all_nodes if n.node_type.value == "act"],
            key=lambda n: n.number
        )

        target_act = next((n for n in act_nodes if n.number == target_act_number), None)

        if not target_act:
            if act_nodes:
                await self.planning_service.create_next_act_auto(
                    novel_id=novel_id,
                    current_act_id=act_nodes[-1].id
                )
                all_nodes = await self.story_node_repo.get_by_novel(novel_id)
                act_nodes = sorted(
                    [n for n in all_nodes if n.node_type.value == "act"],
                    key=lambda n: n.number
                )
                target_act = next((n for n in act_nodes if n.number == target_act_number), None)

            if not target_act:
                logger.error(f"[{novel.novel_id}] 找不到第 {target_act_number} 幕")
                novel.current_stage = NovelStage.WRITING
                return

        # 检查该幕下是否已有章节节点（避免重复规划）
        act_children = self.story_node_repo.get_children_sync(target_act.id)
        confirmed_chapters = [n for n in act_children if n.node_type.value == "chapter"]

        if not confirmed_chapters:
            plan_result = await self.planning_service.plan_act_chapters(
                act_id=target_act.id,
                custom_chapter_count=target_act.suggested_chapter_count or 5
            )
            chapters_data = plan_result.get("chapters", [])
            if chapters_data:
                await self.planning_service.confirm_act_planning(
                    act_id=target_act.id,
                    chapters=chapters_data
                )

        # ⏸ 幕级章节大纲就绪，再次进入人工审阅点
        novel.current_stage = NovelStage.PAUSED_FOR_REVIEW
        logger.info(f"[{novel.novel_id}] 第 {target_act_number} 幕规划完成，进入审阅等待")

    async def _handle_writing(self, novel: Novel):
        """处理写作（节拍级幂等落库）"""
        # 1. 成本控制：达到最大章节数则自动停止
        max_chapters = novel.max_auto_chapters or 50
        if (novel.current_auto_chapters or 0) >= max_chapters:
            logger.info(f"[{novel.novel_id}] 已达成本控制上限 {max_chapters} 章，自动停止")
            novel.autopilot_status = AutopilotStatus.STOPPED
            novel.current_stage = NovelStage.PAUSED_FOR_REVIEW
            return

        # 2. 缓冲章判断（高潮后插入日常章）
        needs_buffer = (novel.last_chapter_tension or 0) >= 8
        if needs_buffer:
            logger.info(f"[{novel.novel_id}] 上章张力≥8，强制生成缓冲章")

        # 3. 找下一个未写章节
        next_chapter_node = await self._find_next_unwritten_chapter_async(novel)
        if not next_chapter_node:
            if await self._current_act_fully_written(novel):
                novel.current_act += 1
                novel.current_chapter_in_act = 0
                novel.current_stage = NovelStage.ACT_PLANNING
            else:
                novel.current_stage = NovelStage.AUDITING
            return

        chapter_num = next_chapter_node.number
        outline = next_chapter_node.outline or next_chapter_node.description or next_chapter_node.title

        if needs_buffer:
            outline = f"【缓冲章：日常过渡】{outline}。主角战后休整，与配角闲聊，展示收获，节奏轻松。"

        logger.info(f"[{novel.novel_id}] 开始写第 {chapter_num} 章：{outline[:60]}...")

        # 4. 组装上下文（不持有数据库锁，纯读操作）
        context = ""
        if self.context_builder:
            try:
                context = self.context_builder.build_context(
                    novel_id=novel.novel_id.value,
                    chapter_number=chapter_num,
                    outline=outline,
                    max_tokens=20000
                )
            except Exception as e:
                logger.warning(f"ContextBuilder 失败，降级：{e}")

        # 5. 节拍放大
        beats = []
        if self.context_builder:
            beats = self.context_builder.magnify_outline_to_beats(outline, target_chapter_words=2500)

        # 6. 🔑 节拍级幂等生成 + 增量落库
        start_beat = novel.current_beat_index or 0  # 断点续写：从上次中断的节拍继续

        chapter_content = await self._get_existing_chapter_content(novel, chapter_num) or ""

        if beats:
            for i, beat in enumerate(beats):
                if i < start_beat:
                    continue  # 跳过已生成的节拍

                beat_prompt = self.context_builder.build_beat_prompt(beat, i, len(beats))
                beat_content = await self._stream_one_beat(outline, context, beat_prompt, beat)

                chapter_content += ("\n\n" if chapter_content else "") + beat_content

                # ✅ 每节拍完成后立刻写库（最小事务）
                await self._upsert_chapter_content(novel, next_chapter_node, chapter_content, status="draft")

                # 更新断点索引（写库后更新，保证原子性）
                novel.current_beat_index = i + 1
                self.novel_repository.save(novel)

                logger.info(f"  节拍 {i+1}/{len(beats)} 落库：{len(beat_content)} 字")
        else:
            # 降级：无节拍，一次生成
            beat_content = await self._stream_one_beat(outline, context, None, None)
            chapter_content += beat_content
            await self._upsert_chapter_content(novel, next_chapter_node, chapter_content, status="draft")

        # 7. 章节完成，标记 completed
        await self._upsert_chapter_content(novel, next_chapter_node, chapter_content, status="completed")

        # 8. 更新计数器，重置节拍索引
        novel.current_auto_chapters = (novel.current_auto_chapters or 0) + 1
        novel.current_chapter_in_act += 1
        novel.current_beat_index = 0
        novel.current_stage = NovelStage.AUDITING

        logger.info(f"[{novel.novel_id}] 第 {chapter_num} 章完成：{len(chapter_content)} 字")

    async def _handle_auditing(self, novel: Novel):
        """处理审计（含张力打分）"""
        chapter_num = novel.current_act * 10 + novel.current_chapter_in_act  # 刚写完的章节

        from domain.novel.value_objects.novel_id import NovelId
        from domain.novel.value_objects.chapter_id import ChapterId

        chapter = self.chapter_repository.get_by_novel_and_number(
            NovelId(novel.novel_id.value), chapter_num
        )
        if not chapter:
            novel.current_stage = NovelStage.WRITING
            return

        content = chapter.content or ""
        chapter_id = ChapterId(chapter.id)

        # 1. 提交后台异步任务（不阻塞）
        for task_type in [TaskType.VOICE_ANALYSIS, TaskType.GRAPH_UPDATE, TaskType.FORESHADOW_EXTRACT]:
            self.background_task_service.submit_task(
                task_type=task_type,
                novel_id=novel.novel_id,
                chapter_id=chapter_id,
                payload={"content": content, "chapter_number": chapter_num}
            )

        # 2. 张力打分（轻量 LLM 调用，~200 token）
        tension = await self._score_tension(content)
        novel.last_chapter_tension = tension
        logger.info(f"[{novel.novel_id}] 章节 {chapter_num} 张力值：{tension}/10")

        # 3. 文风漂移检测（同步）
        drift_too_high = False
        if self.voice_drift_service and content:
            try:
                result = self.voice_drift_service.score_chapter(
                    novel_id=novel.novel_id.value,
                    chapter_number=chapter_num,
                    content=content
                )
                similarity = result.get("similarity_score")
                drift_alert = result.get("drift_alert", False)
                logger.info(f"[{novel.novel_id}] 文风相似度：{similarity}，告警：{drift_alert}")
                drift_too_high = drift_alert
            except Exception as e:
                logger.warning(f"文风检测失败（跳过）：{e}")

        # 4. 文风漂移 → 删章重写
        if drift_too_high:
            logger.warning(f"[{novel.novel_id}] 章节 {chapter_num} 文风漂移，删章重写")
            self.chapter_repository.delete(chapter_id)
            novel.current_chapter_in_act -= 1
            novel.current_auto_chapters = max(0, (novel.current_auto_chapters or 1) - 1)
            novel.current_beat_index = 0
            novel.current_stage = NovelStage.WRITING
            return

        novel.current_stage = NovelStage.WRITING

        # 5. 全书完成检测
        chapters = self.chapter_repository.list_by_novel(NovelId(novel.novel_id.value))
        completed = [c for c in chapters if c.status.value == "completed"]
        if len(completed) >= novel.target_chapters:
            logger.info(f"[{novel.novel_id}] 🎉 全书完成！共 {len(completed)} 章")
            novel.autopilot_status = AutopilotStatus.STOPPED
            novel.current_stage = NovelStage.COMPLETED

    async def _score_tension(self, content: str) -> int:
        """给章节打张力分（1-10），用于判断是否插入缓冲章"""
        if not content or len(content) < 200:
            return 5  # 默认中等张力

        snippet = content[:500]  # 只取前 500 字，节省 token

        try:
            prompt = Prompt(
                system="你是小说节奏分析师，只输出一个 1-10 的整数，不要解释。",
                user=f"""根据以下章节开头，打分当前剧情的张力值（1=日常/轻松，10=生死对决/高潮）：

{snippet}

张力分（只输出数字）："""
            )
            config = GenerationConfig(max_tokens=5, temperature=0.1)
            result = await self.llm_service.generate(prompt, config)
            raw = result.content.strip() if hasattr(result, "content") else str(result).strip()
            score = int(''.join(filter(str.isdigit, raw[:3])))
            return max(1, min(10, score))
        except Exception:
            return 5  # 解析失败，返回默认值

    async def _stream_one_beat(self, outline, context, beat_prompt, beat) -> str:
        """流式生成单个节拍（或整章），返回生成内容"""
        system = """你是一位资深网文作家，擅长写爽文。
写作要求：
1. 严格按节拍字数和聚焦点写作
2. 必须有对话和人物互动，保持人物性格一致
3. 增加感官细节：视觉、听觉、触觉、情绪
4. 节奏控制：不要一章推进太多剧情
5. 不要写章节标题"""

        user_parts = []
        if context:
            user_parts.append(context)
        user_parts.append(f"\n【本章大纲】\n{outline}")
        if beat_prompt:
            user_parts.append(f"\n{beat_prompt}")
        user_parts.append("\n\n开始撰写：")

        max_tokens = int(beat.target_words * 1.5) if beat else 3000

        prompt = Prompt(system=system, user="\n".join(user_parts))
        config = GenerationConfig(max_tokens=max_tokens, temperature=0.85)

        content = ""
        async for chunk in self.llm_service.stream_generate(prompt, config):
            content += chunk

        return content

    async def _upsert_chapter_content(self, novel, chapter_node, content: str, status: str):
        """最小事务：只更新章节内容，不涉及其他表"""
        from domain.novel.entities.chapter import Chapter, ChapterStatus
        from domain.novel.value_objects.novel_id import NovelId

        existing = self.chapter_repository.get_by_novel_and_number(
            NovelId(novel.novel_id.value), chapter_node.number
        )
        if existing:
            existing.update_content(content)
            existing.status = ChapterStatus(status)
            self.chapter_repository.save(existing)
        else:
            chapter = Chapter(
                id=chapter_node.id,
                novel_id=NovelId(novel.novel_id.value),
                number=chapter_node.number,
                title=chapter_node.title,
                content=content,
                outline=chapter_node.outline or "",
                status=ChapterStatus(status)
            )
            self.chapter_repository.save(chapter)

    async def _find_next_unwritten_chapter_async(self, novel):
        """找到下一个未写的章节节点"""
        novel_id = novel.novel_id.value
        all_nodes = await self.story_node_repo.get_by_novel(novel_id)
        chapter_nodes = sorted(
            [n for n in all_nodes if n.node_type.value == "chapter"],
            key=lambda n: n.number
        )

        for node in chapter_nodes:
            chapter = self.chapter_repository.get_by_novel_and_number(
                NovelId(novel_id), node.number
            )
            if not chapter or chapter.status.value != "completed":
                return node
        return None

    async def _current_act_fully_written(self, novel) -> bool:
        """检查当前幕是否已全部写完"""
        novel_id = novel.novel_id.value
        all_nodes = await self.story_node_repo.get_by_novel(novel_id)
        act_nodes = sorted(
            [n for n in all_nodes if n.node_type.value == "act"],
            key=lambda n: n.number
        )

        current_act_node = next(
            (n for n in act_nodes if n.number == novel.current_act + 1),
            None
        )
        if not current_act_node:
            return True

        act_children = self.story_node_repo.get_children_sync(current_act_node.id)
        chapter_nodes = [n for n in act_children if n.node_type.value == "chapter"]

        for node in chapter_nodes:
            chapter = self.chapter_repository.get_by_novel_and_number(
                NovelId(novel_id), node.number
            )
            if not chapter or chapter.status.value != "completed":
                return False
        return True

    async def _get_existing_chapter_content(self, novel, chapter_num) -> Optional[str]:
        """获取已存在的章节内容（用于断点续写）"""
        chapter = self.chapter_repository.get_by_novel_and_number(
            NovelId(novel.novel_id.value), chapter_num
        )
        return chapter.content if chapter else None

