"""后台任务服务 - 真实执行（战役二 v2）

设计理念：
1. 主线冲锋：写作流程不等待分析完成
2. 副线扇出：分析任务在后台线程异步执行
3. 最终一致性：分析结果最终会更新到数据库
4. 熔断保护：队列满时丢弃任务，避免内存爆炸
"""
import logging
import asyncio
import threading
import queue
import time
import uuid
from typing import Dict, Any, Optional
from enum import Enum

from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.chapter_id import ChapterId

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """后台任务类型"""
    GRAPH_UPDATE = "graph_update"
    VOICE_ANALYSIS = "voice_analysis"
    FORESHADOW_EXTRACT = "foreshadow_extract"


class BackgroundTask:
    """后台任务"""
    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        novel_id: NovelId,
        chapter_id: ChapterId,
        payload: Dict[str, Any]
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.novel_id = novel_id
        self.chapter_id = chapter_id
        self.payload = payload


class BackgroundTaskService:
    """后台任务服务（工作线程模式）"""

    def __init__(
        self,
        voice_drift_service=None,
        llm_service=None,
        foreshadowing_repo=None,
        triple_repository=None,
    ):
        self.voice_drift_service = voice_drift_service
        self.llm_service = llm_service
        self.foreshadowing_repo = foreshadowing_repo
        self.triple_repository = triple_repository

        self._queue = queue.Queue(maxsize=200)  # 防队列无限增长
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="bg-task-worker")
        self._worker.start()
        logger.info("BackgroundTaskService worker thread started")

    def submit_task(self, task_type, novel_id, chapter_id, payload):
        """提交后台任务（非阻塞）"""
        try:
            task = BackgroundTask(
                task_id=str(uuid.uuid4()),
                task_type=task_type,
                novel_id=novel_id,
                chapter_id=chapter_id,
                payload=payload
            )
            self._queue.put_nowait(task)
            logger.debug(f"[BG] 任务已入队：{task_type.value}")
        except queue.Full:
            logger.warning(f"[BG] 后台任务队列已满，丢弃任务：{task_type.value}")

    def _worker_loop(self):
        """工作线程主循环"""
        while True:
            try:
                task = self._queue.get(timeout=2)
                self._execute_with_retry(task)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[BG] Worker loop error: {e}", exc_info=True)

    def _execute_with_retry(self, task, max_retries=2):
        """执行任务（带重试）"""
        for attempt in range(max_retries + 1):
            try:
                self._execute_task(task)
                return
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"[BG] 任务最终失败 {task.task_type.value}：{e}")
                else:
                    wait = 2 ** attempt  # 指数退避：1s, 2s
                    logger.warning(f"[BG] 任务失败，{wait}s 后重试：{e}")
                    time.sleep(wait)

    def _execute_task(self, task):
        """分发任务到具体处理器"""
        if task.task_type == TaskType.VOICE_ANALYSIS:
            self._handle_voice_analysis(task)
        elif task.task_type == TaskType.GRAPH_UPDATE:
            self._handle_graph_update(task)
        elif task.task_type == TaskType.FORESHADOW_EXTRACT:
            self._handle_foreshadow_extract(task)

    def _handle_voice_analysis(self, task):
        """文风分析处理器"""
        if not self.voice_drift_service:
            return
        content = task.payload.get("content", "")
        chapter_number = task.payload.get("chapter_number", 0)
        if not content:
            return

        self.voice_drift_service.score_chapter(
            novel_id=task.novel_id.value,
            chapter_number=chapter_number,
            content=content
        )
        logger.info(f"[BG] 文风分析完成：第 {chapter_number} 章")

    def _handle_graph_update(self, task):
        """图谱更新处理器（LLM 提取三元组）"""
        if not self.llm_service or not self.triple_repository:
            return
        content = task.payload.get("content", "")[:2000]
        chapter_number = task.payload.get("chapter_number", 0)
        if not content:
            return

        from domain.ai.value_objects.prompt import Prompt
        from domain.ai.services.llm_service import GenerationConfig

        prompt = Prompt(
            system="你是信息抽取专家，只输出指定格式内容，不要解释。",
            user=f"""从以下小说章节提取人物关系三元组。
格式：主体|关系|客体（每行一条，最多8条）
只提取文中明确描述的动作或关系。

章节内容：
{content}

三元组："""
        )
        config = GenerationConfig(max_tokens=400, temperature=0.2)
        result = asyncio.run(self.llm_service.generate(prompt, config))
        raw = result.content if hasattr(result, "content") else str(result)

        for line in raw.strip().split("\n"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3 and all(parts):
                subject, predicate, obj = parts
                try:
                    self.triple_repository.save({
                        "id": str(uuid.uuid4()),
                        "novel_id": task.novel_id.value,
                        "subject": subject,
                        "predicate": predicate,
                        "object": obj,
                        "chapter_number": chapter_number,
                        "source_type": "autopilot_extract",
                        "confidence": 0.7,
                    })
                except Exception:
                    pass  # 重复三元组忽略
        logger.info(f"[BG] 图谱更新完成：第 {chapter_number} 章")

    def _handle_foreshadow_extract(self, task):
        """伏笔提取处理器"""
        if not self.llm_service or not self.foreshadowing_repo:
            return
        content = task.payload.get("content", "")[:2000]
        chapter_number = task.payload.get("chapter_number", 0)
        if not content:
            return

        from domain.ai.value_objects.prompt import Prompt
        from domain.ai.services.llm_service import GenerationConfig

        prompt = Prompt(
            system="你是小说分析专家，专门识别叙事伏笔。只输出格式内容，不要解释。",
            user=f"""从以下章节提取潜在伏笔（悬而未决的情节/暗示/物品/对话）。
格式：伏笔内容|触发关键词（每行一条，最多4条）

章节：
{content}

伏笔："""
        )
        config = GenerationConfig(max_tokens=300, temperature=0.3)
        result = asyncio.run(self.llm_service.generate(prompt, config))
        raw = result.content if hasattr(result, "content") else str(result)

        # 使用 ForeshadowingRegistry 的领域 API
        from domain.novel.value_objects.novel_id import NovelId
        from domain.novel.value_objects.foreshadowing import (
            Foreshadowing, ForeshadowingStatus, ImportanceLevel,
        )

        try:
            registry = self.foreshadowing_repo.get_by_novel_id(NovelId(task.novel_id.value))
            if not registry:
                logger.warning(f"[BG] 小说 {task.novel_id.value} 不存在，跳过伏笔提取")
                return

            for line in raw.strip().split("\n"):
                parts = line.strip().split("|")
                if parts and parts[0].strip():
                    foreshadow_desc = parts[0].strip()
                    try:
                        foreshadowing = Foreshadowing(
                            id=str(uuid.uuid4()),
                            description=foreshadow_desc,
                            planted_in_chapter=max(1, chapter_number),
                            importance=ImportanceLevel.MEDIUM,
                            status=ForeshadowingStatus.PLANTED,
                        )
                        registry.register(foreshadowing)
                    except Exception:
                        pass  # 重复或无效伏笔忽略

            self.foreshadowing_repo.save(registry)
        except Exception as e:
            logger.warning(f"[BG] 伏笔提取存储失败：{e}")

        logger.info(f"[BG] 伏笔提取完成：第 {chapter_number} 章")
