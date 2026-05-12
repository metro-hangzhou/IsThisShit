# Claude Code `LLM Sessions` Functioning 审查

> 日期：2026-04-23  
> 目的：用“原计划 vs 当前 backend vs 当前 UI vs 真实 session artifact”四方对照，审当前实现到底符不符合 orch session 预期。

## 1. 审查方法
本审查不只看 UI，也不只看代码。判断依据来自四类事实：

1. 原始目标基线  
2. 当前 backend / API / types  
3. 当前前端显示层  
4. 真实 session artifact

特别使用了两类真实 session：
- live：
  - `state/llm_sessions/live_32bbc7776ce6c8`
- mock：
  - `state/llm_sessions/mock_*`

## 2. 总判断
当前 `LLM Sessions` 的状态可以概括成一句话：

**它已经是一个真实可运行的 orch session 观察面，但仍不是完整的 orch session 控制台。**

更细一点说：

- runtime / persistence / stream / materialize 主链已经通
- UI 也已经不再是纯 demo 壳
- 但 session 的关键可操作性与可观察性仍缺块
- 当前最大的偏差不是“完全没做成”，而是：
  - UI 收敛快于功能暴露
  - 聊天产品化快于 orch observability 闭环

## 3. 能力矩阵

| 能力 | 预期 | 当前 backend | 当前 UI | 结论 |
|---|---|---|---|---|
| session 持久化 | 每个 session 有稳定 artifact，可离线回看 | 已有 `state/llm_sessions/*`、manifest/status/events | detail 可回放 completed session | 已实现 |
| session list/detail | editor 可加载 session summary/detail | 已实现 | 已实现 | 已实现 |
| registry 自动发现 | 外部新 session 出现时无需重启 editor | 已有 registry stream | `App.vue` 已自动 upsert + auto select | 已实现 |
| per-session stream | active session 可持续接收增量事件 | 已有 `/stream` SSE | `App.vue` 已 merge patch/message/chunk | 已实现 |
| mock/live 同协议 | mock 与真实 orch session 走同一前端主链 | 基本成立 | 基本成立 | 已实现，但只证明协议一致，不证明能力等价 |
| prompt 可见性 | 能看到 prompt，并能区分 prompt 与别的上下文块 | backend 已有 `llm.prompt_built` / `prompt.built` | UI 只把它吞进 `context` 折叠类 | 部分实现 |
| chat packet 可见性 | 能看到 packet，并能阅读缩略/展开细节 | backend 已有 `chat_packet.prepared/built` | UI 合并成 `context` 折叠类 | 部分实现 |
| tool call/result 可见性 | 能看到 tool 调用、结果、摘要与细节 | backend 已有 `tool.requested/completed/failed` 和 details/jsonPreview | UI 只保留极轻摘要行 | 部分实现 |
| token 流式输出 | assistant 内容实时增长 | live session 已有 `session.stream_chunk` 12733 条 | UI 已把 assistant 内容原位合并显示 | 已实现 |
| reasoning 可见性 | reasoning 与 content 分层显示 | backend 有 reasoning lane | UI 有 `Thinking` 折叠块 | 已实现 |
| orch phase/mode 可见性 | 能看出当前在 context/tooling/judge/materialize 哪个阶段 | backend 有 `phase` / `sessionPatch` | UI 几乎不显示 phase | backend 已有，UI 未暴露 |
| evidence/tool observation 可见性 | 能看出 evidence gap / tool observation 状态 | detail 有 `evidenceGapCount` / `toolObservationCount` | UI 不展示 | backend 已有，UI 未暴露 |
| stop/retry 控制 | session 可停、可重试 | backend 有 `stop_session` / `retry_session` | UI 无入口 | backend 已有，UI 未暴露 |
| continue 输入 | active session 可继续输入下一轮 | 未见 `/session/:id/input` | composer 占位文案暗示可继续，但行为仍是新建 session | 未实现，且 UI 语义误导 |
| replay 控制 | 已有 session 可 replay/reopen 更强回放 | backend 只有 retry / replay-like stream rebuild，未形成正式用户面 | UI 无入口 | 未实现为正式能力 |
| materialized review run | live session 完成后可桥接到 review run | live session 已真实生成 overlay manifest | UI 无显式入口 | backend 已有，UI 未暴露 |
| live review source | review 侧可直接消费 live run 产物 | backend 侧已有 materialization | UI 未形成 live runs source | 未闭环 |

## 4. 真实 live session 给出的结论
真实 session `live_32bbc7776ce6c8` 是当前最关键的证据。

它证明了这些事情不是 mock：

