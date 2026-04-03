"""创建增强的测试数据：包含完整上下文信息"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.persistence.database.connection import DatabaseConnection
from infrastructure.persistence.database.sqlite_knowledge_repository import SqliteKnowledgeRepository


def create_enhanced_test_data():
    """创建包含完整上下文的测试数据"""
    db = DatabaseConnection("data/aitext.db")
    repo = SqliteKnowledgeRepository(db)

    novel_id = "novel-1775150981848"

    print(f"为小说 {novel_id} 创建增强测试数据...")

    # 增强的测试数据：包含完整上下文
    test_data = {
        "version": 1,
        "premise_lock": "修仙世界，主角林晨从江城起步，逐步成长为强者",
        "chapters": [
            {
                "number": 1,
                "chapter_id": 1,
                "summary": "主角林晨在江城觉醒修炼天赋，遇到师姐柳月"
            }
        ],
        "facts": [
            # 人物节点 - 林晨（主角）
            {
                "id": "char-linchen",
                "subject": "林晨",
                "predicate": "是",
                "object": "主角",
                "chapter_id": None,
                "note": "天赋异禀的修炼者，故事主角",
                "entity_type": "character",
                "importance": "primary",
                "description": "25岁男性修炼者，出生于江城普通家庭。性格冷静果断，重情义。在第1章觉醒修炼天赋后开始修炼之路。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["主线", "主角", "活跃"],
                "attributes": {
                    "age": "25岁",
                    "gender": "男",
                    "cultivation_level": "筑基初期",
                    "personality": ["冷静", "果断", "重情义"],
                    "abilities": ["剑术", "基础阵法"],
                    "goals": ["突破金丹", "保护江城"],
                    "status": "active"
                }
            },

            # 人物节点 - 柳月（重要配角）
            {
                "id": "char-liuyue",
                "subject": "柳月",
                "predicate": "是",
                "object": "重要配角",
                "chapter_id": None,
                "note": "林晨的师姐，冰系修炼者",
                "entity_type": "character",
                "importance": "secondary",
                "description": "28岁女性修炼者，天玄宗核心弟子。擅长冰系功法，性格温柔但战斗时果决。在第1章与林晨相识，成为其引路人。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["主线", "导师", "活跃"],
                "attributes": {
                    "age": "28岁",
                    "gender": "女",
                    "cultivation_level": "金丹中期",
                    "personality": ["温柔", "果决", "负责"],
                    "abilities": ["冰系功法", "剑术", "高级阵法"],
                    "affiliation": "天玄宗",
                    "status": "active"
                }
            },

            # 人物节点 - 张三（次要人物）
            {
                "id": "char-zhangsan",
                "subject": "张三",
                "predicate": "是",
                "object": "次要人物",
                "chapter_id": None,
                "note": "江城守卫，林晨的青梅竹马",
                "entity_type": "character",
                "importance": "minor",
                "description": "26岁男性，江城城卫军成员。与林晨从小一起长大，虽然修炼天赋一般但忠诚可靠。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["支线", "朋友", "活跃"],
                "attributes": {
                    "age": "26岁",
                    "gender": "男",
                    "cultivation_level": "练气后期",
                    "personality": ["忠诚", "热情", "直率"],
                    "occupation": "城卫军",
                    "status": "active"
                }
            },

            # 人物关系 - 林晨与柳月
            {
                "id": "rel-linchen-liuyue",
                "subject": "林晨",
                "predicate": "师徒",
                "object": "柳月",
                "chapter_id": None,
                "note": "柳月是林晨的师姐和引路人",
                "entity_type": "character",
                "description": "柳月在第1章发现林晨的修炼天赋，主动收其为师弟，传授基础功法。两人关系亦师亦友。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["主线关系", "重要"],
                "attributes": {
                    "relationship_type": "师徒",
                    "strength": "strong",
                    "status": "active",
                    "key_events": [
                        {"chapter": 1, "event": "初次见面，柳月发现林晨天赋"}
                    ]
                }
            },

            # 人物关系 - 林晨与张三
            {
                "id": "rel-linchen-zhangsan",
                "subject": "林晨",
                "predicate": "朋友",
                "object": "张三",
                "chapter_id": None,
                "note": "青梅竹马，从小一起长大",
                "entity_type": "character",
                "description": "林晨和张三从小在江城一起长大，是最好的朋友。张三一直支持林晨的修炼之路。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["支线关系", "友情"],
                "attributes": {
                    "relationship_type": "好友",
                    "strength": "strong",
                    "status": "active",
                    "duration": "20年"
                }
            },

            # 地点节点 - 江城
            {
                "id": "loc-jiangcheng",
                "subject": "江城",
                "predicate": "是",
                "object": "核心地点",
                "chapter_id": None,
                "note": "故事主要发生地，修炼者聚集的城市",
                "entity_type": "location",
                "importance": "core",
                "location_type": "city",
                "description": "北渊域最大的修炼城市，人口百万。城内有多个修炼宗门，灵气充沛，是修炼者的聚集地。城主府统治，治安良好。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["核心场景", "常驻", "安全"],
                "attributes": {
                    "size": "大型城市",
                    "population": "百万修炼者",
                    "climate": "四季分明",
                    "resources": ["灵石矿", "灵药市场", "炼器坊"],
                    "ruler": "城主府",
                    "special_features": ["传送阵", "拍卖行", "任务大厅"],
                    "access": "public",
                    "safety_level": "safe"
                }
            },

            # 地点节点 - 天玄宗
            {
                "id": "loc-tianxuanzong",
                "subject": "天玄宗",
                "predicate": "是",
                "object": "重要地点",
                "chapter_id": None,
                "note": "江城最大的修炼宗门",
                "entity_type": "location",
                "importance": "important",
                "location_type": "faction",
                "description": "江城最强大的修炼宗门，拥有数千弟子。宗门位于江城北部山脉，灵气浓郁。柳月是其核心弟子。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["重要场景", "宗门", "偶尔"],
                "attributes": {
                    "type": "修炼宗门",
                    "strength": "金丹期长老数十位",
                    "disciples": "数千人",
                    "specialization": "剑道、阵法",
                    "access": "restricted",
                    "reputation": "正派"
                }
            },

            # 地点节点 - 玄武阁
            {
                "id": "loc-xuanwuge",
                "subject": "玄武阁",
                "predicate": "是",
                "object": "一般地点",
                "chapter_id": None,
                "note": "天玄宗的藏书楼",
                "entity_type": "location",
                "importance": "normal",
                "location_type": "building",
                "description": "天玄宗的藏书楼，收藏各类功法、秘籍和典籍。分为三层，越高层级越高的功法。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["功能场景", "修炼", "限制"],
                "attributes": {
                    "type": "藏书楼",
                    "floors": 3,
                    "contents": ["功法", "秘籍", "典籍"],
                    "access": "宗门弟子",
                    "guardian": "元婴期长老"
                }
            },

            # 地点节点 - 北渊域
            {
                "id": "loc-beiyuanyu",
                "subject": "北渊域",
                "predicate": "是",
                "object": "重要地点",
                "chapter_id": None,
                "note": "江城所在的修炼区域",
                "entity_type": "location",
                "importance": "important",
                "location_type": "region",
                "description": "修炼世界的一个大域，包含数十座城市。江城是其中心城市。域内灵气充沛，适合修炼。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["背景", "区域"],
                "attributes": {
                    "size": "数万里",
                    "cities": ["江城", "云城", "雷城"],
                    "dangers": ["妖兽森林", "魔修据点"],
                    "resources": ["灵石矿脉", "灵药山"],
                    "ruler": "域主联盟"
                }
            },

            # 地点关系 - 江城位于北渊域
            {
                "id": "rel-jiangcheng-beiyuanyu",
                "subject": "江城",
                "predicate": "位于",
                "object": "北渊域",
                "chapter_id": None,
                "note": "江城是北渊域的中心城市",
                "entity_type": "location",
                "description": "江城位于北渊域中心位置，是该域最繁华的城市，也是域主联盟的议事地点。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["地理关系"],
                "attributes": {
                    "relationship_type": "地理包含",
                    "position": "中心"
                }
            },

            # 地点关系 - 天玄宗坐落于江城
            {
                "id": "rel-tianxuanzong-jiangcheng",
                "subject": "天玄宗",
                "predicate": "坐落于",
                "object": "江城",
                "chapter_id": None,
                "note": "天玄宗位于江城北部山脉",
                "entity_type": "location",
                "description": "天玄宗山门位于江城北部的青云山脉，距离城区约50里。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["地理关系"],
                "attributes": {
                    "relationship_type": "地理位置",
                    "direction": "北部",
                    "distance": "50里"
                }
            },

            # 地点关系 - 玄武阁属于天玄宗
            {
                "id": "rel-xuanwuge-tianxuanzong",
                "subject": "玄武阁",
                "predicate": "属于",
                "object": "天玄宗",
                "chapter_id": None,
                "note": "玄武阁是天玄宗的核心建筑",
                "entity_type": "location",
                "description": "玄武阁是天玄宗的藏书楼，位于宗门核心区域，由元婴期长老镇守。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["从属关系"],
                "attributes": {
                    "relationship_type": "从属",
                    "importance": "核心建筑"
                }
            },

            # 人物与地点关系 - 林晨出生于江城
            {
                "id": "rel-linchen-jiangcheng",
                "subject": "林晨",
                "predicate": "出生于",
                "object": "江城",
                "chapter_id": None,
                "note": "林晨是江城本地人，在此长大",
                "description": "林晨出生并成长于江城，对这座城市有深厚感情。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["人物-地点关系"],
                "attributes": {
                    "relationship_type": "出生地",
                    "duration": "25年"
                }
            },

            # 人物与地点关系 - 柳月修炼于天玄宗
            {
                "id": "rel-liuyue-tianxuanzong",
                "subject": "柳月",
                "predicate": "修炼于",
                "object": "天玄宗",
                "chapter_id": None,
                "note": "柳月是天玄宗核心弟子",
                "description": "柳月15岁加入天玄宗，现已是金丹期核心弟子，深受宗门器重。",
                "first_appearance": 1,
                "related_chapters": [1],
                "tags": ["人物-地点关系"],
                "attributes": {
                    "relationship_type": "所属宗门",
                    "position": "核心弟子",
                    "duration": "13年"
                }
            }
        ]
    }

    print(f"\n准备保存 {len(test_data['facts'])} 条增强三元组...")
    print(f"- 人物节点: 3 个（含完整属性）")
    print(f"- 人物关系: 2 条（含关系历史）")
    print(f"- 地点节点: 4 个（含详细信息）")
    print(f"- 地点关系: 3 条（含地理信息）")
    print(f"- 人物-地点关系: 2 条")

    # 保存数据
    repo.save_all(novel_id, test_data)

    print("\n✓ 增强测试数据创建成功！")
    print("\n新增字段验证：")
    print("- description: 每个实体都有详细描述")
    print("- first_appearance: 所有实体首次出现在第1章")
    print("- related_chapters: 追踪实体活跃章节")
    print("- tags: 语义标签便于分类和检索")
    print("- attributes: 丰富的领域特定属性")
    print("\n这些信息将帮助 AI：")
    print("1. 理解人物性格、能力、目标")
    print("2. 了解地点规模、功能、安全等级")
    print("3. 追踪关系强度和发展历史")
    print("4. 保持时间线一致性")
    print("5. 减少生成内容的幻觉")


if __name__ == "__main__":
    create_enhanced_test_data()
