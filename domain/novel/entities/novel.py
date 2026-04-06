# domain/novel/entities/novel.py
from enum import Enum
from typing import List
from domain.shared.base_entity import BaseEntity
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.entities.chapter import Chapter, ChapterStatus
from domain.shared.exceptions import InvalidOperationError


class NovelStage(str, Enum):
    """小说阶段（细化为自动驾驶状态机）"""
    PLANNING = "planning"  # 旧版兼容
    MACRO_PLANNING = "macro_planning"  # 规划部/卷/幕
    ACT_PLANNING = "act_planning"  # 规划当前幕的章节（插入缓冲章）
    WRITING = "writing"  # 写正文（节拍放大器）
    AUDITING = "auditing"  # 审计：文风、伏笔、图谱
    REVIEWING = "reviewing"  # 旧版兼容
    PAUSED_FOR_REVIEW = "paused_for_review"  # 幕完成，等待人工确认
    COMPLETED = "completed"


class AutopilotStatus(str, Enum):
    """自动驾驶状态"""
    STOPPED = "stopped"  # 人工接管/暂停
    RUNNING = "running"  # 全托管狂奔中
    ERROR = "error"  # 遇到阻断性错误，挂起等待急救


class Novel(BaseEntity):
    """小说聚合根"""

    def __init__(
        self,
        id: NovelId,
        title: str,
        author: str,
        target_chapters: int,
        premise: str = "",
        stage: NovelStage = NovelStage.PLANNING,
        autopilot_status: AutopilotStatus = AutopilotStatus.STOPPED,
        current_stage: NovelStage = NovelStage.PLANNING,
        current_act: int = 0,
        current_chapter_in_act: int = 0,
        max_auto_chapters: int = 50,
        current_auto_chapters: int = 0,
        last_chapter_tension: int = 0,
        consecutive_error_count: int = 0,
        current_beat_index: int = 0,
    ):
        super().__init__(id.value)
        self.novel_id = id  # 存储 NovelId 对象
        self.title = title
        self.author = author
        self.target_chapters = target_chapters
        self.premise = premise  # 故事梗概/创意
        self.stage = stage
        self.chapters: List[Chapter] = []

        # 自动驾驶状态
        self.autopilot_status = autopilot_status
        self.current_stage = current_stage  # 当前阶段（状态机）
        self.current_act = current_act  # 当前幕号（从 0 开始）
        self.current_chapter_in_act = current_chapter_in_act  # 当前幕内章节号（从 0 开始）

        # 护城河字段
        self.max_auto_chapters = max_auto_chapters  # 成本控制上限
        self.current_auto_chapters = current_auto_chapters  # 已生成章节数
        self.last_chapter_tension = last_chapter_tension  # 上章张力值（1-10）
        self.consecutive_error_count = consecutive_error_count  # 连续失败计数
        self.current_beat_index = current_beat_index  # 当前节拍索引（断点续写）

    def add_chapter(self, chapter: Chapter) -> None:
        """添加章节（必须连续）"""
        expected_number = len(self.chapters) + 1
        if chapter.number != expected_number:
            raise InvalidOperationError(
                f"Chapter number must be {expected_number}, got {chapter.number}"
            )
        self.chapters.append(chapter)

    @property
    def completed_chapters(self) -> int:
        """已完成章节数"""
        return len([c for c in self.chapters if c.status == ChapterStatus.COMPLETED])

    def get_total_word_count(self):
        """获取总字数"""
        from domain.novel.value_objects.word_count import WordCount
        total = WordCount(0)
        for chapter in self.chapters:
            total = total + chapter.word_count
        return total
