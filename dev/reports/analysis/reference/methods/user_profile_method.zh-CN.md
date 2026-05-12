# 群友画像方法规范

**目标**：定义一个评分 + 限制清晰的用户画像插件，使方法易于替换而非硬编码。

**输入**

- 窗口级/跨窗口的 sender metrics（消息数、forward、asset、reply、reaction、caption）。
- 在选中窗口中该用户被 reply、mention、reaction 的聚合次数。
- media gaps 与 multimodal captions 作为辅助上下文。
- 先验 persona/role 设定（可选），用于提供注释。

**评分规则**

1. 将每个候选者根据 persona 类型（社交焦点、搬运强度、发言驱动、媒体投放）计算加权得分。
2. 依据指标如 forward count、nested forward、asset count、incoming reply、distinct repliers、meaningful text 参与度构造可调权重；权重写在模板中以便调整。
3. `社交焦点候选` 需要额外硬门槛：
   - 必须有真实发送样本
   - 必须 `window_hits > 0`
   - 不能由 reply-target-only 的匿名 numeric id 直接触发
4. 取分数最高者作为该 persona Head，并附带 `score_components` 分解。
5. 计算 `confidence`（score 差距 + window hits），并写入 `confidence` 字段。

**输出字段**

- `persona_head`（label + sender id/name）。
- `score` + `score_components` + `confidence`。
- `selection_metric_description`（如“综合 forward + asset”）。
- `heuristic_status` + `known_limitations`。
- `impl_status`（method version + prototype tag）。
- `headline_candidates`
  - 最终给产品层看的头部候选
- `headline_evaluations`
  - 对每个头部候选的评分拆解和局限说明

**禁止事项**

- 不得直接输出 `best`/`top` 而不标记 `heuristic_status`。
- 不得将 reply count 最高自动认作“群宠”而不说明 alias/mention 范围。
- 不得让 `window_hits = 0` 的对象成为 `social_focus_candidate`。
- 不得忽略 `platform alias` or `mention graph` 缺失。

**已知边界**

- 当前只基于 sampled windows，不作全群画像。
- 仅把 forward count + asset count 作为搬运/媒体 signal，未来可 replace。
- Reaction-like counts是代替真实 mention 图的 proxy，存在偏差。
- 真实产品层输出不应再叫 `all_profiles`，否则容易误导成“全体群友画像”。

**部署建议**

把这个 md 插件当成 `persona scoring v1`，运行时：

1. 脚本收集所有窗口 `sender_metrics` 和 `reply_targets`。
2. 调用模板中的权重公式 + confidence 逻辑。
3. 将结果写进 `user_profiles.json` + `group_profile.md` 的 persona 表格（包括 `heuristic_status`）。
