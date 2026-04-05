"""
测试章节审稿服务

验证章节审稿功能是否正常工作，包括：
- 人物一致性检查
- 时间线一致性检查
- 故事线连贯性检查
- 伏笔使用检查
- 改进建议生成
"""

import sys
from pathlib import Path
import asyncio

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from load_env import load_env
load_env()

from infrastructure.persistence.database.connection import get_database
from infrastructure.persistence.database.sqlite_chapter_repository import SqliteChapterRepository
from infrastructure.persistence.database.sqlite_cast_repository import SqliteCastRepository
from infrastructure.persistence.database.sqlite_timeline_repository import SqliteTimelineRepository
from infrastructure.persistence.database.sqlite_storyline_repository import SqliteStorylineRepository
from infrastructure.persistence.database.sqlite_foreshadowing_repository import SqliteForeshadowingRepository
from infrastructure.ai.chromadb_vector_store import ChromaDBVectorStore
from infrastructure.ai.local_embedding_service import LocalEmbeddingService
from application.services.chapter_review_service import ChapterReviewService
from infrastructure.ai.providers.anthropic_provider import AnthropicProvider
from infrastructure.ai.config.settings import Settings
import os


async def main():
    print("=" * 80)
    print("测试章节审稿服务")
    print("=" * 80)

    # 初始化数据库连接
    db = get_database()

    # 初始化仓储
    chapter_repo = SqliteChapterRepository(db)
    cast_repo = SqliteCastRepository(db)
    timeline_repo = SqliteTimelineRepository(db)
    storyline_repo = SqliteStorylineRepository(db)
    foreshadowing_repo = SqliteForeshadowingRepository(db)

    # 初始化向量存储
    embedding_service = LocalEmbeddingService()
    vector_store = ChromaDBVectorStore(embedding_service)

    # 初始化 LLM 服务
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ 未找到 ANTHROPIC_API_KEY，使用 MockProvider")
        from infrastructure.ai.providers.mock_provider import MockProvider
        llm_service = MockProvider()
    else:
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        settings = Settings(api_key=api_key, base_url=base_url)
        llm_service = AnthropicProvider(settings)
        print("✅ 使用 AnthropicProvider")

    # 初始化章节审稿服务
    review_service = ChapterReviewService(
        chapter_repo=chapter_repo,
        cast_repo=cast_repo,
        timeline_repo=timeline_repo,
        storyline_repo=storyline_repo,
        foreshadowing_repo=foreshadowing_repo,
        vector_store=vector_store,
        llm_service=llm_service
    )

    # 测试参数
    novel_id = "test-novel-001"
    chapter_number = 1

    print(f"\n📖 审稿章节: {novel_id} - 第 {chapter_number} 章")
    print("-" * 80)

    try:
        # 执行审稿
        result = await review_service.review_chapter(novel_id, chapter_number)

        print(f"\n✅ 审稿完成")
        print(f"   章节号: {result.chapter_number}")
        print(f"   总体评分: {result.overall_score:.1f}/100")
        print(f"   问题数量: {len(result.issues)}")
        print(f"   审稿时间: {result.reviewed_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # 显示问题列表
        if result.issues:
            print(f"\n📋 检测到的问题:")
            for i, issue in enumerate(result.issues, 1):
                severity_icon = {
                    "critical": "🔴",
                    "warning": "🟡",
                    "suggestion": "🟢"
                }.get(issue.severity, "⚪")

                print(f"\n   {i}. {severity_icon} [{issue.severity.upper()}] {issue.issue_type}")
                print(f"      位置: {issue.location}")
                print(f"      描述: {issue.description}")
                if issue.suggestion:
                    print(f"      建议: {issue.suggestion}")
        else:
            print(f"\n✅ 未检测到问题")

        # 显示改进建议
        if result.improvement_suggestions:
            print(f"\n💡 改进建议:")
            for i, suggestion in enumerate(result.improvement_suggestions, 1):
                print(f"   {i}. {suggestion}")

        print("\n" + "=" * 80)
        print("✅ 测试完成")
        print("=" * 80)

    except ValueError as e:
        print(f"\n❌ 错误: {e}")
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
