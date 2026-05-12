# Orch Session 基线重建

> 日期：2026-04-23  
> 目的：把“我们之前对 orch session 想做什么、做到哪、接下来技术路线是什么”重新写清楚，避免继续凭记忆推进。

## 1. 这份基线怎么重建出来
本文件基于三类事实来源重建：

1. 仓库内现有 handoff / map / findings 文档  
2. 当前 `review-editor` / session backend / orch runtime 代码  
3. 已落地的真实 session artifact（`state/llm_sessions/*`）

因此它不是新的拍脑袋设计，而是对现有目标与现状的再整理。

## 2. Orch Session 的真实定位
`LLM Sessions` 从来不只是“另一个聊天页面”。它的正确定位是：

- `chat_orchestrator` 的**实时观察面**
- `review-editor` 里的**live orchestration console**
- 从 orch runtime 到人工审核包之间的**桥接层**

换句话说，session 的核心价值不是“像聊天产品”，而是同时满足这三件事：

1. 像聊天产品一样可读  
2. 像工程控制台一样可观察  
3. 能把 live 结果继续送进 review 流

## 3. 之前已经明确过的目标能力

### A. Runtime / artifact 层
session 后端应是结构化 artifact，不是 CLI stdout 录像。

已经明确的目标形态：
- session root 固定在 `state/llm_sessions/`
- 每个 session 有 manifest / status / events.jsonl
- 前端消费的是结构化：
  - `summary`
  - `detail`
  - `packet`
  - `chatMessage`
  - `tokenChunk`
  - `sessionPatch`
- mock session 与真实 orch session 共享同一套协议

### B. 观察能力层
session 页面本来就应该把下面这些东西暴露出来：
- prompt
- chat packet
- tool call / tool result
- token 流
- reasoning / thinking
- orch phase / mode / evidence acquisition 痕迹

这里的关键点不是“都默认展开”，而是：
- 默认阅读要轻
- 但工程痕迹必须能追进去

### C. Editor 联动层
之前明确想要的是：
- 外部新建 session 时，editor 无需重启即可发现
- registry stream 能把新 session 自动插入左 rail
- active session 可以连 per-session stream 实时刷新
- session 完成后可离线回看

### D. Review 桥接层
session 的终点不只是“看完一段 token 输出”，而是：
- live session 可以 materialize 成 review packets
- materialized run 后续应可进入人工审核入口

这条线是 `orch -> session -> review` 的正式桥，不是 demo。

### E. 控制面
此前 session 规划里，控制面至少包括：
- start
- stop
- retry
- continue
- replay

当前 repo 里并不是全部都已经落地，但这一直是 session 作为“可操作 runtime surface”应有的能力方向。

### F. UI 方向
视觉上一直是双参考路线：

- **ChatGPT Web**
  - 骨架
  - 主列
  - rail / transcript / composer 关系
- **Claude Code / Codex**
  - tool
  - reasoning
  - engineering trace

所以 `LLM Sessions` 的目标从来不是纯 ChatGPT 复刻，而是：
- 主区像聊天产品
- 工程痕迹像 agent console

## 4. 在当前 repo 里，哪些已经做到了
截至当前代码与 artifact，下面这些已经成立：

### 已成立
- session 持久化根目录存在：`state/llm_sessions/`
- summary / detail / registry / per-session SSE 已通
- mock 与 live 走同一前端主链
- `App.vue` 已实现 sessions 页面进入、自动刷新、registry 自动切换、stream 合并
- 真实 live session 已存在：
  - `live_32bbc7776ce6c8`
- live session 已真实产出：
  - `context.prepared`
  - `chat_packet.prepared/built`
  - `tool.requested/completed`
  - `llm.prompt_built`
  - `prompt.built`
  - `session.stream_chunk`
  - `session.materialized_review_run`
- live session 完成后已生成 `review_packets_overlay_manifest.json`

### 已做但仍偏观察面不足
- transcript 已经从“控制台卡片墙”转成 transcript-first
- assistant / user / thinking / tool / context 现在已能在同一阅读流里显示

## 5. 当前仍没收完的目标

### A. 控制面还没闭环
repo 里当前已见：
- backend 有 `stop_session`
- backend 有 `retry_session`

但当前没有完整落地：
- session continuation 输入 API
- replay / continue 的正式控制流
- 前端 stop / retry / replay 按钮

### B. 观察面还没闭环
backend 已经有很多工程事件，但前端并未完整暴露：
- prompt 仍未形成明确“可读且可展开”的独立阅读面
- packet / tool payload / details 目前被压得过轻
- phase / evidence gap / tool observation 数量并未形成清晰 UI

### C. Review 桥接只完成了一半
backend 已能 materialize review run，但当前前端还没有把：
- materialized review run
- live review run 入口
- review 跳转链

做成真正可用的 editor surface。

### D. “像聊天产品”与“可观察”之间还没找到平衡点
前几轮 UI 优化明显把页面从控制台拉回了聊天产品骨架，但也带来一个风险：
- 工程痕迹被弱化过头

对 orch session 来说，这不是纯视觉问题，而是功能问题。

## 6. 当前最合理的技术路线
接下来不应只围绕“再像一点 ChatGPT”推进。更合理的顺序是：

### 第一层：先把语义不一致的问题修掉
- `continue` 的 UI 语义与真实行为要一致
- materialized review run 要有可见入口
- stop / retry 至少要从 UI 可达

### 第二层：恢复 orch 观察能力
- prompt 与 chat packet 要恢复成明确可追踪的结构
- tool call / result 要有可展开 payload / detail
- phase / evidence acquisition 要有足够弱但真实的暴露

### 第三层：再继续收 UI
- transcript 密度
- rail 结构
- composer 形态
- assistant / system / packet / tool 的层级

也就是说，接下来正确路线不是“UI 先做到完全像 ChatGPT”，而是：

1. session 语义闭环  
2. orch 可观察性闭环  
3. 聊天产品视觉精修

## 7. 这份基线对后续 review 的作用
后续看 Claude Code 的代码和功能时，必须按下面三组维度审：

1. 它是推进了 UI，还是推进了 session capability  
2. 它是推进了 mock demo，还是推进了真实 live orch session  
3. 它是让页面更像聊天产品了，还是也真的让 orch 更可观察了

如果不按这三组维度拆开，后面很容易把“看起来更像 ChatGPT”和“session 更符合 orch 目标”误当成同一件事。
