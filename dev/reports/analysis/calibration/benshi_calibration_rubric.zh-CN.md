# 搬史校准 rubric

对应 canonical 英文文件：

- [benshi_calibration_rubric.md](benshi_calibration_rubric.md)

## 这份文件在 cleaned slice 里的角色

它是：

- `calibration`

不是：

- `reference ontology`
- `current execution plan`

因为它关心的是：

- 证据层级怎么分
- 置信度怎么校准
- 哪些判断暂时够稳定

## 核心结构

### 1. Evidence tiers

- `Direct Observed Evidence`
- `Context-Only Inference`
- `Adversarial / Motive Hypothesis`
- `Unknown / Missing-Media Gaps`

这三层的真正价值在于：

- 强迫 analyzer 区分看到的、推到的、未知的

这里需要补成四层理解：

- `Direct Observed Evidence`
- `Context-Only Inference`
- `Adversarial / Motive Hypothesis`
- `Unknown / Missing-Media Gaps`

其中 `Adversarial / Motive Hypothesis` 的地位是：

- 允许存在
- 允许更恶意、更敌意、更不留情面
- 但必须比普通 context-only inference 更谨慎
- 永远不能伪装成直接观察事实

### 2. Calibration questions

它最关键的问题其实是：

- 这是直接证据还是上下文推断？
- 如果 missing media 反过来打脸，这个判断还成立吗？
- 观察和解释有没有混在一起？

### 3. Stable dimensions

当前看起来相对稳定的维度包括：

- `interaction_density`
- `information_density`
- `content_provenance`
- `narrative_coherence`
- `media_dependence`
- `uncertainty_load`
- `topic_type`
- `followup_value`

### 4. Soft role labels

这份 rubric 也支持这些 soft role labels：

- `narrative_carrier`
- `relay_forwarder`
- `topic_initiator`
- `noise_broadcaster`
- `question_probe`
- `reaction_echoer`
- `resource_dropper`

## 当前最重要的 guardrails

- 不要从一个 pilot 冻结终态 taxonomy
- 不要把 inferred media meaning 并进 direct evidence
- 不要因为报告听起来合理，就偷偷抹掉不确定性
- 允许二阶/动机/敌意假说，但必须：
  - 明确标成假说层
  - 给出 evidence basis
  - 给出 confidence
  - 给出反证边界
