# Claude Code `LLM Sessions` Asset Density UI 任务入口

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 当前分工：CC 负责 `LLM Sessions` 前端/UI；Codex 负责 backend/runtime、资产路径契约与验收。  
> 本文是本轮 UI 调整入口。请先读本文，再按文中列出的文件定位代码。

## 1. 当前用户反馈

用户在真实 session 截图中确认：

- 图片缩略图已经能显示，说明 thumbnail/lightbox 主链路基本成立。
- 但 missing asset 超过 2 个时全部铺开，占据过多 transcript 空间。
- 图片缩略图现在有一层蓝色外框，用户不希望有外框。
- 文件名现在独立占一行，空间浪费；用户希望文件名显示在缩略图右下角。
- 文件名覆盖层应为半透明/半虚化，不要完全遮挡图像。

目标不是重写整个 LLM Sessions 页面，而是收敛 asset 展示密度，让 transcript 更像 ChatGPT/OpenWebUI 的附件展示，而不是 inspector 卡片墙。

## 2. 已知可用真实验收 session

真实 session：

- `live_108278632af28c`
- source run: `x3c_group_757773326_run_20260417_210641_orch`
- candidate: `group_757773326_candidate_001`
- status: `completed`

该 session 的 packet 中：

- `asset_summary.total = 8`
- `asset_summary.available = 2`
- `asset_summary.missing = 6`
- `types = ["image"]`
- 两个 renderable image URL 已由 Codex 实测 `GET 200 image/jpeg`

用户截图中正在看的就是这一类真实 packet。

## 3. Backend contract 状态

Codex 已完成 backend 修复。CC 不需要改 backend。

关键点：

- JSONL 里的 `D:\QQHOT\...` 是导出源机器路径，只能当 provenance，不能作为当前机器 truth。
- 后端现在会优先使用 `export.manifest.json` / `materialization_exported_rel_path` 拼到当前项目本地 corpus bundle。
- 正确本地 bundle 示例：
  - `dev/testdata/local/x3c_group_757773326/assets/images/93120E872394A56E708EA8E33AFDABD6.jpg`
- 前端收到的 image `asset_url` 已经是可 GET 的 review server URL：
  - `http://127.0.0.1:43127/api/review/asset?...`

前端只需要消费这些字段：

- `jsonPreview.renderable_assets[]`
- `jsonPreview.missing_assets[]`
- `asset.asset_type`
- `asset.file_name`
- `asset.status`
- `asset.reason`
- `asset.asset_url` / `asset.assetUrl`
- `asset.exported_rel_path` / `asset.exportedRelPath`

不要用 `source_path` 或旧 JSONL `path` 做图片展示。

## 4. 允许改动范围

优先改：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmSessionAssetLightbox.vue`

如需抽组件，可以新增：

- `apps/review-editor/src/components/LlmSessionAssetStrip.vue`
- `apps/review-editor/src/components/LlmSessionAssetThumb.vue`
- `apps/review-editor/src/components/LlmSessionMissingAssets.vue`

可补测试：

- `apps/review-editor/src/App.test.ts`
- 或已有 LLM session component/composable 测试

禁止改：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/review_service.py`
- `scripts/run_review_editor_server.py`
- 其他 backend/runtime/orch 代码

如果发现字段不够，请写 backend gap，不要自行补 backend。

## 5. 具体 UI 要求

### 5.1 Missing assets 折叠

当前问题：

- `parseMissingAssets(entry.message)` 返回 6 个时，UI 全部渲染成 missing pill，占据大量纵向空间。

要求：

- missing asset 数量 `<= 2`：全部显示。
- missing asset 数量 `> 2`：默认只显示前 2 个。
- 第 3 个位置显示一个紧凑控制，例如：
  - `+4 missing`
  - `show 4 more`
  - `4 more missing assets`
- 点击/展开后再显示剩余 missing assets。
- 折叠控件要局部作用于当前 packet，不要影响其他 packet。
- 展开态必须可再次收起。
- missing 信息仍要保留在 Raw JSON 中，不得丢失。

建议实现：

