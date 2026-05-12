# ORCH 弱绑定升级防护记录

> Date: 2026-05-06
> Scope: ORCH model-led review payload, BenshiMaster-style `shi` judgment.

## 问题

模型可能把“时间相邻的后续解释”当成强证据，从而把原本直接可审的图文梗错误改名为后续解释里的普通对象。

典型形态：

- 前一条 QQ 原文已经有可审配文和图片。
- 后面有人问“这啥”。
- 再后面有人回答一个普通解释。
- 回复链补证为空，或只能确认时间相邻。
- 模型仍把普通解释升级为非 boundary `shi` 名称。

这不是 UI 问题，而是 ORCH 语义边界问题。

## 最新规则

弱绑定不能支撑非 boundary 结论。

弱绑定包括：

- 时间相邻
- 普通后续问答
- 工具空返回或失败
- 未确认回复链
- `boundary_edges` / `rejected_edges` / `open_questions`

可以支撑非 boundary 结论的只有：

- 直接 QQ 原文
- 同条消息上的文本和媒体绑定
- 带 QQ 原文证据的 confirmed relation edge
- 有实际内容的工具返回

## 实现

Prompt 侧：

- `src/qq_data_analysis/orch/model_prompt_contract.py`
- 明确要求相邻解释、失败回复链、工具空返回只能进入 boundary/open question。

Runtime 侧：

- `src/qq_data_analysis/orch/model_result_guardrails.py`
- 在 JSON schema validation 后、observer/report materialization 前执行。
- 对弱绑定证据执行删除、降级或重写。
- 若强证据仍存在，则保留强证据并把对象重写回直接 QQ 原文锚点。
- 若只剩弱证据，则降级为 `role=boundary` / `result_kind=topic`。
- 同步修剪 `shi_type_profile` 里依赖弱绑定的 axis/signals。

测试侧：

- `tests/test_chat_orchestrator_runtime.py::test_model_result_guardrail_rewrites_weak_adjacent_explanation_to_boundary`
- 使用合成数据覆盖，不把真实样本词写死进规则。

## 实测

Session:

- `live_c3ee7dcc360c62`
- Source run: `amd_guanren_group_712742342_run_20260417_001344_orch`
- Candidate: `group_712742342_candidate_001`

结果：

- 直接图文配文被保留为独立可审对象。
- 未确认后续问答被放入 boundary。
- 后续普通解释没有命名或升级非 boundary `shi` 结果。

## 后续注意

不要用样本词做 prompt patch。

如果后续出现类似误判，应优先检查：

- 模型是否把弱关系写进了 `confirmed_edges`
- 工具 observation 是否缺少 empty/failure 语义
- direct QQ evidence 和 boundary evidence 是否混在同一条 evidence 中
- `shi_type_profile` 是否引用了被删除的弱证据
