# 三元组扩展设计：减少 AI 幻觉的上下文管理

## 设计目标
1. 为 AI 提供足够的上下文信息，减少幻觉
2. 支持时间线追踪（首次出现、相关章节）
3. 支持语义检索（描述、标签、属性）
4. 保持数据结构灵活可扩展

## 扩展字段设计

### 1. 核心上下文字段

| 字段 | 类型 | 说明 | 用途 |
|------|------|------|------|
| `description` | TEXT | 实体详细描述 | 为 AI 提供完整上下文，避免误解 |
| `first_appearance` | INTEGER | 首次出现章节号 | 时间线追踪，判断信息新旧 |
| `related_chapters` | TEXT (JSON) | 相关章节列表 `[1,3,5]` | 追踪实体活跃范围 |
| `tags` | TEXT (JSON) | 标签列表 `["主线","伏笔"]` | 语义分类，快速过滤 |
| `attributes` | TEXT (JSON) | 灵活属性对象 | 存储特定领域的额外信息 |

### 2. 人物实体扩展属性 (attributes)

```json
{
  "age": "25岁",
  "gender": "男",
  "cultivation_level": "筑基期",
  "personality": ["冷静", "果断", "重情义"],
  "abilities": ["剑术", "阵法"],
  "relationships": {
    "柳月": "师姐",
    "张三": "好友"
  },
  "goals": ["突破金丹", "复仇"],
  "secrets": ["身怀异宝"],
  "status": "active"  // active/injured/missing/dead
}
```

### 3. 地点实体扩展属性 (attributes)

```json
{
  "size": "大型城市",
  "population": "百万修炼者",
  "climate": "四季分明",
  "resources": ["灵石矿", "灵药"],
  "dangers": ["妖兽出没"],
  "ruler": "城主府",
  "special_features": ["传送阵", "拍卖行"],
  "access": "公开"  // public/restricted/secret
}
```

### 4. 标签体系设计

#### 人物标签
- **角色定位**: `主线`, `支线`, `过场`
- **阵营**: `正派`, `反派`, `中立`
- **状态**: `活跃`, `隐退`, `失踪`, `已故`
- **重要性**: `核心`, `重要`, `次要`
- **情节**: `伏笔`, `转折点`, `冲突源`

#### 地点标签
- **功能**: `战斗`, `修炼`, `交易`, `剧情`
- **安全**: `安全`, `危险`, `禁地`
- **频率**: `常驻`, `偶尔`, `一次性`
- **重要性**: `核心`, `重要`, `背景`

### 5. 关系三元组扩展

关系三元组也需要上下文：

```json
{
  "id": "rel-001",
  "subject": "林晨",
  "predicate": "师徒",
  "object": "柳月",
  "entity_type": "character",
  "description": "柳月是林晨的师姐，在第1章相识，第5章传授冰系功法",
  "first_appearance": 1,
  "related_chapters": [1, 5, 12],
  "tags": ["主线关系", "重要"],
  "attributes": {
    "relationship_type": "师徒",
    "strength": "strong",  // strong/normal/weak
    "status": "active",  // active/broken/complicated
    "key_events": [
      {"chapter": 1, "event": "初次见面"},
      {"chapter": 5, "event": "传授功法"}
    ]
  }
}
```

## AI 使用场景

### 场景 1: 生成新章节
AI 需要知道：
- 哪些人物在这个章节活跃？(`related_chapters` 包含当前章节)
- 人物当前状态？(`attributes.status`)
- 人物关系如何？(关系三元组的 `attributes.strength`)

### 场景 2: 一致性检查
AI 需要验证：
- 人物首次出现是否正确？(`first_appearance`)
- 人物能力是否前后一致？(`attributes.abilities`)
- 地点描述是否矛盾？(`description` + `attributes`)

### 场景 3: 向量检索
检索时需要：
- 完整的 `description` 用于语义匹配
- `tags` 用于快速过滤
- `related_chapters` 用于时间线过滤

## 数据维护策略

### 1. 自动更新
- 每次生成新章节后，自动更新 `related_chapters`
- 人物状态变化时，更新 `attributes.status`

### 2. 一致性保证
- 关系三元组的 subject/object 必须在人物节点中存在
- `first_appearance` 不能大于 `related_chapters` 中的最小值

### 3. 检索优化
- 为 `description` 创建全文索引
- 为 `tags` 创建 JSON 索引
- 为 `first_appearance` 和 `related_chapters` 创建范围索引

## 实现优先级

1. **Phase 1**: 添加基础字段 (description, first_appearance, related_chapters, tags, attributes)
2. **Phase 2**: 实现人物和地点的标准 attributes 模板
3. **Phase 3**: 实现自动更新机制
4. **Phase 4**: 集成向量检索和一致性检查