- 在 `LlmSessionPage.vue` 内用 `ref<Record<string, boolean>>` 或局部 component state 记录每个 packet 的 missing 展开状态。
- key 可用 `entry.key` 或 `entry.message.messageId`。
- 提供 helper：
  - `visibleMissingAssets(entry)`
  - `hiddenMissingCount(entry)`
  - `toggleMissingAssets(entry)`

### 5.2 图片缩略图去外框

当前问题：

- `.asset-thumb` 有蓝色 border/background，像选中态卡片，不像自然附件。

要求：

- 默认状态不要蓝色外框。
- 缩略图本体直接显示，保持圆角即可。
- 背景透明或接近页面背景。
- hover/focus 可以有轻微反馈，但不要一直有蓝色框。
- keyboard focus 仍然必须可见，可用 outline / box-shadow，只在 focus-visible 时出现。

建议 CSS：

- `.asset-thumb` 设为 `position: relative; padding: 0; border: 0; background: transparent;`
- `.asset-thumb__img` 保持固定尺寸与 `object-fit: cover`
- hover 使用轻微 `filter` / `transform`，不要重 shadow
- `:focus-visible` 再显示 accessible outline

### 5.3 文件名覆盖在图片右下角

当前问题：

- `.asset-thumb__name` 在图下方独立成行，占空间。

要求：

- 文件名显示在缩略图右下角。
- 使用半透明/半虚化 overlay。
- overlay 不要挡住主体图像；只占图片底部或右下小块。
- 文本超长时省略号。
- 不要裸露长 URL。

建议 CSS：

- `.asset-thumb__name`：
  - `position: absolute`
  - `right: 0.25rem`
  - `bottom: 0.25rem`
  - `max-width: calc(100% - 0.5rem)`
  - `padding: 0.125rem 0.375rem`
  - `border-radius: 999px`
  - `background: rgba(17, 24, 39, 0.54)`
  - `backdrop-filter: blur(8px)`
  - `color: rgba(255,255,255,0.92)`
  - `font-size: 0.625rem`
  - `text-overflow: ellipsis`

注意：

- 如果项目的 CSS 变量已有更合适的 token，优先用现有 token。
- 不要引入新的依赖。

### 5.4 Non-image assets

本轮用户主要反馈 image/missing 展示。

file / speech / sticker 可以暂时维持 pill，但请确保：

- 不要把 asset 区域撑成卡片墙。
- `metadata_only` / `remote_url_only` / `missing` 状态仍清晰。
- 如果顺手统一为 compact attachment strip，可以做，但不要大改整页布局。

## 6. 当前相关代码定位

文件：

- `apps/review-editor/src/components/LlmSessionPage.vue`

当前相关位置：

- template renderable assets:
  - `parseRenderableAssets(entry.message)`
  - `.asset-row`
  - `.asset-thumb`
  - `.asset-chip`
- missing assets:
  - `parseMissingAssets(entry.message)`
  - `.asset-chip--missing`
- lightbox:
  - `openLightbox(...)`
  - `LlmSessionAssetLightbox.vue`
- helper:
  - `buildSegmentUrlMap(...)`
  - `parseRenderableAssets(...)`
  - `parseMissingAssets(...)`

## 7. 验收清单

必须验证：

- 打开真实 session `live_108278632af28c`。
- Prepared packet 中只默认显示前 2 个 missing asset。
- 有一个紧凑的 `+N missing` / `show N more` 控件。
- 展开后能看到剩余 missing asset，并可收起。
- 两张可用 image 无默认蓝色外框。
- 文件名覆盖在图片右下角，半透明/半虚化，长文件名省略。
- 点击图片仍能打开 lightbox。
- Esc / 点击遮罩仍能关闭 lightbox。
- Raw JSON 展开仍保留。
- 实时 token 流不受影响。

建议命令：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vitest run
npm run tauri:build
```

如果只改 Vue/CSS，也至少跑：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
```

## 8. 给 Codex 的交付摘要格式

完成后请回复：

- 改了哪些文件。
- missing assets 折叠行为如何实现。
- image thumbnail 样式如何变化。
- 是否保留 keyboard/lightbox 行为。
- 跑了哪些验证命令。
- 是否发现 backend gap。

