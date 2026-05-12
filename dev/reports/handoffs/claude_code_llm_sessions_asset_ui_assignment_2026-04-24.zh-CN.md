# Claude Code `LLM Sessions` Multi-Asset UI 任务入口

> 日期：2026-04-24  
> 目标受众：Claude Code  
> 本文是本轮唯一入口。请先读完本文列出的强制文档，再开始改 UI。  
> 当前负责人分工：CC 负责 `LLM Sessions` 前端/UI；Codex 负责 backend/runtime 与验收。

## 1. 这轮要解决什么

用户已经确认：

- LLM Sessions 基础 UI 初步可用。
- Mock session 可以实时自动打开并流式显示 token。
- `Failed to fetch` 的瞬时误报已由 Codex 修掉。
- 后端已经能模拟多 asset 输入：image / file / speech / sticker / missing image。

这轮 CC 的目标是：

- 把 `LLM Sessions` 的多资产聊天记录显示补成真正可读的 AI 对话 UI。
- 保持 ChatGPT/OpenWebUI 风格的主 transcript 阅读流。
- 让用户能清楚看到传给模型的 chat packet 中有哪些消息、哪些 asset、哪些 asset 可用或缺失。
- 不要把页面做回 inspector / console / 卡片墙。

## 2. 必须先读的文档

不要只读当前文件。请按这个顺序读：

### 项目与 review-editor 背景

1. `dev/reports/handoffs/claude_code_project_handoff_2026-04-23.zh-CN.md`
2. `dev/reports/handoffs/review_editor_technical_index_2026-04-23.zh-CN.md`
3. `dev/reports/handoffs/review_editor_current_features_and_style_2026-04-23.zh-CN.md`

### LLM Sessions 总体接口与并行边界

4. `dev/reports/handoffs/llm_sessions_backend_frontend_map_2026-04-23.zh-CN.md`
5. `dev/reports/handoffs/claude_code_llm_sessions_ui_handoff_2026-04-23.zh-CN.md`
6. `dev/reports/handoffs/claude_code_llm_sessions_ab_ui_assignment_2026-04-23.zh-CN.md`
7. `dev/reports/handoffs/llm_sessions_parallel_work_boundary_2026-04-23.zh-CN.md`

### Codex 最近已经做完的修复与新增能力

8. `dev/reports/handoffs/llm_sessions_realtime_stream_fix_2026-04-24.zh-CN.md`
9. `dev/reports/handoffs/llm_sessions_multi_asset_mock_probe_2026-04-24.zh-CN.md`

### 需求复盘和 UI 方法

