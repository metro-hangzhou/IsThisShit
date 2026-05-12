# 分析上下文刷新

对应 canonical 英文文件：

- [analysis_context_refresh_20260327.md](analysis_context_refresh_20260327.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_analysis_slice_20260327/source_snapshot/analysis_context_refresh_20260327.md`

## 这份报告的作用

它是当前 analyzer 侧的现实状态校准文档，用来回答：

- 现在分析器到底做到哪了
- 哪些代码已经存在
- 哪些只是规划
- 下一步主线到底是什么

## 当前最关键的事实

### 1. exporter 已经不是主阻塞

现在 exporter 这条线已经足够强，分析器侧不应该再继续等“未来某天 zero-missing”这种幻想条件。

分析器应该开始在：

- 直接证据
- context-only inference
- unknown gaps

三层分离的前提下继续推进。

### 2. 分析器不是空白项目

当前已经恢复并可见的基线包括：

- `src/qq_data_process/`
- `src/qq_data_analysis/`

这意味着正确策略是：

- 恢复
- 校验
- 在现有基线上继续推进

而不是重头设计一遍。

### 3. 四份本地语料已经进入统一工作面

#### 中央稠密基准

- `shi_group_751365230`

当前角色：

- `central_reference_baseline`
- `dense_shi_baseline`
- `manual_review_anchor`
- 删除保护开启

#### 三份大群稀疏语料

- `amd_guanren_group_712742342`
- `amd_guanren_group_763328502`
- `x3c_group_757773326`

当前规则：

- 都暂时视为 `pending_role_assignment`
- 不能先凭印象把它们定成正样本/控制样本/多样性样本
- 必须等 deterministic + report-first 校准结果来决定

## 已经实现的部分

### `qq_data_process`

已存在：

- exporter/QCE/TXT adapters
- canonical ingest
- preprocess view build/load
- preprocess profiles
- chunking policies
- SQLite + 向量基础设施

### `qq_data_analysis`

已存在：

- `AnalysisService`
- deterministic agents
- `BenshiAnalysisPack`
- `BenshiMasterAgent`
- whole-window LLM path
- preprocess overlay 进入 analysis materials

## 当前还缺什么

1. 更稳定的 corpus ingest facade
2. 全 analyzer 面 retro-review
3. 三个大群的角色校准
4. 大语料的 runtime budget policy

## 下一步主线

下一阶段最合理的顺序仍然是：

1. corpus ingest
2. preprocess
3. deterministic analysis
4. 大群角色校准
5. 然后才继续加深 `Benshi` / report-first
