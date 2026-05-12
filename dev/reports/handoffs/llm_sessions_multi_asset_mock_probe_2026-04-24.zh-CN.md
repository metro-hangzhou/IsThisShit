# LLM Sessions Multi-Asset Mock Probe

Date: 2026-04-24

## CC 本轮 UI 入口

Claude Code 继续处理 UI 时，应优先从这份任务单进入：

- `dev/reports/handoffs/claude_code_llm_sessions_asset_ui_assignment_2026-04-24.zh-CN.md`

## 背景

本轮目标是在接入真实 review/orch 数据前，先用本地 mock 验证 LLM Session 流式链路对多资产消息的承载能力。

## 后端改动

- `LlmSessionManager.start_mock_session(...)` 新增 `asset_scenario` 参数。
- `/api/review/llm/session/mock-start` 接收 `assetScenario` / `mockAssetScenario`。
- `scripts/start_mock_llm_session.py` 新增：
  - `--asset-scenario multi_asset`
  - `--delay-scale <float>`

## `multi_asset` 场景内容

Mock session 会在 `session.request_created` / `chat_packet.built` / `prompt.built` / `tool.completed` / token stream / `result.json` 中注入结构化资产数据：

- image: `mock_ui_regression.png`, `available`, 带 data URI SVG 预览占位。
- speech: `mock_voice.amr`, `metadata_only`。
- file: `mock_logs.zip`, `available`。
- sticker: `mock_sticker.gif`, `remote_url_only`。
- missing image: `mock_missing_context.jpg`, `missing_after_napcat`。

## 目前 UI 观察点

当前 `LlmSessionPage.vue` 只渲染：

- user / assistant 文本。
- tool call/result 的摘要与 `details`。
- prompt / packet 摘要。
- system 折叠事件。

当前页面没有专门渲染 `jsonPreview`，也没有专门渲染 asset card / image preview。也就是说，后端已经能把多资产结构放进 session packet，但如果 UI 中只能看到资产数量或 derived hints，看不到附件卡片/图片预览，这是前端展示层缺口，不是流式传输缺口。

## 本地触发命令

```powershell
.\.venv\Scripts\python.exe scripts\start_mock_llm_session.py --chat-name "MULTI ASSET STREAM PROBE" --run-id mock_asset_probe_20260424 --candidate-id candidate_asset_probe --chat-id asset_probe_chat --asset-scenario multi_asset --delay-scale 4
```

## 本轮验证记录

- `mock_2fc1243a9b7d2c`: completed, `events=14`, `packets=9`, `chatMessages=15`。
- `chat_packet.built.jsonPreview.asset_summary`: `total=5`, `available=4`, `missing=1`, `types=file/image/speech/sticker`。
- `tool.completed.details` 已包含五条可见资产提示：
  - `asset image available: mock_ui_regression.png`
  - `asset speech metadata only: mock_voice.amr`
  - `asset file available: mock_logs.zip`
  - `asset sticker remote only: mock_sticker.gif`
  - `asset missing boundary: mock_missing_context.jpg`
- `mock_092070055b35c8`: slow visual probe, 用于前端自动打开和流式观察。

## 给 CC 的 UI 提示

如果验收时多资产信息只出现在摘要/折叠文本，而没有 ChatGPT/OpenWebUI 风格的附件卡片，请优先改 `apps/review-editor/src/components/LlmSessionPage.vue`：

- 对 `message.jsonPreview` 提供可展开 raw packet view。
- 从 `session.request_created` 和 `chat_packet.built` 的 `inputPacket.messages[*].segments` / `asset_refs` / `renderable_assets` / `missing_assets` 解析 asset card。
- 对 image 使用缩略图卡片；对 file/speech/sticker/missing 使用紧凑附件 pill。
- 长聊天记录默认折叠，短消息直接全文展示。
