# TODOs.review-editor-round-016

## P0

- [x] 把高频审阅动作做成主动作带：`下一条待审 / 回到锚点 / 保存 / 资料开关`
- [ ] 把底部 composer 继续收成 QQ 风格的紧凑输入/操作条（2026-04-06：已移除主动作混装，当前剩余的是继续压缩视觉层级与表单感；2026-04-07：已继续把 `ComposerDock` 从“表单壳 + 独立信息卡”压成更扁平的快审条，整合顶部状态、弱化 LLM 卡片感、收口备注/补充入口。当前剩余的是再往“输入区”而不是“审阅面板”方向逼近。）
- [ ] 修 forward 子窗口的 optimistic success / 静默失败问题
- [ ] 补齐 forward 资源链，复用 richer asset contract

## P1

- [ ] 让右栏更像 QQ 成员栏而不是自定义信息面板（2026-04-06：已去掉大段资料卡/胶囊堆叠，当前剩余的是继续压缩成更接近原生 QQ 成员列表的视觉语法；2026-04-07：已把右栏头部的“资料/审阅 + 统计气泡条”继续压成标题/时间/概览一体化头区，成员区标题改成更轻的“相关成员”，并把 item 内待审状态收进更像列表元信息的一行。）
- [ ] 继续压缩会话栏，使其更像最近聊天（2026-04-06：已去掉明显任务卡/状态 pill 语法，当前剩余的是继续逼近 QQ 最近聊天列表的节奏和信息比例；2026-04-07：已把左栏项里的 `打标任务` 语义从装配层和视图层一起抽掉，改成“标题 / 预览 / 细元信息 / 未读式待审信号”的节奏；当前剩余的是进一步减弱 review 元信息密度。）
- [ ] 让聊天头部优先承载状态和主动作，而不是 generic icon（2026-04-06：主动作已进头部黄金区，窗口右上角三按钮已统一成同一套笔画/hover 语法，当前剩余的是继续去产品后台感；2026-04-07：已把头部从“统计块 + workflow pills”压成更轻的消息/标记/待审概览和状态行，剩余的是继续向更原生的聊天头密度靠拢。）
- [ ] 统一 image/video/file/speech 在主聊天与 forward 中的预览行为（2026-04-06：已先统一主聊天 bubble / forward bubble / 内嵌卡片的圆角语言，并补上 forward 子窗底部圆角链路；同时移除了窗体外层透明留白并给 frame 增加圆角裁剪，避免“视觉阴影已消失但方形透明命中区仍可点击”的假圆角；当前剩余的是资源预览交互和表现完全一致）
- [ ] 收口 forward sender identity / avatar 解析（2026-04-07：这条线已经从 viewer 猜测推进到“上游 schema + review_service + viewer 降级策略”三层。`src/qq_data_core/normalize.py` 与 `src/qq_data_process/adapters/exporter_jsonl.py` 会保留 `raw_sender_id / raw_sender_name / avatar_url / timestamp_iso`；`src/qq_data_analysis/review_service.py` 现在会先吃当前候选窗口唯一名字，再吃整条 run 的 chat 内唯一名字，为旧 run 回填 `raw_sender_id / avatar_url`；viewer 则不再把一个被多个不同名字复用的假 `sender_id` 渲染成默认企鹅，而是退回名字 fallback。新增 `scripts/inspect_forward_payload.py` 和 `scripts/inspect_review_candidate_forward.py` 可分别检查 exporter 原始 payload 与 review_service 最终输出。当前 `amd_712` 实测 `Jelly Terra` 已恢复真实头像，而 `gjz010 / 🍥HachiHikari` 因 run 内无真相支撑，仍只能走安全 fallback；若要全面恢复仍需用新 schema 重新导出/重建 review 数据。新增确认：主窗消息与右栏审阅成员已优先吃后端下发的本地 `avatarUrl`；QQ 本地头像缓存 `SNS/Com.Tencent.PersonalCard/<qqid>/*` 只是按 QQ 号分目录的 JPEG 文件，不带名字索引，所以只靠名字无法从缓存反查真实 QQ。）
- [ ] 后续研究：对比 NapCat 原生 forward raw 结构与 fast plugin slim payload 的头像线索透传（2026-04-07：已完成 live probe，但暂缓实现。好友 `1507833383` 的样本表明：原生 `get_friend_msg_history(parse_mult_msg=true)` 和 `get_forward_msg` 展开的 inner forward messages 本身就会把多个真实发言人压成共享的 `user_id=1094950020 / group_id=284840486` synthetic sentinel；因此“恢复真实 QQ 号”不能指望现有 public parsed tree。另一方面，NapCat 源码里 `contentHead.forward.avatar` / `unknownBase64` 确实存在，fake forward builder 也会填这两个字段，而 fast plugin `slimRawMessage()` 当前并不透传它们。高概率结论是：QQ 客户端能在缓存未失效时显示部分 forward 头像，依赖的是 raw forward head 的头像线索，而不是 parsed child 里的 `1094950020`。这条线后续若继续做，优先方向是抓/透传 raw forward head，而不是继续在 viewer/review_service 层猜 sender。新增脚本：`scripts/probe_napcat_forward_live.ps1`。）
- [ ] 修 runtime bridge failure cache

## P2

- [ ] 处理 forward localStorage transport 的配额/生命周期风险
- [ ] 修 forward 日期分组按“每条消息时间”而不是“每天”
- [ ] 设计 human feedback -> analyzer feedback 的下一阶段接口边界

## Session Handoff

- [ ] Keep [SESSION_HANDOFF_MASTER_20260406.md](/mnt/d/Coding_Project/IsThisShit/state/program_runs/shi_analyzer/round_016/SESSION_HANDOFF_MASTER_20260406.md) synchronized with future review-editor and analysis-loop changes
