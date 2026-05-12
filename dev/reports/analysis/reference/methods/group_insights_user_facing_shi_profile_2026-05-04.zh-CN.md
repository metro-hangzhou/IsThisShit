# ORCH group_insights 用户向 shi 画像契约

日期：2026-05-04

## 目标

`group_insights` 是 ORCH 在主审结果之外生成的用户向群聊概览层。它面向普通用户回答三类问题：

- 这个窗口里的群聊整体给人什么感觉。
- 哪些群友在这个窗口里呈现出什么发言风格。
- 这段内容的 `shi` 类型构成大致是什么。

它不是 evidence package、不是来源分析、不是模型置信度报告，也不是传播路径图。主线展示必须先服务“普通用户能快速看懂这段群聊的 shi 味构成”，内部证据、工具、来源、候选窗口和不确定性细节只能进入 `Inspect` / `Raw`。

## 核心原则

1. 雷达图只表示用户向 `shi` 类型构成，轴名由模型按当前窗口动态生成。
2. 雷达图不表示来源、证据强度、不确定性、传播性质、载体类型或工具路径。
3. `score` 是类型显著度 / 构成强度，不是 confidence，也不是证据数量。
4. `dominant_axes` 只能从同一组动态轴里派生，不能额外引入“证据多”“来源外部”“forward 多”等伪轴。
5. 群画像和群友画像都必须声明窗口边界，不得暗示长期人格、真实身份或全群永久画像。
6. `Inspect` / `Raw` 可以保留诊断材料，但这些材料不得反向污染主线视觉和文案。

## 动态雷达定义

当前公共雷达不是固定六轴。模型必须按当前窗口自行生成用户向 `shi` 类型轴，并把每个轴绑定到可追溯的 QQ 原文证据。

数量规则：

- 通常建议 `3..8` 个有效轴。
- 如果当前窗口只支持 `1..2` 个有效轴，就只输出 `1..2` 个。
- 如果没有足够证据形成用户向 `shi` 类型轴，就输出空轴列表。
- 不允许为了凑数生成通用分类、行业分类、行为标签或来源维度。

允许的轴名示例：

- `立场消费反差 shi`
- `图片配文错位 shi`
- `提示词注入梗 shi`
- `参数嘴硬燃料 shi`

这些示例只说明“普通用户能看懂的类型名”长什么样，不是固定词表。后端不得保留 deterministic `shi` 类型兜底轴；模型缺失或无效时，用户向雷达应少显示或不显示。

禁止作为 `shi` 类型轴的例子：

- `群友接球 shi`
- `抽象复读 shi`
- `转人工 shi`
- `硬件/技术 shi`
- `管人/八卦 shi`

这些要么只是行为特征，要么是粗粒度话题分类。它们可以进入群友行为画像、窗口背景或 Inspect，但不能直接当作用户向 `shi` 成分轴。

## 禁止进入雷达的维度

以下维度可以出现在 `Inspect` / `Raw`，但不得作为雷达轴、公共 badge、公共排序理由或主线图例：

- 来源 / provenance：外部来源、群内原创、forward、nested forward、截图、工具补证来源。
- 证据 / evidence：证据条数、`message_uid` 数量、关系边数量、引用覆盖率、工具 observation 数。
- 不确定性 / uncertainty：confidence、audit risk、missing media、sampling warning、posterior status。
- 传播性质 / transport：转发链、扩散方式、载体类型、媒体类型、图片/视频/文件/语音路径。
- 实现细节：关键词、命中片段、`source_packet`、candidate id、raw relation edge id、tool name、cache key。

如果产品需要展示这些信息，必须另做折叠区或调试区，并标注为 `Inspect` / `Raw`。不得把它们和 shi 成分雷达混画。

## 顶层字段契约

`compact_payload.group_insights` 应保持以下结构：

```json
{
  "schema_version": "orch_group_insights_v1",
  "group_portrait": {},
  "shi_type_profile": {},
  "member_portraits": [],
  "style_sample_pack": {},
  "inspect": {}
}
```

字段含义：

- `schema_version`：固定为 `orch_group_insights_v1`，用于前端选择解析器。
- `group_portrait`：用户向群画像摘要，展示群聊窗口整体状态。
- `shi_type_profile`：用户向 `shi` 类型构成，雷达图唯一数据源。
- `member_portraits`：用户向群友风格速写，仅覆盖当前窗口。
- `style_sample_pack`：样本文案包，用于辅助感知群内说话风格。
- `inspect`：诊断材料，只能进入 Inspect/Raw。

