# ORCH shi 类型轴契约加固记录

日期：2026-05-06

## 背景

近期实测暴露出两个问题：

- 模型会把“复读”“接球”“转人工”等行为现象误升级成 `shi` 类型。
- 旧 deterministic fallback 会补出“硬件/技术 shi”“管人/八卦 shi”等通用分类，导致雷达看起来像写死标签，而不是当前窗口真实成分。

这会让用户误以为雷达图是模型从 QQ 原文中审出来的结论，实际却混入了内部兜底逻辑和粗粒度话题分类。

## 新规则

- `shi_type_profile.axes` 必须由模型按当前窗口生成。
- 每个轴必须有 `evidence_messages`，并能绑定到当前 source packet 里的 QQ 原文。
- 有效轴通常建议 `3..8` 个，但证据只支持 `1..2` 个时必须少输出；没有有效轴时输出空列表。
- 后端不再用 deterministic fallback 补公共 `shi` 类型轴。
- 复读、接球、转人工、客服腔等纯行为只能进入 `behavior_trait_profile` 或 Inspect，不能进入雷达。
- “硬件/技术”“管人/八卦”这类粗粒度话题词只能作为说话风格或窗口背景提示，不能直接作为 `shi` 类型轴。

## 已落地

- `group_insights.py` 移除固定/兜底 `shi` 类型轴和关键词打分死代码。
- `model_result_guardrails.py` 增加未绑定证据轴剪枝，模型输出的轴必须能回溯到 QQ 原文。
- `model_result_guardrails.py` 修复弱绑定后处理误伤：只有模型和证据都确实指向图文配文时，才允许把弱绑定对象改写为“图片配文玩梗 shi”；硬件、跑分、功耗等非图片证据不会再被误改名。
- `model_result_guardrails.py` 增加 `signals -> source packet` 反向绑定：模型只写了可审原文信号但漏填 `evidence_messages` 时，后处理会从当前 QQ 原文包中补齐绑定；绑定不到的信号会被移除，避免前端出现无法点开的线索。
- `model_prompt_contract.py`、`source_packet.py`、`benshi_prompting.py` 同步更新 prompt 契约，要求宁缺毋滥。
- `tests/test_chat_orchestrator_runtime.py` 增加/更新回归测试，覆盖无模型轴、部分模型轴、行为轴剪枝和证据绑定。
- `tests/test_final_report_view.py` 更新前端 ViewModel 夹具，避免继续依赖旧固定分类。
- `group_insights_user_facing_shi_profile_2026-05-04.zh-CN.md` 同步更新为新契约。

## 验收口径

- 新 session 的雷达不应再凭空出现固定分类。
- 如果模型只找到一个有效对象，雷达可以只有一个轴或不显示雷达。
- 所有可点击 `shi` 成分都应能回到 QQ 原文证据。
- 行为现象可以显示为群聊行为观察，但不能冒充 `shi` 成分。

## 2026-05-06 实测记录

- 回归测试：`tests/test_chat_orchestrator_runtime.py tests/test_final_report_view.py`，结果 `50 passed`。
- 真实 session：`live_e41d116a69d5c6`，run `x3c_group_757773326_run_20260417_210641_orch`。
- 实测输出 5 个 `shi_type_profile` 轴：消费反差、硬件嘴硬、跑分作弊、超频功耗、自研续命。
- 自检结果：未出现“管人/八卦”“图片配文玩梗”“复读”“接球”“转人工”“客服腔”等错误轴；所有 `signals` 均能绑定到 `evidence_messages` 中的 QQ 原文。
