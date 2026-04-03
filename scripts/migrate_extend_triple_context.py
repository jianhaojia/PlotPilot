"""扩展三元组表，添加上下文字段以减少 AI 幻觉"""
import sqlite3
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.persistence.database.connection import DatabaseConnection


def migrate():
    """执行迁移"""
    db = DatabaseConnection("data/aitext.db")
    conn = db.get_connection()
    cursor = conn.cursor()

    print("开始扩展三元组表结构...")

    # 添加新字段
    new_columns = [
        ("description", "TEXT", "实体描述，用于 AI 理解上下文"),
        ("first_appearance", "INTEGER", "首次出现的章节号"),
        ("related_chapters", "TEXT", "相关章节列表（JSON 数组）"),
        ("tags", "TEXT", "标签列表（JSON 数组），如 ['主线', '重要']"),
        ("attributes", "TEXT", "额外属性（JSON 对象），灵活扩展"),
    ]

    for col_name, col_type, description in new_columns:
        try:
            cursor.execute(f"ALTER TABLE triples ADD COLUMN {col_name} {col_type}")
            print(f"✓ 添加字段: {col_name} ({description})")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"- 字段已存在: {col_name}")
            else:
                raise

    # 创建索引以优化查询
    indexes = [
        ("idx_triples_first_appearance", "first_appearance"),
        ("idx_triples_tags", "tags"),
    ]

    for idx_name, col_name in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON triples({col_name})")
            print(f"✓ 创建索引: {idx_name}")
        except Exception as e:
            print(f"! 索引创建失败 {idx_name}: {e}")

    conn.commit()
    print("\n迁移完成！")
    print("\n新增字段说明：")
    print("- description: 实体的详细描述，帮助 AI 理解上下文")
    print("- first_appearance: 首次出现的章节号，用于时间线追踪")
    print("- related_chapters: 相关章节列表（JSON），如 [1, 3, 5]")
    print("- tags: 标签列表（JSON），如 ['主线', '重要', '伏笔']")
    print("- attributes: 灵活的 JSON 对象，存储任意额外属性")


if __name__ == "__main__":
    migrate()
