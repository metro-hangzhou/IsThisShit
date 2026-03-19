# Analysis / LLM / Chat Parsing Roadmap

## Current implementation snapshot

截至 `2026-03-18`，第一批“导出器之后”的分析底座已经开始落地，不再只是纯规划。

### 已落地模块

- `src/qq_data_process/`
  - `models.py`
  - `service.py`
  - `adapters/exporter_jsonl.py`
  - `preprocess_types.py`
  - `preprocess_models.py`
  - `preprocess_registry.py`
  - `preprocess_profiles.py`
  - `preprocess_service.py`
- `src/qq_data_analysis/`
  - `models.py`
  - `interfaces.py`
  - `service.py`
  - `llm_agent.py`
  - `summary.py`
  - `preprocessors/thread_compaction.py`
  - `preprocessors/topic_windows.py`
  - `preprocessors/asset_recurrence.py`
  - `preprocessors/forward_expansion.py`
  - `preprocessors/context_budget.py`
  - `preprocessors/expired_asset_inference.py`

### 已具备能力

- `build_corpus_from_export(...)`
  - 将现有导出 bundle 构建成 corpus
- `load_corpus(...)`
  - 从 `corpus/` 回读标准化数据
- `run_analysis(...)`
  - 支持插件注册、依赖拓扑排序、落盘 findings / summary
- `build_preprocess_view(...)`
  - 在 corpus 之上构建可插拔预处理视图

### 已具备的 preprocess profile

- `raw_only`
- `compact_default`
- `meme_focus`
- `raw_plus_processed`

### 已落地的预处理专项指令输入

预处理层现在支持可选的 `PreprocessDirective` 输入，用于描述：

- 这次预处理真正服务的分析目标是什么
- 哪些话题是重点保留对象
- 哪些话题/参与者/消息模式应被压缩或抑制
- 是否启用“抠掉无关闲聊、只保留专项上下文”的策略

当前设计原则已经固定：

- `directive` 只能影响 **processed/preprocess view**
- 不允许改写 `raw / bypass truth layer`
- 对“无关信息”的处理只能是：
  - `compact`
  - `suppress`
  - `annotate`
- 不允许直接从原始 corpus 硬删除

### 已落地的首批预处理插件

- `thread_compaction_preprocessor`
- `topic_window_builder`
- `asset_recurrence_preprocessor`
- `forward_bundle_expander`
- `expired_asset_inference_preprocessor`

### 已验证的 smoke

基于真实导出：

- `exports/group_922065597_20260317_224355_864151.jsonl`

已完成这些验证：

- corpus 构建成功
- corpus 回读成功
- `compact_default` preprocess view 成功落盘
- `meme_focus` preprocess view 成功落盘

当前 smoke 结果特征：

- `compact_default`
  - `success_count=2`
  - `thread_count=124`
  - `annotation_count=124`
- `meme_focus`
  - `success_count=5`
  - `thread_count=135`
  - `asset_count=182`
  - `annotation_count=317`

### 当前仍属于骨架阶段的部分

- `expired_asset_inference_preprocessor`
  - 目前只负责结构化上下文装配和预算控制
  - 还没有接入真实 LLM provider 做内容逆推
- `caption / OCR / ASR / VLM`
  - 还没接上
- `identity resolution / event extraction / topic timeline`
  - 还在待实现阶段

### 现阶段结论

- corpus layer 已经从“想法”变成“可运行代码”
- preprocess layer 已经从“想法”变成“可运行代码”
- 当前最适合继续推进的是：
  - `forward_decomposer` 继续深化
  - `asset recurrence` 向 repost / 搬 shi 分析靠拢
  - `expired asset inference` 接入真实 agent 调度
  - `identity / event / topic` 三条确定性 enrich 链

## Goal

在当前导出器已经基本稳定的前提下，开始规划“导出之后”的第二阶段：

- 数据分析底座
- 聊天记录解析与结构化
- LLM / RAG / 检索工作流
- 面向“搬 shi 分析”的专题分析能力

目标不是立刻把所有分析功能塞进 `main`，而是先把：

1. 可靠的数据契约
2. 明确的模块分层
3. 可逐步验收的开发顺序

先钉死。

## Current reality

### What we already have

- 稳定的导出入口：
  - `app.py export-history`
  - REPL `/export`
  - watch 内导出
- 统一的标准化模型：
  - `SourceChatSnapshot`
  - `NormalizedSnapshot`
  - `NormalizedMessage`
  - `NormalizedSegment`
- 统一的导出产物：
  - `*.jsonl`
  - `*.txt`
  - `*.manifest.json`
  - `<stem>_assets/`
- 比较成熟的资源物化 / 缺失分类 / 取证能力

### What we do not really have yet