10. `dev/reports/analysis/reference/methods/orch_session_baseline_reconstruction_2026-04-23.zh-CN.md`
11. `dev/reports/analysis/reference/methods/cc_llm_sessions_delta_inventory_2026-04-23.zh-CN.md`
12. `dev/reports/analysis/reference/methods/cc_llm_sessions_functioning_review_2026-04-23.zh-CN.md`
13. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_reference_method.zh-CN.md`
14. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round1_findings.zh-CN.md`
15. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round2_findings.zh-CN.md`
16. `dev/reports/analysis/reference/methods/review_editor_llm_sessions_ui_round3_findings.zh-CN.md`

## 3. Codex 最近做了什么

这些不是待办，已经做完。不要重复实现，也不要误删。

### 实时流事件修复

文件：

- `src/qq_data_analysis/llm_session_service.py`

修复：

- active subscriber 现在收到的是 `_build_stream_event(...)` 后的前端协议事件，而不是原始 `events.jsonl`。
- SSE 事件名已可被前端识别：
  - `message`
  - `message.delta`
  - `response.completed`

### Failed Fetch 瞬时误报修复

文件：

- `apps/review-editor/src/App.vue`

修复：

- `fetchLlmSessions()` 连续失败达到阈值后才显示红条。
- live stream `onError` 不再把短暂断线直接升级成全局错误。
- 请不要把每一次 background polling 失败重新变成红条。

### Mock session 可调慢

文件：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `scripts/start_mock_llm_session.py`

新增：

- `delayScale` / `mockDelayScale`
- CLI: `--delay-scale`

用途：

- 前端视觉验收时拉慢事件流。

### Multi-asset mock 场景

文件：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `scripts/start_mock_llm_session.py`
- `tests/test_llm_session_service.py`

新增：

- `assetScenario` / `mockAssetScenario`
- CLI: `--asset-scenario multi_asset`

Mock 数据里会出现：

- image: `mock_ui_regression.png`, `available`
- speech: `mock_voice.amr`, `metadata_only`
- file: `mock_logs.zip`, `available`
- sticker: `mock_sticker.gif`, `remote_url_only`
- missing image: `mock_missing_context.jpg`, `missing_after_napcat`

已验证：

- `mock_2fc1243a9b7d2c`: completed, `events=14`, `packets=9`, `chatMessages=15`
- `asset_summary.total=5`
- `asset_summary.available=4`
- `asset_summary.missing=1`

## 4. 当前前端缺口

当前 `apps/review-editor/src/components/LlmSessionPage.vue` 主要显示：

- user / assistant 文本。
- tool call/result 摘要与 `details`。
- prompt / packet 摘要。
- system 折叠事件。

当前缺口：

- `message.jsonPreview` 没有在当前主 UI 中暴露为可读 raw packet。
- `chat_packet.built.jsonPreview.renderable_assets` 没有被转成附件卡片。
- `chat_packet.built.jsonPreview.missing_assets` 没有被转成 missing asset pill。
- `session.request_created.jsonPreview.inputPacket.messages[*].segments` / `asset_refs` 没有在消息级显示。
- 用户看不到“到底传给模型的聊天记录里有哪些 asset”。

这就是本轮要补的 UI 缺口。

## 5. 允许改动范围

优先改：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`
- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/App.test.ts`

允许新增：

- `apps/review-editor/src/components/LlmSessionAsset*.vue`
- `apps/review-editor/src/components/LlmSessionPacket*.vue`
- 与 LLM Sessions 相关的测试/fixtures
- 本轮 findings / handoff 文档

可以只读参考，原则上不要改：

- `apps/review-editor/src/components/MessageBubble.vue`
- `apps/review-editor/src/components/MessageAssetViewer.vue`
- `apps/review-editor/src/components/MessageList.vue`

如果确实要复用或调整上述 review 页面组件，必须说明对 Review 主页面的影响，并补对应回归。

禁止改：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `src/qq_data_analysis/review_service.py`
- session backend / runtime / orchestrator 代码

如果你发现 backend 字段不够，只能写成 `backend gap`，不要自行补 backend。

## 6. UI 具体要求

### Chat packet 消息展示

- 短消息直接展示全文。
- 长消息默认折叠成独立卡片，可以展开查看完整内容。
- 一条消息内的 `segments` 应保留顺序语义，不要把 text 和 asset 完全拆散成无关列表。
- `inputPacket.messages[*].asset_refs` / `segments[*]` 要能让用户看见。

### Asset 展示

必须支持这些状态：

- `available`
- `metadata_only`
- `remote_url_only`
- `missing_after_napcat`
- `missing`

必须支持这些类型：

- `image`
- `file`
- `speech`
- `sticker`
- 未知类型 fallback

视觉要求：

- image 用紧凑缩略图或 media card。
- file / speech / sticker 用附件 pill 或小卡。
- missing asset 要明显但不能刺眼，标注为 boundary-only / missing，不要像成功证据一样展示。
- 多 asset 不要把 transcript 撑成卡片墙，应保持 ChatGPT/OpenWebUI 风格的阅读流。

### Tool result 展示

- `tool.completed` 的 `assets` 与 `derived_hints` 应可追进去。
- 摘要层只显示关键计数/名称。
- 展开层显示结构化 payload 或 asset list。

### Raw payload 展示

- `jsonPreview` 要有可展开入口。
- 默认不要展开大 JSON。
- 展开后要可读，不要挤压主 transcript。

## 7. 本地验证命令

后端服务如果没在跑，用 Windows `.venv`：

```powershell
.\.venv\Scripts\python.exe scripts\run_review_editor_server.py --host 127.0.0.1 --port 43127
```

触发慢速多资产 mock：

```powershell
.\.venv\Scripts\python.exe scripts\start_mock_llm_session.py --chat-name "MULTI ASSET UI PROBE" --run-id mock_asset_ui_probe_20260424 --candidate-id candidate_asset_ui_probe --chat-id asset_probe_chat --asset-scenario multi_asset --delay-scale 6
```

预期：

- LLM Sessions 页自动出现新 session。
- 新 session 自动选中并开始流式显示。
- transcript 中能看到 chat packet / prompt / tool / token。
- chat packet 或消息卡里能看到 image/file/speech/sticker/missing image。
- missing image 明确表现为边界/缺失，不混成可用证据。

## 8. 验收标准

### 必须满足

- 不破坏实时 token 流。
- 不恢复 `Failed to fetch` 短暂红条循环。
- 不破坏 registry 新 session 自动出现和自动切入。
- 多资产 mock 中 5 个 asset 至少都能在 UI 中被发现。
- `jsonPreview` 能被展开查看。
- 长 packet / 长消息默认折叠。
- 视觉上保持会话 UI，不是控制台卡片墙。

### 建议补测试

- `App.test.ts` 或组件测试覆盖：
  - chat packet 中 asset refs 可渲染。
  - missing asset 有单独状态。
  - `jsonPreview` 有展开入口。
  - 实时 stream event 仍能更新 assistant token。

### 回归命令

优先跑：

```powershell
npx vue-tsc --noEmit
npm run test
```

如果环境允许，再跑：

```powershell
npm run build
```

## 9. 交付物

完成后请输出：

- 改了哪些文件。
- 如何触发 multi-asset mock 验证。
- 5 个 asset 在 UI 中分别如何显示。
- 是否发现 backend gap。
- 测试/类型检查结果。

完成后由 Codex 做验收，不要自行改 backend 补洞。
