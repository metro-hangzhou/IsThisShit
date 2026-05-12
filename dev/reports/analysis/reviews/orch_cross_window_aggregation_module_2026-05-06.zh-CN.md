# ORCH 跨窗口群画像聚合模块化记录

日期：2026-05-06

## 背景

`scripts/run_benshi_group_full_analysis.py` 原本同时承担全链路脚本编排、窗口选择、单窗分析、跨窗口聚合和 markdown 输出职责，文件长度超过 1000 行。按照当前维护规则，脚本层应保持薄，跨窗口群画像 / 群友画像 / shi 成分分布这类可复用逻辑应进入 `src/qq_data_analysis/orch/`。

## 本次调整

新增 `src/qq_data_analysis/orch/group_aggregation.py`，承载以下稳定聚合能力：

- `aggregate_group_outputs(...)`：把多个 window-level LLM 输出聚合为群级摘要。
- `build_member_profiles(...)`：结合原始 JSONL 和窗口输出生成群友画像候选。
- `component_family_distribution(...)`：聚合跨窗口 shi 成分 family 分布。
- `render_group_profile_markdown(...)`：生成面向人工审阅的群画像 markdown。

`scripts/run_benshi_group_full_analysis.py` 现在只保留管线编排、输入输出、窗口选择、SVG 写出等脚本职责，并从 ORCH 模块导入聚合函数。

同时补齐 `group_portrait_method` 要求的群画像输出契约：

- `implementation_status`：明确当前是 `prototype_sampled_window_aggregation`。
- `scope_statement`：说明抽样窗口数、覆盖消息数和不可冒充全群永久画像。
- `known_gaps`：列出 sampled windows、多模态缺失和群友画像边界。
- `heuristic_warning_block`：提醒 topic/carrier/活跃发送者不能直接当作 shi 结论。
- `component_summary` / `reaction_summary` / `transport_summary`：同时暴露 raw counts 和 normalized ratios。

## 架构边界

- 聚合模块只做确定性统计、归并和呈现，不发明新的用户侧 shi 类型。
- `shi_type_profile` 的用户侧类型仍由模型输出，并由 guardrail 做证据绑定和剪枝。
- 跨窗口聚合可以统计 `baseline_topics`、`dominant_core_objects`、`interaction_style`、群友行为特征等，但不能把 routine topic 或行为统计直接升级为 shi 结论。
- 脚本可继续负责具体产物落盘；模块提供可被 CLI、GUI、批处理和后续 ORCH 阶段复用的函数。

## 验证

已执行：

```text
python -m py_compile scripts\run_benshi_group_full_analysis.py src\qq_data_analysis\orch\group_aggregation.py
python -m pytest tests\test_benshi_group_full_analysis_script.py -q --basetemp .pytest_tmp_orch_group_aggregation_20260506
python -m pytest tests\test_benshi_group_full_analysis_script.py tests\test_chat_orchestrator_runtime.py tests\test_final_report_view.py -q --basetemp .pytest_tmp_orch_group_related_20260506
python -m pytest tests\test_benshi_group_full_analysis_script.py tests\test_chat_orchestrator_runtime.py tests\test_final_report_view.py -q --basetemp .pytest_tmp_orch_group_contract_20260506
```

结果：

- `test_benshi_group_full_analysis_script.py`：4 passed
- ORCH 相关组合测试：56 passed
- 契约补齐后 ORCH 相关组合测试：56 passed

## 后续接点

- 后续“群画像 / 群友画像 / 跨窗口 shi 成分”正式产品化时，应优先扩展 `group_aggregation.py`，不要再把新聚合逻辑塞回脚本。
- review-editor 如果需要展示跨窗口群画像，应读取聚合后的结构产物，而不是反向解析 markdown。
- 若需要加入跨群对比，应新增独立模块，例如 `group_comparison.py`，避免把跨群逻辑混入单群跨窗口聚合。
