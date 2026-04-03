"""SQLite Knowledge Repository 实现"""
import logging
import json
from typing import Optional, List
from datetime import datetime
from domain.novel.value_objects.novel_id import NovelId
from domain.knowledge.story_knowledge import StoryKnowledge
from domain.knowledge.chapter_summary import ChapterSummary
from domain.knowledge.knowledge_triple import KnowledgeTriple
from infrastructure.persistence.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class SqliteKnowledgeRepository:
    """SQLite Knowledge Repository 实现

    管理三元组知识图谱和章节摘要
    """

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def save_knowledge(self, novel_id: str, premise_lock: str = "") -> None:
        """保存或更新知识库基础信息"""
        sql = """
            INSERT INTO knowledge (id, novel_id, version, premise_lock, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(novel_id) DO UPDATE SET
                premise_lock = excluded.premise_lock,
                updated_at = excluded.updated_at
        """
        now = datetime.utcnow().isoformat()
        knowledge_id = f"{novel_id}-knowledge"
        self.db.execute(sql, (knowledge_id, novel_id, 1, premise_lock, now, now))
        self.db.get_connection().commit()

    def get_by_novel_id(self, novel_id: NovelId) -> Optional[StoryKnowledge]:
        """获取小说的完整知识库（包含三元组和章节摘要）"""
        # 处理 novel_id 可能是字符串或 NovelId 对象
        novel_id_str = novel_id.value if hasattr(novel_id, 'value') else novel_id

        # 获取基础信息
        sql = "SELECT * FROM knowledge WHERE novel_id = ?"
        knowledge = self.db.fetch_one(sql, (novel_id_str,))

        if not knowledge:
            return None

        # 获取三元组
        triples_sql = """
            SELECT id, subject, predicate, object, chapter_id, note,
                   entity_type, importance, location_type,
                   description, first_appearance, related_chapters, tags, attributes
            FROM triples
            WHERE novel_id = ?
            ORDER BY created_at ASC
        """
        triples_rows = self.db.fetch_all(triples_sql, (novel_id_str,))

        # 获取章节摘要
        summaries_sql = """
            SELECT chapter_number, summary
            FROM chapter_summaries
            WHERE knowledge_id = ?
            ORDER BY chapter_number ASC
        """
        summaries_rows = self.db.fetch_all(summaries_sql, (knowledge['id'],))

        # 转换为领域对象
        import json
        facts = [
            KnowledgeTriple(
                id=row['id'],
                subject=row['subject'],
                predicate=row['predicate'],
                object=row['object'],
                chapter_id=row['chapter_id'],
                note=row['note'] or "",
                entity_type=row.get('entity_type'),
                importance=row.get('importance'),
                location_type=row.get('location_type'),
                description=row.get('description'),
                first_appearance=row.get('first_appearance'),
                related_chapters=json.loads(row.get('related_chapters') or '[]'),
                tags=json.loads(row.get('tags') or '[]'),
                attributes=json.loads(row.get('attributes') or '{}')
            )
            for row in triples_rows
        ]

        chapters = [
            ChapterSummary(
                chapter_id=row['chapter_number'],
                summary=row['summary'] or "",
                key_events="",
                open_threads="",
                consistency_note="",
                beat_sections=[],
                sync_status="synced"
            )
            for row in summaries_rows
        ]

        return StoryKnowledge(
            novel_id=novel_id_str,
            version=knowledge['version'],
            premise_lock=knowledge['premise_lock'] or "",
            chapters=chapters,
            facts=facts
        )

    def save_triple(self, novel_id: str, triple: dict) -> None:
        """保存单个三元组"""
        import json
        sql = """
            INSERT INTO triples (id, novel_id, subject, predicate, object, chapter_id, note,
                                entity_type, importance, location_type,
                                description, first_appearance, related_chapters, tags, attributes,
                                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                subject = excluded.subject,
                predicate = excluded.predicate,
                object = excluded.object,
                chapter_id = excluded.chapter_id,
                note = excluded.note,
                entity_type = excluded.entity_type,
                importance = excluded.importance,
                location_type = excluded.location_type,
                description = excluded.description,
                first_appearance = excluded.first_appearance,
                related_chapters = excluded.related_chapters,
                tags = excluded.tags,
                attributes = excluded.attributes,
                updated_at = excluded.updated_at
        """
        now = datetime.utcnow().isoformat()
        self.db.execute(sql, (
            triple['id'],
            novel_id,
            triple['subject'],
            triple['predicate'],
            triple['object'],
            triple.get('chapter_id'),
            triple.get('note', ''),
            triple.get('entity_type'),
            triple.get('importance'),
            triple.get('location_type'),
            triple.get('description'),
            triple.get('first_appearance'),
            json.dumps(triple.get('related_chapters', [])),
            json.dumps(triple.get('tags', [])),
            json.dumps(triple.get('attributes', {})),
            now,
            now
        ))
        self.db.get_connection().commit()

    def delete_triple(self, triple_id: str) -> None:
        """删除三元组"""
        sql = "DELETE FROM triples WHERE id = ?"
        self.db.execute(sql, (triple_id,))
        self.db.get_connection().commit()

    def list_triples_by_subject(self, novel_id: str, subject: str) -> List[dict]:
        """查询指定主体的所有三元组"""
        sql = """
            SELECT id, subject, predicate, object, chapter_id, note,
                   entity_type, importance, location_type
            FROM triples
            WHERE novel_id = ? AND subject = ?
            ORDER BY created_at ASC
        """
        return self.db.fetch_all(sql, (novel_id, subject))

    def list_triples_by_predicate(self, novel_id: str, predicate: str) -> List[dict]:
        """查询指定谓词的所有三元组"""
        sql = """
            SELECT id, subject, predicate, object, chapter_id, note,
                   entity_type, importance, location_type
            FROM triples
            WHERE novel_id = ? AND predicate = ?
            ORDER BY created_at ASC
        """
        return self.db.fetch_all(sql, (novel_id, predicate))

    def list_triples_by_entity_type(self, novel_id: str, entity_type: str) -> List[dict]:
        """查询指定实体类型的所有三元组"""
        sql = """
            SELECT id, subject, predicate, object, chapter_id, note,
                   entity_type, importance, location_type
            FROM triples
            WHERE novel_id = ? AND entity_type = ?
            ORDER BY created_at ASC
        """
        return self.db.fetch_all(sql, (novel_id, entity_type))

    def save_chapter_summary(self, knowledge_id: str, chapter_number: int, summary: str) -> None:
        """保存章节摘要"""
        sql = """
            INSERT INTO chapter_summaries (id, knowledge_id, chapter_number, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(knowledge_id, chapter_number) DO UPDATE SET
                summary = excluded.summary,
                updated_at = excluded.updated_at
        """
        now = datetime.utcnow().isoformat()
        summary_id = f"{knowledge_id}-ch{chapter_number}"
        self.db.execute(sql, (summary_id, knowledge_id, chapter_number, summary, now, now))
        self.db.get_connection().commit()

    def save(self, knowledge: 'StoryKnowledge') -> None:
        """保存 StoryKnowledge 对象到数据库"""
        from domain.knowledge.story_knowledge import StoryKnowledge

        novel_id = knowledge.novel_id

        with self.db.transaction() as conn:
            # 1. 保存基础信息
            self.save_knowledge(novel_id, knowledge.premise_lock)

            knowledge_id = f"{novel_id}-knowledge"

            # 2. 删除旧的三元组
            conn.execute("DELETE FROM triples WHERE novel_id = ?", (novel_id,))

            # 3. 保存新的三元组
            for fact in knowledge.facts:
                triple_dict = {
                    'id': fact.id,
                    'subject': fact.subject,
                    'predicate': fact.predicate,
                    'object': fact.object,
                    'chapter_id': fact.chapter_id,
                    'note': fact.note,
                    'entity_type': getattr(fact, 'entity_type', None),
                    'importance': getattr(fact, 'importance', None),
                    'location_type': getattr(fact, 'location_type', None)
                }
                self.save_triple(novel_id, triple_dict)

            # 4. 删除旧的章节摘要
            conn.execute("DELETE FROM chapter_summaries WHERE knowledge_id = ?", (knowledge_id,))

            # 5. 保存新的章节摘要
            for chapter in knowledge.chapters:
                self.save_chapter_summary(
                    knowledge_id,
                    chapter.chapter_number,
                    chapter.summary
                )

        logger.info(f"Saved StoryKnowledge for novel: {novel_id}")

    def save_all(self, novel_id: str, data: dict) -> None:
        """保存完整的知识库数据（用于批量更新）"""
        logger.info(f"save_all called for {novel_id}, facts count: {len(data.get('facts', []))}")
        with self.db.transaction() as conn:
            # 1. 保存基础信息
            knowledge_id = f"{novel_id}-knowledge"
            now = datetime.utcnow().isoformat()
            logger.info(f"Saving knowledge base info, premise_lock: {data.get('premise_lock', '')[:50]}")

            conn.execute("""
                INSERT INTO knowledge (id, novel_id, version, premise_lock, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    premise_lock = excluded.premise_lock,
                    updated_at = excluded.updated_at
            """, (knowledge_id, novel_id, 1, data.get('premise_lock', ''), now, now))

            # 2. 删除旧的三元组
            logger.info(f"Deleting old triples for {novel_id}")
            conn.execute("DELETE FROM triples WHERE novel_id = ?", (novel_id,))

            # 3. 保存新的三元组（直接执行 SQL，不调用 save_triple 避免嵌套提交）
            logger.info(f"Saving {len(data.get('facts', []))} new triples")
            for triple in data.get('facts', []):
                logger.info(f"Inserting triple: {triple['id']} - {triple['subject']}")
                conn.execute("""
                    INSERT INTO triples (id, novel_id, subject, predicate, object, chapter_id, note,
                                        created_at, updated_at, entity_type, importance, location_type,
                                        description, first_appearance, related_chapters, tags, attributes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        subject = excluded.subject,
                        predicate = excluded.predicate,
                        object = excluded.object,
                        chapter_id = excluded.chapter_id,
                        note = excluded.note,
                        entity_type = excluded.entity_type,
                        importance = excluded.importance,
                        location_type = excluded.location_type,
                        description = excluded.description,
                        first_appearance = excluded.first_appearance,
                        related_chapters = excluded.related_chapters,
                        tags = excluded.tags,
                        attributes = excluded.attributes,
                        updated_at = excluded.updated_at
                """, (
                    triple['id'],
                    novel_id,
                    triple['subject'],
                    triple['predicate'],
                    triple['object'],
                    triple.get('chapter_id'),
                    triple.get('note', ''),
                    now,
                    now,
                    triple.get('entity_type'),
                    triple.get('importance'),
                    triple.get('location_type'),
                    triple.get('description'),
                    triple.get('first_appearance'),
                    json.dumps(triple.get('related_chapters', [])),
                    json.dumps(triple.get('tags', [])),
                    json.dumps(triple.get('attributes', {}))
                ))

            # 4. 删除旧的章节摘要
            conn.execute("DELETE FROM chapter_summaries WHERE knowledge_id = ?", (knowledge_id,))

            # 5. 保存新的章节摘要（直接执行 SQL）
            for chapter in data.get('chapters', []):
                chapter_number = chapter.get('number') or chapter.get('chapter_id')
                summary_id = f"{knowledge_id}-ch{chapter_number}"
                conn.execute("""
                    INSERT INTO chapter_summaries (id, knowledge_id, chapter_number, summary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(knowledge_id, chapter_number) DO UPDATE SET
                        summary = excluded.summary,
                        updated_at = excluded.updated_at
                """, (summary_id, knowledge_id, chapter_number, chapter.get('summary', ''), now, now))


        logger.info(f"Saved complete knowledge for novel: {novel_id}")
