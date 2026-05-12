# LLM Session / ORCH 调试观察器 contract 交接

日期：2026-04-25

## 目标

`LLM Sessions` 不是普通聊天页，也不是 raw JSON 查看器。它是 ORCH session 调试观察器，必须让人类在同一页里看懂：

- 本轮 session 为什么启动、对应哪个 review run / candidate / chat。
- 发送给模型的输入包是什么，包括聊天记录、资源、摘要、边界和 prompt。
- ORCH 调用了什么工具、拿到了什么结果、哪些证据缺口仍然存在。
- 模型正在输出什么，流式 JSON 未闭合时也不能把整段 raw JSON 直接摊开成正文。
- 最终报告应该优先呈现“可审结论、核心对象、证据链、复审导航、媒体缺口、调试信息”，而不是把 40+ payload 字段逐项折叠成条。

## 后端 contract

后端入口：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`

前端 API 类型：

- `apps/review-editor/src/types.ts`
- `apps/review-editor/src/api.ts`

当前新增/收紧字段：

- `finalReportPayload`：仍保留结构化 payload，但 raw/heavy 字段会被剔除。
- `finalReportViewModel`：新增，给前端直接渲染 Final Report 主 UI。
- `reviewSurfaceGuidance`：保留人工复审导航字段。
- `inputPacket`：保留 session request 的输入包摘要，最多 `300` 条消息，去掉 raw/heavy 字段。
- `events`：detail 中只返回事件摘要，不再直接返回 `result`、`raw_text` 这类大 payload。

`finalReportViewModel` 结构：

```json
{
  "schemaVersion": "llm_final_report_view_v1",
  "hero": {
    "primaryVerdict": "...",
    "coreObject": "...",
    "coreReason": "...",
    "mediaGapSummary": "...",
    "status": "completed",
    "stopReason": "completed"
  },
  "sections": [
    {
      "id": "verdicts",
      "title": "判定结论",
      "tone": "model",
      "purpose": "...",
      "collapsedByDefault": false,
      "items": [{ "label": "...", "sourceKey": "...", "valueKind": "...", "preview": "..." }],
      "records": [],
      "itemCount": 1,
      "recordCount": 0
    }
  ],
  "debug": {
    "sourcePayloadKeyCount": 46,
    "duplicateAliasMap": {
      "crowd_reaction_items": "reaction_patterns"
    },
    "hiddenByDefault": true
  }
}
```

标准 section 语义：

- `verdicts`：最终判定，默认展开，必须一眼可读。
- `core`：史对象和核心机制，默认展开，解释为什么值得审。
- `evidence`：直接证据与边界，默认展开，避免 raw JSON。
- `inference`：推理链路，可默认折叠。
- `review_surface`：人工复审导航，默认展开，告诉人优先看哪里。
- `reaction`：群体反应，可默认折叠但要能快速理解。
- `media`：媒体与缺口，有 missing 时必须醒目。
- `orch_debug`：编排与模型元信息，默认折叠，只给调试用。

## 前端呈现原则

1. 主阅读区只放“人类需要审阅/判断的内容”。
2. raw JSON、raw report、large events、重复别名字段只能进 Debug/Raw 折叠区。
3. 聊天记录输入包必须默认折叠成 PCQQ/forward 风格摘要卡，展开后复用 review 页面已有的聊天记录 UI。
4. `content_preview` 是输入包消息的可显示文本 fallback；不能只读 `content` / `text_content`。
5. `sender_name` 可能是去敏 alias，如 `user_d83a571bba`。UI 应明确标注 alias/去敏，而不是假装是真实昵称。
6. 图片/语音/文件/贴图的 segment 字段不能在 adapter 中丢掉。至少保留 `fileName`、`path`、`assetUrl`、`extra`。
7. 模型流式输出如果是 JSON，应增量结构化显示已出现字段；不能等完整闭合后才一口气渲染，也不能直接把半截 JSON 当正文。
8. Final Report 不再以 `human_report` 文本 parser 为主；应优先使用 `finalReportViewModel`。
9. 允许使用 emoji 做轻量状态/类型标识，但不要让 emoji 替代真实信息结构。

## 已知问题清单

- `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`
  - `rawMsgToEntry()` 目前未读取 `content_preview`，导致输入包窗口只有 sender/time 没有消息正文。
  - `normalizeSegments()` 只保留 `{type, token, text}`，丢失媒体字段，导致图片/文件不能按 review 页面能力显示。
  - raw input packet 被标成“聊天记录/转发消息”，语义不准，应改成“模型输入包/输入聊天片段”。

- `apps/review-editor/src/components/LlmSessionPage.vue`
  - Packet 可能同时走 `LlmSessionChatPacketCard` 和旧 `packet-block`，造成重复视觉系统。
  - 应只保留一个 canonical packet renderer。

- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
  - 目前同时依赖 `human_report` parser 和 payload 猜字段，导致碎片化。
  - 应改为 `finalReportViewModel` 驱动主 UI，`human_report` 仅做 raw/secondary。

- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
  - 不能把 100+ 功能字段全按一行一卡展示。
  - 应按 category/message/source 聚合，只显示代表项和计数。

## 验收样本

优先使用当前真实 session：

- session id: `live_6fab58045c3264`
- source run: `x3c_group_757773326_run_20260417_210641_orch`
- 关键现象：包含 223 条输入包消息、媒体缺口、Final Report、模型输出 JSON/文本、工具/ORCH 调试事件。

如果当前 review server 已启动，可以用：

```powershell
curl.exe -s http://127.0.0.1:43127/api/review/llm/session/live_6fab58045c3264
```

如果没有启动，按用户要求必须使用项目 venv：

```powershell
.\.venv\Scripts\python.exe scripts\run_review_editor_server.py --host 127.0.0.1 --port 43127
```