- 可持续使用的“分析子系统源码”
- 可复用的 corpus build 管线
- 面向检索/LLM 的 chunk / doc / event / entity 层
- 聊天线程、人物身份、事件流、话题流的稳定结构化表示
- 可直接让 LLM 使用的索引与检索接口

### Important branch reality

- 当前 `main` 分支是运行面分支。
- `README.md` 已明确：`main` 不应继续承载完整分析 / RAG 开发工作。
- 当前 `src/qq_data_analysis/` 和 `src/qq_data_process/` 在这个分支里基本是空壳目录，不应误判为“已有可继续迭代的成熟源码”。

结论：

- 分析阶段应视为“新产品线”启动，而不是“把几个函数补完”。

## Core design principle

后续必须强制分层，避免再把“导出、解析、分析、LLM”混成一坨。

建议固定为四层：

1. Export layer
2. Corpus layer
3. Analysis layer
4. LLM / Retrieval layer

## Layer 1: Export layer

职责：

- 从 NapCat / QQ 拿到可追溯、可复核的原始导出结果
- 保留 manifest、assets、missing、forensics

输入：

- 聊天目标
- 时间范围 / data_count

输出：

- `jsonl/txt`
- `manifest`
- `assets`
- `trace`
- `forensics`

这一层现在已经基本成立，后续只做维护，不再承载分析逻辑。

## Layer 2: Corpus layer

这是下一阶段最先要补的“数据分析底座”。

职责：

- 把一轮或多轮导出结果整理成可复用 corpus
- 解决“重复导出、跨批次、跨群、跨好友”的数据归档问题
- 生成统一 schema 和 lineage

建议输出对象：

- `CorpusManifest`
- `CorpusChat`
- `CorpusMessage`
- `CorpusSegment`
- `CorpusAsset`
- `CorpusEntityRef`
- `CorpusEventRef`

建议最小字段：

- source lineage
  - export run id
  - source file path
  - message id / seq / raw id
- chat identity
  - group/private
  - chat_id
  - chat_name
- sender identity
  - sender_id
  - sender_name
  - sender_card
- time
  - timestamp_ms
  - timestamp_iso
- content
  - content
  - text_content
  - segments
- attachment linkage
  - asset ids
  - exported_rel_path
  - materialization status
- provenance
  - normalization version
  - schema version
  - profile

建议最小落地形态：

- `corpus/manifest.json`
- `corpus/messages.jsonl`
- `corpus/assets.jsonl`
- `corpus/chats.jsonl`
- `corpus/build_report.json`

后续再考虑：

- `parquet`
- `duckdb`
- `sqlite`

但一开始不要同时上三套。

### Recommendation

第一版优先：

- `jsonl + build_report`

第二版再上：

- `duckdb`

原因：

- 先把 schema 和 lineage 钉死，比一开始选数据库更重要。

## Layer 3: Parsing / enrichment layer

这是“聊天记录解析”真正该干的地方。

职责：

- 在不依赖 LLM 的前提下，先做稳定的结构化 enrich

建议拆成 6 个子模块：

1. Identity resolution
2. Conversation threading
3. Forward decomposition
4. Event extraction
5. Entity extraction
6. Content classification

### 3.1 Identity resolution

目标：

- 同一人多种显示名、群名片、昵称、QQ号之间做弱绑定

输出：

- `IdentityCluster`
- `IdentityAlias`

### 3.2 Conversation threading

目标：

- 把 reply、连续消息、短时互动整理成 thread / exchange

输出：

- `Thread`
- `ThreadMessageRef`

### 3.3 Forward decomposition

目标：

- 不再只把 forward 当一个 segment
- 而是显式保留：
  - outer forward message
  - inner forwarded messages
  - inner assets / inner reply / inner sender

### 3.4 Event extraction

先做规则版，不上 LLM。

目标事件类型建议从最小集合开始：

- join / leave / mute / recall
- file shared
- link shared
- image burst
- video burst
- repeated repost / repeated forward
- direct reply / directed mention

### 3.5 Entity extraction

先不追求百科级 NER。

优先抽：

- 人名 / 昵称
- 群名 / 项目名
- 文件名
- 链接域名
- 作品 / 游戏 / 软件名

### 3.6 Content classification

规则优先，LLM 只做补充。

建议先分：

- ordinary chat
- logistics
- meme / joke
- quarrel / tension
- link share
- file share
- image-heavy
- video-heavy
- system / gray-tip

## Layer 4: Analysis layer

这是“搬 shi 分析”真正发生的地方。

职责：

- 对 corpus 和 enrichment 结果做面向问题的分析

建议先做 5 类分析器：

1. Chat health / rhythm
2. Participant profile
3. Topic timeline
4. Conflict / drama detector
5. Repost /搬运链分析

### 4.1 Chat health / rhythm

