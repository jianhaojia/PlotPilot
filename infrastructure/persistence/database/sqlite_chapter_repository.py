"""SQLite Chapter Repository 实现"""
import logging
import json
from typing import Optional, List
from datetime import datetime
from domain.novel.entities.chapter import Chapter
from domain.novel.value_objects.chapter_id import ChapterId
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.repositories.chapter_repository import ChapterRepository
from infrastructure.persistence.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class SqliteChapterRepository(ChapterRepository):
    """SQLite Chapter Repository 实现"""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def save(self, chapter: Chapter) -> None:
        """保存章节"""
        sql = """
            INSERT INTO chapters (id, novel_id, number, title, content, outline, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                outline = excluded.outline,
                status = excluded.status,
                updated_at = excluded.updated_at
        """
        now = datetime.utcnow().isoformat()
        chapter_id = chapter.id.value if hasattr(chapter.id, 'value') else chapter.id
        novel_id = chapter.novel_id.value if hasattr(chapter.novel_id, 'value') else chapter.novel_id
        status = chapter.status.value if hasattr(chapter.status, 'value') else chapter.status
        self.db.execute(sql, (
            chapter_id,
            novel_id,
            chapter.number,
            chapter.title,
            chapter.content,
            chapter.outline,  # 使用实体的 outline 字段
            status,
            now,
            now
        ))
        self.db.get_connection().commit()
        logger.info(f"Saved chapter: {chapter_id}")

    def get_by_id(self, chapter_id: ChapterId) -> Optional[Chapter]:
        """根据 ID 获取章节"""
        sql = "SELECT * FROM chapters WHERE id = ?"
        row = self.db.fetch_one(sql, (chapter_id.value,))

        if not row:
            return None

        return self._row_to_chapter(row)

    def get_by_novel_and_number(self, novel_id: NovelId, number: int) -> Optional[Chapter]:
        """根据小说 ID 和章节号获取章节"""
        sql = "SELECT * FROM chapters WHERE novel_id = ? AND number = ?"
        row = self.db.fetch_one(sql, (novel_id.value, number))

        if not row:
            return None

        return self._row_to_chapter(row)

    def list_by_novel(self, novel_id: NovelId) -> List[Chapter]:
        """列出小说的所有章节"""
        sql = "SELECT * FROM chapters WHERE novel_id = ? ORDER BY number ASC"
        rows = self.db.fetch_all(sql, (novel_id.value,))

        return [self._row_to_chapter(row) for row in rows]

    def delete(self, chapter_id: ChapterId) -> None:
        """删除章节"""
        sql = "DELETE FROM chapters WHERE id = ?"
        self.db.execute(sql, (chapter_id.value,))
        self.db.get_connection().commit()
        logger.info(f"Deleted chapter: {chapter_id.value}")

    def exists(self, chapter_id: ChapterId) -> bool:
        """检查章节是否存在"""
        sql = "SELECT 1 FROM chapters WHERE id = ? LIMIT 1"
        row = self.db.fetch_one(sql, (chapter_id.value,))
        return row is not None

    def _row_to_chapter(self, row: dict) -> Chapter:
        """将数据库行转换为 Chapter 实体"""
        from domain.novel.value_objects.novel_id import NovelId
        from domain.novel.entities.chapter import ChapterStatus
        raw_status = row.get('status', 'draft')
        try:
            status = ChapterStatus(raw_status)
        except ValueError:
            status = ChapterStatus.DRAFT
        return Chapter(
            id=row['id'],
            novel_id=NovelId(row['novel_id']),
            number=row['number'],
            title=row['title'],
            content=row['content'],
            outline=row.get('outline', ''),
            status=status
        )
