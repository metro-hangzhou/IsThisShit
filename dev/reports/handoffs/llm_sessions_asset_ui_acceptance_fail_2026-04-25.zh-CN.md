# LLM Sessions Asset UI 验收不通过记录

Date: 2026-04-25

## 验收结论

Claude Code 本轮完成了 asset chip 与 raw JSON 展开，但没有满足新的验收目标：

- image 需要显示缩略图。
- image 需要可点击打开原图/大图预览。

当前实现只显示彩色 chip，不是实际媒体展示。

## 复现实测 session

本轮 Codex 发起了多资产 mock：

- `mock_3c499f45355d50`
- `chatName`: `ASSET ACCEPTANCE PROBE`
- `assetScenario`: `multi_asset`

API detail 确认：

- `asset_summary.total = 5`
- `asset_summary.available = 4`
- `asset_summary.missing = 1`
- types: `file`, `image`, `speech`, `sticker`

## 具体问题

### 1. 前端只渲染 chip

当前 `apps/review-editor/src/components/LlmSessionPage.vue` 中：

- `parseRenderableAssets(entry.message)` 只从 `jsonPreview.renderable_assets` 读取。
- template 只渲染 `.asset-chip`。
- 没有 `<img>`。
- 没有 preview modal / lightbox。
- 没有 click / keyboard open handler。

### 2. 后端 mock 的 URL 没在 UI 当前读取位置

当前 mock 的 image preview URL 存在于：

- `chat_packet.built.jsonPreview.messages[0].segments[1].asset_url`

但当前 UI 读取的是：

- `chat_packet.built.jsonPreview.renderable_assets`

而 `renderable_assets` 中的 image 只有：

```json
{
  "asset_id": "asset_img_001",
  "asset_type": "image",
  "file_name": "mock_ui_regression.png",
  "status": "available",
  "role": "direct_evidence"
}
```

因此 CC 需要在前端做 asset merge：

- 以 `file_name` / `asset_id` 为 key。
- 将 `renderable_assets`、`missing_assets` 与 `messages[*].segments[*]` 合并。
- 从 segment 中补齐 `asset_url` / `width` / `height` / `summary` 等字段。

如果 CC 认为这应该由后端补齐，也可以标为 backend gap；但前端已经有足够数据从 `messages[*].segments` 合并出 image preview。

## 必须补齐的 UI 行为

### Image

- `available` image 必须显示实际缩略图。
- 如果存在 `asset_url`，直接用该 URL 作为 thumbnail source。
- 点击缩略图打开大图预览。
- 支持键盘 Enter / Space 打开。
- 大图预览需要能关闭。
- 不要把 data URI / URL 文本裸露在 transcript 中。

### Non-image assets

- file / speech / sticker 可继续用 pill 或小卡。
- sticker 如果有可用 `asset_url`，可以先按附件处理；如要显示 GIF preview，需保持不破坏布局。
- `metadata_only` / `remote_url_only` / `missing_after_napcat` 必须明确显示状态。

### Missing image

- 不显示 broken image。
- 用 missing / boundary-only 小卡或 pill。
- 不要让 missing asset 看起来像直接证据。

## 建议实现位置

优先仍在：

- `apps/review-editor/src/components/LlmSessionPage.vue`

可新增局部组件：

- `apps/review-editor/src/components/LlmSessionAssetPreview.vue`
- `apps/review-editor/src/components/LlmSessionAssetLightbox.vue`

不要改：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `src/qq_data_analysis/review_service.py`

## 验收要求

完成后用这条命令触发：

```powershell
.\.venv\Scripts\python.exe scripts\start_mock_llm_session.py --chat-name "ASSET THUMBNAIL ACCEPTANCE" --run-id mock_asset_thumbnail_acceptance_20260425 --candidate-id candidate_asset_thumbnail_acceptance --chat-id asset_acceptance_chat --asset-scenario multi_asset --delay-scale 4
```

必须确认：

- `mock_ui_regression.png` 在 Packet 展开层显示缩略图。
- 点击 `mock_ui_regression.png` 后能打开大图预览。
- 大图预览能关闭。
- `mock_missing_context.jpg` 显示 missing/boundary-only 状态，不显示 broken image。
- raw JSON 展开仍保留。
- 实时 token 流不受影响。