前端不得从 `inspect` 派生主线图表、主线标题或主线标签。

## 群画像字段契约

`group_portrait` 面向普通用户展示“这段群聊整体是什么样”。

```json
{
  "schema_version": "orch_group_portrait_v1",
  "title": "当前群聊窗口",
  "summary": "本窗共有 ...",
  "message_count": 0,
  "sender_count": 0,
  "asset_count": 0,
  "missing_asset_count": 0,
  "dominant_shi_types": [],
  "time_window": {
    "start_timestamp_iso": null,
    "end_timestamp_iso": null,
    "duration_minutes": null
  },
  "risk_notes": []
}
```

公共展示规则：

- `title` 和 `summary` 可以作为卡片主标题和摘要。
- `message_count`、`sender_count`、`asset_count` 可以展示为窗口统计。
- `missing_asset_count` 和 `risk_notes` 是边界提醒，不是雷达轴。
- `dominant_shi_types` 只能展示动态雷达里的用户向标签。
- `time_window` 必须配合“当前窗口 / 本次样本”口径，不得写成全群长期结论。

禁止：

- 不得把 `risk_notes` 写成模型置信度。
- 不得把 `missing_asset_count` 写成内容缺陷结论。
- 不得把窗口内 `sender_count` 写成全群活跃人数。

## shi 类型画像字段契约

`shi_type_profile` 是动态 shi 成分雷达的数据源。

```json
{
  "schema_version": "orch_user_facing_shi_type_profile_v1",
  "axes": [
    {
      "axis_id": "snapdragon_pose_shi",
      "label": "高通嘴硬 shi",
      "score": 0,
      "summary": "技术立场与消费选择错位最突出。",
      "description": "围绕高通立场、购买选择和群友围观形成的 shi 味。",
      "evidence_messages": [
        {
          "message_uid": "msg_x",
          "quote": "可追溯到 QQ 原文的一句短引用"
        }
      ]
    }
  ],
  "dominant_axes": [],
  "display_policy": "user_facing_shi_composition_not_source_or_provenance_axes",
  "axis_generation_mode": "model_authored",
  "axis_count": 3,
  "axis_count_bounds": {"min": 0, "recommended_min": 3, "max": 8}
}
```

公共字段：

- `axes[*].axis_id`：稳定短 ID；优先用模型输出，后端可归一化。
- `axes[*].label`：模型生成的用户向短标签，不是固定词表。
- `axes[*].score`：`0..100` 整数，用于雷达半径。
- `axes[*].summary`：一句用户向解释。
- `axes[*].description`：标签说明。
- `axes[*].evidence_messages`：绑定到 QQ 原文的依据列表，至少包含 `message_uid` 或可匹配短引用。
- `dominant_axes`：从 `axes` 中取显著轴的短列表。
- `display_policy`：必须保留，用来显式声明雷达不是来源/证据/provenance 图。

诊断字段：

- 如果 payload 中存在关键词命中、内部 scoring trace 或工具路径，前端只能放入 `Inspect` / `Raw`。
- 主线雷达只能读取 `axis_id`、`label`、`score`、`summary`、`description` 和用于“查看相关原文”的 `evidence_messages`。
- `evidence_count` 不得作为 score label、tooltip 主文案或排序依据展示给普通用户。

校验规则：

- `axes` 可以包含 `0..8` 个公共轴；推荐 `3..8`，但不能为凑数补轴。
- 每个公共轴必须有可绑定到当前 source packet 的 `evidence_messages`；绑定失败的轴必须被后端 guardrail 移除。
- `score` 缺失、非数值或越界时，前端应降级为 `0` 并记录 Inspect warning。
- `display_policy` 不匹配时，前端应隐藏雷达或降级为普通列表，避免误展示。
- `dominant_axes[*].axis_id` 必须存在于 `axes[*].axis_id`。

## 群友画像字段契约

`member_portraits` 是窗口内群友风格速写，不是用户长期人格画像。

```json
[
  {
    "sender_id": "user_x",
    "sender_name": "昵称",
    "display_name": "昵称",
    "message_count": 0,
    "asset_count": 0,
    "reply_count": 0,
    "style_tags": ["普通参与"],
    "sample_quotes": []
  }
]
```

