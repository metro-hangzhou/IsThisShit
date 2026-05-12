# 搬史分析器 readiness 报告

对应 canonical 英文文件：

- [shi_analyzer_readiness_report_20260327.md](shi_analyzer_readiness_report_20260327.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_analysis_slice_20260327/source_snapshot/shi_analyzer_readiness_report_20260327.md`

## 结论先说

当前 exporter 输出已经足够作为 analyzer 的上游基础。

这意味着：

- analyzer 现在应该正式往前走
- 不应继续把 exporter 当成唯一主战场
- 也不应继续等待“完全无 missing”才开工

## 为什么说已经 ready

当前导出产物已经具备：

- JSONL canonical message records
- companion manifest
- assets 目录
- forward-heavy 内容保留
- missing media 状态显式保留，而不是悄悄吞掉

这对 analyzer 来说已经够用，因为 analyzer 本来就应该区分：

- direct evidence
- context-only inference
- unknown gaps

## 这份 readiness 报告最重要的启发

### 1. exporter 不再是唯一主战场

当前 repository 的主战场应该切到：

- preprocess
- analysis substrate
- report-first analysis
- benshi / shi 分析链路

### 2. 三个大群暂时不要先定角色

虽然现在直觉上可能会把：

- `763328502`
  视为更像主正样本
- `712742342`
  视为更像控制语料

但当前正确规则仍然是：

- 先跑 deterministic 和 report-first
- 再做角色校准

### 3. readiness 不等于分析器已经完成

这份报告只表示：

- 输入已经够用了

并不表示：

- ontology 已冻结
- benshi agent 已完成
- corpus roles 已定
- 分析器已经到 final form

## 当前 analyzer 最该做的事

1. 统一 corpus ingest
2. 跑 preprocess
3. 跑 deterministic analysis
4. 校准 3 个大群的角色
5. 再进入更深的 benshi/report-first