回答：

- 什么时候最活跃
- 谁在带节奏
- 高峰期是图、文、视频还是转发

### 4.2 Participant profile

回答：

- 谁更像发起者 / 响应者 / 搞笑者 / 搬运者 / 资料党

### 4.3 Topic timeline

回答：

- 某个时间段群里到底围绕什么在聊
- 话题怎么切换

### 4.4 Conflict / drama detector

回答：

- 哪些时间段存在明显冲突、阴阳、拉扯、围攻、嘲讽

### 4.5 搬运链分析

这是你说的“搬 shi 分析”的核心。

先定义成下面这些问题：

- 哪些内容是高频转发 / 二次搬运
- 谁是搬运源头，谁是二次传播节点
- 哪些梗图 / 视频 / 文件跨时间反复出现
- 哪些 forward 只是壳重复，哪些内层内容真的一样

这一块强依赖：

- asset identity
- forward decomposition
- thread / event / entity

所以不能在 corpus 底座没稳时直接硬上。

## Layer 5: LLM / Retrieval layer

LLM 应该放在最后一层，不应该反过来定义前面 schema。

职责：

- 基于 corpus / thread / event / entity / asset 构建可检索上下文
- 让 LLM 做：
  - 摘要
  - 归因
  - 解释
  - 假设生成
  - 争议点整理

### LLM layer should not own truth

LLM 输出必须是：

- “解释层”
- “归纳层”
- “问答层”

不应负责：

- 原始事实存储
- 最终 ID 绑定
- 时间轴真相定义

### First useful LLM tasks

建议最早落地的 LLM 能力：

1. Thread summarization
2. Topic window summary
3. Participant style sketch
4. Forward content explanation
5. Conflict summary with evidence refs

### Retrieval unit recommendation

不要直接拿“单条消息”做 RAG 最小单元。

优先级建议：

1. `thread`
2. `windowed topic block`
3. `forward inner message bundle`
4. `single message`

原因：

- 单条消息上下文太弱
- QQ 聊天的语义常常跨多条消息才成立

## Suggested module layout

下一阶段建议重新把这两块目录真正用起来：

- `src/qq_data_process/`
- `src/qq_data_analysis/`

建议职责如下：

### `src/qq_data_process/`

放“确定性处理”：

- corpus build
- enrichment
- thread build
- entity / event extraction
- chunking
- retrieval prep

### `src/qq_data_analysis/`

放“面向问题的分析”：

- profile analyzer
- topic analyzer
- drama analyzer
- repost analyzer
- llm service / llm agents

## Recommended development order

### Phase A: Corpus foundation

先做：

- 从 export bundle 构建 corpus
- 固定 schema version
- 固定 lineage
- 生成 `messages/assets/chats/build_report`

验收标准：

- 同一轮导出可稳定 build 成 corpus
- build 结果可重复
- manifest 与 corpus 数字能对上

### Phase B: Deterministic enrichment

先做：

- identity aliases
- reply/thread linkage
- forward inner message flattening
- basic event/entity extraction

验收标准：

- 对 2-3 个真实群样本能稳定生成 thread/event/entity 产物

### Phase C: Analytics substrate

先做：

- participant profile
- activity timeline
- repost / forward recurrence

验收标准：

- 不靠 LLM，也能对一个群给出基础画像和时间轴

### Phase D: Retrieval substrate

先做：

- chunk schema
- document refs
- evidence refs
- vector store abstraction

验收标准：

- 能围绕 thread / topic window 做可解释检索

### Phase E: LLM applications

最后再做：

- 群聊总结
- 人物画像
- 冲突总结
- 搬运链解释

验收标准：

- 输出里每个结论都能回链到 thread / message / asset 证据

## First concrete deliverables

下一步如果正式开工，建议第一批只做这 5 个东西：

1. `CorpusManifest` schema
2. `build_corpus_from_export(...)`
3. `corpus/messages.jsonl + assets.jsonl + build_report.json`
4. `thread_builder` 第一版
5. `repost/fwd recurrence` 第一版

原因：

- 这 5 个东西一旦站稳，后面的分析和 LLM 都会顺很多。

## Explicit non-goals for the first milestone

第一里程碑先不要做：

- 全自动“群聊真相机”
- 复杂 agent orchestration
- 多模型训练
- 大而全 dashboard
- 一开始就上在线服务
- 一开始就把 `main` 变成分析工作分支

## Decision recommendation

建议把“导出器之后”的项目节点正式定义为：

- `Milestone 1`: corpus foundation
- `Milestone 2`: deterministic parsing/enrichment
- `Milestone 3`: analysis substrate
- `Milestone 4`: retrieval + LLM

其中最先开工的是：

- `Milestone 1`

而不是直接开做 LLM。
