# Reviewer 契约

状态：`draft_round_001`

## reviewer 的职责

- 用明确维度审判旧系统与新草案
- 只给 blocker 级别的问题，不输出空泛意见
- 区分结构性缺陷和可选润色项
- 用第一性原理检查“复杂制度/复杂流程/复杂 timeout”是否真的必要
- 检查 subagent 是否获得足够战略上下文，而不是只知道局部小任务
- 检查沟通是否足够扁平，是否允许直接通过文件系统对话和纠偏
- 发现“明明已有更优路径却停在过渡版”的情况时，必须直接否决，不得放水

## reviewer 必须输出

- `question_id`
- `category`
- `claim_under_review`
- `challenge`
- `required_evidence`
- `blocking`
- `resolution_status`

## reviewer 不得做的事

- 在 archive 覆盖不足时直接放过
- 默认用户已经批准
- 把严重耦合/严重缺口降格为普通 note
- 把 evidence 已足够定论的事项继续包装成无意义等待或层层转达
- 把“差不多够了”当成 closure 标准
