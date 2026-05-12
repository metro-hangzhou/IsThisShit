# 证据优先决策法

状态：`draft_round_003`

## 核心规则

当 evidence 已经达到决策阈值时，workflow 必须允许直接 fast-close 或 fast-fail，而不是为了流程形式感继续浪费时间。

## 含义

- timeout 的存在是为了处理不确定性，不是为了假装系统在思考
- 层级存在是为了协调，不是为了压制已经足够强的证据
- 证据优先不是只反对 timeout，而是反对一切“明明能定，却继续绕”的坏工程
- 这条法则要求系统具备：
  - 证据思维
  - 决定思维
  - 因果追溯思维

## 更广义的坏模式

除了 timeout，这条法则同样反对：

- 多余的 fallback 串联
- 明知低价值却继续跑的探测
- 已经被证据打死的路径仍然被当成候选
- 纯粹因为“之前就是这么写的”而保留下来的冗余流程

## reviewer 执法点

reviewer 可以在下面情况直接出 blocker：

- evidence 已经足够
- 但系统仍继续维持一个明显已死的路径

对应 blocker：

- `evidence_decision_fidelity`
- `latency_waste_risk`
- `decision_quality`
- `causal_traceability`

## 强制 artifact

当 evidence 已足够并触发直接短路时，系统应能留下至少一种运行态证据：

- `objection_or_fast_fail_notice.md`
- 或 challenge register 中的 `evidence_based_shortcut`

否则 reviewer 无法确认这条制度真的被执行。