### 已证实
- 真实 orch session 已能启动并完成
- 真实 orch loop 已跑出多轮：
  - `loop.context_built`
  - `loop.tool_requests_planned`
  - `tool.requested/completed`
- prompt 已真实构建：
  - `llm.prompt_built`
  - `prompt.built`
- token 已真实流出：
  - `llm.stream_chunk`
  - `session.stream_chunk`
- 结果已真实 materialize：
  - `session.materialize_started`
  - `session.materialized_review_run`
  - overlay manifest 已落盘

### 这条 live session 同时说明
当前 backend 已经明显超过“纯 UI mock demo”阶段。  
也就是说，后续问题的中心不再是“session 真不真”，而是：

- UI 是否把这些真实能力正确暴露出来  
- 这些能力是否还缺关键控制面

## 5. 当前最重要的偏差

### A. UI 已经开始像聊天产品，但 observability 被压过头
这是当前最大偏差。

backend 里已经有：
- prompt
- packet
- tool payload
- phase
- evidence counts
- materialized review run

但当前前端把大量工程语义压成了：
- tool 摘要行
- context 折叠块
- assistant prose

这让页面更像聊天产品，但反而削弱了它作为 orch session console 的价值。

### B. composer 存在语义误导
当前 `LlmSessionPage.vue` 会根据 `activeSessionId` 把 placeholder 改成：
- `继续输入指令…`

但 `@start-session` 最终仍调用 `App.vue` 的 `startLiveLlmSession()`，而这条链当前只会：
- `POST /api/review/llm/session`
- 创建新的 session

也就是说：

**UI 暗示“继续当前 session”，实际行为仍是“新建 session”。**

这是比视觉问题更优先的语义错误。

### C. control plane 没有真正上屏
目前 stop/retry 明显只存在于 backend。

这导致当前 session 页面更像：
- 看板

而不像：
- 可操作的 runtime surface

### D. review bridge 只到了一半
当前 real live session 已生成：
- `materialized_review_run_id`
- `materialized_review_run_label`
- `review_packets_overlay_manifest.json`

但用户在 UI 里看不到：
- 它 materialize 成了哪个 run
- 能不能立即跳去 review
- 当前 session 是否已经进入“可审状态”

这条链缺的不是 backend，而是前端 surface。

## 6. 当前是否符合我们对 orch session 的期望

### 符合的部分
- session 不是假壳，真实 orch 已跑通
- mock 和 live 已能共用主链
- packet / message / chunk / registry / persistence 主结构正确
- materialize review 这条后链真实存在

### 不符合的部分
- session 还不够“可操作”
- session 还不够“可观察”
- UI 对 orch engineering trace 的暴露度偏低
- continue/replay/control plane 仍未真正形成产品能力
- materialized review run 仍未成为用户可直接利用的 editor surface

所以当前最准确的结论是：

**它已经符合“orch session v0 可观察原型”的期望，但还不符合“orch session v1 正式工作台”的期望。**

## 7. 对 Claude Code 这轮工作的评价

### 正面评价
- 它没有把 backend 主链搞坏
- 它延续了 capture/diff/findings 的方法
- 它把 UI 从“控制台墙”拉回了 transcript-first

### 负面评价
- 它推进的是 UI 收敛，不是 session capability 闭环
- 它让页面更像聊天产品，但没有同步把 orch observability 收好
- 它留下了一个明确的语义问题：
  - composer 的“继续输入”是假语义

## 8. 下一步技术路线建议
当前最合理的顺序不是继续只修 UI，而是按这三步走：

### Step 1. 先修 session 语义错误
- 把“继续输入”改成真实 continue，或者移除该语义
- 把 stop / retry 至少上屏
- 把 materialized review run 上屏

### Step 2. 恢复 orch observability
- prompt 要有独立可读面
- packet 要恢复明确语义
- tool details / payload 不能只剩摘要
- phase / evidence gap / tool observation 需要弱暴露

### Step 3. 再继续 UI 精修
- rail / transcript / composer 的视觉收敛
- assistant / system / tool / packet 的层级微调
- 更像 ChatGPT / Claude Code，但不牺牲工程可读性

## 9. 当前环境下的验证边界
本次审查额外确认了一个现实限制：

- 在当前 Linux/WSL 环境下，`apps/review-editor` 的 `vitest` 与 `vite build` 因 `rolldown` native binding 缺失而失败

因此本轮 functioning 审查主要依赖：
- 代码阅读
- session artifact
- 已有 capture/diff/findings

这不会影响“能力面是否存在”的判断，但会影响：
- 本地即时运行态回归
- UI 构建产物级验证

后续若要做最终验收，应补一轮 Windows 环境下的：
- `npm test`
- `npm run build`
- `npm run tauri:build`