公共展示规则：

- `display_name` 是主显示名，`sender_id` 默认不得裸露在普通用户主线，除非产品已采用 alias 化策略。
- `message_count`、`asset_count`、`reply_count` 只能说明当前窗口行为。
- `style_tags` 是窗口内说话风格 / 话题提示，不是 `shi` 成分轴。例如“硬件/技术话题”“抽象吐槽”“普通参与”。
- `sample_quotes` 可展示为短引用，但需要长度限制和敏感信息裁剪。

禁止：

- 不得写成“这个人就是某类人”。
- 不得把窗口内发言多直接解释成群内核心成员。
- 不得把 raw QQ 号、raw sender id、内部 alias map 放入主线。
- 不得把 `reply_count` 写成真实社交地位。

## style_sample_pack 字段契约

`style_sample_pack` 用于补充“这群人怎么说话”的感觉。

```json
{
  "schema_version": "orch_style_sample_pack_v1",
  "samples": [
    {
      "sender_id": "user_x",
      "display_name": "昵称",
      "style_tags": [],
      "quotes": []
    }
  ],
  "notes": []
}
```

公共展示规则：

- 展示为轻量样本区，不要抢占主审结果和 shi 成分雷达。
- `notes` 必须保留“只用于快速感知风格”“不要当作真实身份/长期人格”的边界语义。
- 样本区可以折叠，但不应混入 Raw JSON。

## Inspect / Raw 字段边界

`inspect` 和 Raw JSON 可以包含：

- `message_count`、`sender_count`、`tool_observation_count`。
- source packet、candidate、cache key、tool observation、relation edge raw id。
- 关键词命中、scoring trace、signals、evidence_count。
- evidence package、message uid、relation edge id、missing media detail。
- sampling、posterior、confidence、audit risk、remaining limits。

这些字段的用途是审查和调试，不是产品主叙事。前端可以提供“查看依据 / Inspect / Raw”入口，但默认主线必须保持用户向画像语义。

## 前端展示要求

主线布局建议：

1. 顶部：`group_portrait.title`、`group_portrait.summary`、窗口统计。
2. 中部：`shi_type_profile.axes` 动态雷达，标题必须包含“shi 类型构成”或等价用户向表达；若有效轴少于 `3` 个，前端应清楚显示“有效成分较少”，不要补假轴。
3. 雷达旁：`dominant_axes` 列表，展示标签和一句 summary。
4. 下方：`member_portraits` 群友风格速写，明确“本窗口”。
5. 辅助：`style_sample_pack` 样本区。
6. 折叠：Inspect / Raw，用于证据、来源、工具、候选和不确定性。

主线文案要求：

- 使用“本窗口”“这段群聊”“当前样本”。
- 不使用“全群真实构成”“长期人格”“模型确认”“证据强度最高”。
- 雷达 tooltip 只解释类型含义和当前 summary。
- 如果显示 score，命名为“显著度”或“构成强度”，不得命名为“置信度”。

视觉要求：

- 雷达使用模型输出且证据绑定成功的用户向类型轴，前端不得自行补固定轴。
- 不允许动态把来源/证据/不确定性变成额外轴或替换某一轴。
- 复读、接梗、转人工、客服腔等纯行为特征不得作为 `shi` 成分轴；如需展示，应进入 `behavior_trait_profile` 或 Inspect。
- missing media、audit risk 和 tool calls 只能用边界提醒或 Inspect badge，不得覆盖雷达颜色。

## 当前实现状态

已落实：

- 后端 `build_group_insights()` 只采用模型输出且证据绑定成功的用户向 `shi` 类型轴，并声明 `display_policy = "user_facing_shi_composition_not_source_or_provenance_axes"`。
- ORCH model-led 路径和 deterministic/headless 路径都会把 `group_insights` 附加到 `AnalysisOutput.compact_payload`。
- LLM Session final report ViewModel 会校验 `display_policy`，非用户向来源 / provenance 轴不会进入主线 UI。
- Review Editor 的 `GroupInsightsPanel.vue` 已实现动态雷达，而不是只用条形列表。
- Review Editor 会展示窗口统计、主导成分、动态雷达、成员简表和说话风格样本，避免只把内部 JSON 留给用户猜。
- 前端群友画像主线默认显示昵称或 alias，不再显示 `QQ <uid>` 这种裸身份标签。
- 后端 guardrail 会移除无法绑定到当前 source packet 的轴，避免模型凭空生成“看似合理”的类型。

