# 给 Claude Code 的任务：重构 LLM Session / ORCH 调试观察器 UI

日期：2026-04-25

## 必读文档

先读：

1. `dev/reports/handoffs/llm_session_orch_debugger_contract_2026-04-25.zh-CN.md`
2. `dev/reports/handoffs/cc_llm_session_orch_debugger_ui_task_2026-04-25.zh-CN.md`
3. 如需理解 review 页面聊天记录渲染，读 `apps/review-editor/src/components/ForwardRecordViewer.vue`、`apps/review-editor/src/forwardWindow.ts`、`apps/review-editor/src/components/MessageList.vue`。

不要从零设计一个新产品。目标是把现有 LLM Sessions 收敛成一个可用的 ORCH session 调试观察器。

## 你的写入范围

允许改：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
- `apps/review-editor/src/components/LlmStructuredStreamBlock.vue`
- `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`
- `apps/review-editor/src/lib/llmFinalReportParser.ts`
- 如需要，可以新增 `apps/review-editor/src/components/llm-session/*.vue`
- 如需要，可以小改 `apps/review-editor/src/types.ts` 读取新增字段，但不要改 API contract 语义。

禁止改：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- 后端测试、ORCH pipeline、exporter、NapCat 相关代码。

Codex 正在负责后端 contract。你只做前端呈现层。

## 必须修复的问题

### 1. 输入包聊天记录为空

文件：`apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`

`rawMsgToEntry()` 必须读取：

- `content`
- `text_content`
- `textContent`
- `content_preview`
- `contentPreview`

fallback 顺序建议：

```ts
const content = str(
  r.content ?? r.text_content ?? r.textContent ?? r.content_preview ?? r.contentPreview,
  "",
).trim();
```

如果只有 `content_preview`，它仍然是模型输入包的人类可读文本，必须显示。

### 2. Segment 媒体字段被丢弃

`normalizeSegments()` 不允许只保留 `{type, token, text}`。至少保留：

- `fileName` / `file_name`
- `path`
- `md5`
- `summary`
- `emojiId` / `emoji_id`
- `emojiPackageId` / `emoji_package_id`
- `extra`
- `assetUrl` / `asset_url` / `url`

目标：输入包展开后的 PCQQ 窗口能复用已有聊天记录 UI 显示图片/文件/语音/贴图；不能因为 adapter 丢字段导致只剩 token。

### 3. 输入包语义不要误标成转发消息

`raw_messages` 类型不是 QQ forward。它是“模型输入聊天片段 / 输入包”。

主卡片文案建议：

- eyebrow: `模型输入包`
- title: `Prepared packet` / `Effective prompt packet`
- summary: `223 条消息 · 16 人 · 8 assets · 6 missing`
- action: `展开聊天片段`

打开独立窗口可以复用 forward window 技术，但窗口标题不能叫“转发消息”。应为：

- `模型输入聊天片段`
- `Prepared packet`
- `Effective prompt packet`

### 4. Final Report 主 UI 改用 finalReportViewModel

后端现在会给：

- `detail.finalReportViewModel`
- `detail.finalReportPayload`
- `detail.finalReport`

主 UI 必须优先使用 `finalReportViewModel`：

- 顶部 hero 卡：显示 `primaryVerdict`、`coreObject`、`coreReason`、`mediaGapSummary`。
- Section：按 `sections[]` 渲染，尊重 `collapsedByDefault`。
- `tone` 控制视觉类型：`model`、`evidence`、`review`、`warning`、`debug`。
- `debug.hiddenByDefault` 的内容只能放 Debug/Raw 折叠区。

`human_report` parser 只能作为 fallback 或 raw report，不能再驱动主 UI。

### 5. 功能字段必须聚合

不要把 100+ 字段逐条铺满页面。

建议规则：

- `model_inference`：按 message_uid / label 聚合，显示 Top 6，剩余计数折叠。
- `evidence_boundary`：优先显示缺口、边界、证据依据，列表超过 6 条折叠。
- `debug`：默认折叠。
- 只有 source quote / 原文片段可以更醒目地直接露出。

### 6. Packet 不要重复渲染

检查 `LlmSessionPage.vue`。如果一个 packet 已经由 `LlmSessionChatPacketCard` 渲染，就不要再继续渲染旧 `packet-block` 的 raw/packet UI。

## UI/UX 标准

整体方向：日常工具，不是炫技大屏。

- 主栏阅读宽度控制在适合长文的范围，避免一整屏横向拉满。
- 默认视图先让人看懂结论和行动点，再让人展开证据和 raw。
- Raw/Debug 永远折叠，且有清楚标签。
- 大列表默认只露代表项和计数。
- 所有可展开区域要有稳定标题、计数、用途，不要只有“字段/条”。
- 支持 emoji 做类型标识，例如 ⚠、🧠、🧾、🖼，但信息不能只靠 emoji。
- 保持当前 ChatGPT/Claude 风格：简洁、低边框、清楚层级、底部 composer 不要被大块 debug 挤压。

## 自测流程

开发阶段必须先用 Vite/Vue dev server 自行打开页面验收，不要默认先打 Tauri 包。顺序如下：

1. 类型检查和单测。
2. 启动 `npm run dev`，打开 LLM Sessions 页面自查真实/模拟 session。
3. 页面验收通过后，再做 `npm run build`。
4. 只有最终交付或用户明确要求桌面包验收时，才做 `npm run tauri:build`。

必须执行并在交付里报告结果：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
npm run dev
npm run build
```

如果需要验证 Tauri release，可先按用户授权关闭旧窗口，但这不是开发阶段默认动作：

```powershell
taskkill /IM review-editor.exe /F
npm run tauri:build
```

真实数据验收建议：

1. 后端使用项目 venv 启动：

```powershell
cd D:\Coding_Project\IsThisShit
.\.venv\Scripts\python.exe scripts\run_review_editor_server.py --host 127.0.0.1 --port 43127
```

2. 打开 LLM Sessions。
3. 选择 `live_6fab58045c3264` 或最新 x3c session。
4. 检查：

- 输入包卡片默认不撑爆页面。
- 展开输入包后能看到 `content_preview` 对应消息文本。
- 如果 sender 只有 `user_xxx`，UI 标注为 alias/去敏。
- 图片 asset 不因 adapter 丢字段而消失。
- Final Report 顶部不是一串折叠字段，而是可读结论卡。
- `口吻层输出`、承载度、证据边界等模型派生内容有清楚类别，不像原文聊天。
- Raw report / Raw JSON / Debug 默认折叠。

## 交付要求

交付时必须说明：

- 修改了哪些文件。
- 哪些问题已修。
- 哪些仍是后端 contract 或数据源问题。
- `vue-tsc`、`vitest`、`npm run dev` 页面验收、`npm run build` 的结果。
- 是否实际打开最新 session 做了人工/截图级验收；如果没有，说明原因。