当前边界：

- 旧 full-analysis SVG/雷达如果仍使用来源、证据、传播或置信度轴，只能视为内部研究图，不得迁移为公共 `shi` 成分雷达。
- `group_insights` 的模型动态轴仍需要更多语料校准；模型缺失或无效时应少显示或不显示雷达，不再用 deterministic fallback 补公共 `shi` 类型轴。
- 关系图 UI 和 evidence package UI 是独立问题，不允许把关系边数量、证据数量或工具补证路径混入 `shi_type_profile.axes`。

维护要求：

- 模型可以在每个窗口新增不同的用户向 `shi` 类型轴；前提是同一 display policy、可绑定 QQ 原文证据、且不混入内部维度。
- 新模型、新 prompt 或新 worker 输出 group insights 时，必须保留同一 `display_policy`，否则前端会隐藏雷达。
- 如果未来把群画像扩展为跨窗口 / 长期画像，需要新增 schema version，不能复用当前“本窗口画像”语义。

## 验收项

后端 / 契约验收：

- `compact_payload.group_insights.schema_version == "orch_group_insights_v1"`。
- `shi_type_profile.schema_version == "orch_user_facing_shi_type_profile_v1"`。
- `shi_type_profile.display_policy == "user_facing_shi_composition_not_source_or_provenance_axes"`。
- `shi_type_profile.axes` 包含 `0..8` 个公共轴，顺序按模型输出或后端归一化结果保持；通常建议 `3..8`，但不能凑数。
- 每个公共轴的 `score` 是 `0..100` 数字。
- 每个公共轴必须有可绑定到 QQ 原文的 `evidence_messages`。
- `dominant_axes` 的所有 `axis_id` 都能在 `axes` 中找到。
- 来源、证据、不确定性、传播性质、工具细节不得新增为公共雷达轴。

前端验收：

- 雷达标题明确是 `shi` 类型构成。
- 主线不出现 `message_uid`、raw sender id、raw edge id、tool name、source packet、candidate id。
- 主线不把 `score` 写成 confidence。
- `evidence_count`、`signals` 如存在，只能在 Inspect/Raw 查到。
- 复读、接梗、转人工、客服腔等纯行为特征不作为公共雷达轴。
- `member_portraits` 文案明确是窗口内风格速写。
- 缺失媒体、audit risk、remaining limits 出现在边界提醒或 Inspect/Raw，不进入雷达。

回归验收：

- 构造一个 forward 很多但内容类型单一的样本，雷达不得出现“forward/传播”轴。
- 构造一个证据很多但类型明确的样本，雷达只能提高对应类型显著度，不得显示“证据强”轴。
- 构造一个 missing media 很多的样本，雷达不得新增“资源缺失/图片缺失”内部轴，missing 信息只进入边界提醒或 Inspect/Raw。
- 构造一个工具补证成功的样本，tool observation 不得成为雷达轴。

## 未来扩展

允许扩展：

- 新增 `axis_generation_notes`，用于解释模型轴缺失、部分输出或证据绑定失败的原因。
- 新增本地化标签，如 `label_i18n`，但不得改变当前轴的用户向语义。
- 新增时间序列趋势，例如多个窗口的 `shi` 类型变化，但趋势图仍只能使用用户向类型轴。
- 新增“为什么是这个类型”的用户向解释卡，但证据明细仍从 evidence package 或 Inspect/Raw 打开。
- 新增群友画像的 alias 保护层和样本引用跳转，但不得暴露 raw 身份。

不允许扩展：

- 把 provenance/source/evidence/confidence/transport 混入 shi 成分雷达。
- 用雷达承担审计、证据包或工具链可视化。
- 把窗口画像升级成全群永久画像，除非另有 posterior / 全量统计契约并提升 schema version。

## 一句话结论

`group_insights` 的公共层只讲用户能理解的群聊感觉、群友风格和 `shi` 类型构成。动态雷达永远是 `shi` 类型雷达，不是来源图、证据图、置信度图或传播图；这些内部审查维度只能留在 `Inspect` / `Raw`。
