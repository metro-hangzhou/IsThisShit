# Claude Code `LLM Sessions` PCQQ Chat Record UI 任务入口

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 分工边界：CC 负责 `LLM Sessions` 前端/UI 移植与视觉整理；Codex 已处理 backend detail 体量爆炸和基础稳定性。  
> 重要约束：不要重造聊天记录 UI。review 页已经有 PCQQ-like 消息气泡、forward 卡片、独立窗口 viewer，请直接复用/移植。

## 1. 当前用户反馈

用户在 `LLM Sessions` 页面看到：

- 聊天记录/模型输入上下文区域直接变成大段 JSON 或类 JSON 文本。
- 这不符合预期。用户希望聊天记录默认折叠成类似 QQ/PCQQ 转发聊天记录的卡片。
- 折叠态只显示简要信息：消息数、发送者数、预览行、资源/缺失资源摘要。
- 点击后打开独立窗口，窗口中用 review 页已经实现过的 PCQQ-like 消息列表显示完整聊天记录。
- 如果 Tauri 子窗口打开失败，再 fallback 到页面内弹窗。
- 模型输出里的功能字段/派生字段，例如 `口吻层输出`、`baseline_role=[...]`、`shi_delta=[...]`、`bearingness=[...]`，不能继续像普通聊天原文一样裸文本显示。
- 这些字段应该有明显视觉标记，让人一眼知道它们是模型/编排派生信息，不是原始聊天内容。

## 2. 不要改的东西

本轮不要改 backend。

Codex 已修复这些后端/稳定性问题：

- completed session detail 不再返回几百 MB。
- detail 中 stream lane 只保留最新累计 message。
- `tokenChunks` detail 保留尾部 500 条。
- `events` detail 保留尾部 1000 条并附 `eventsTruncated`。
- 大 session HTTP detail 已从 `789MB/970MB` 降到 `2MB` 级。

不要动这些文件，除非用户另行要求：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/benshi_llm_agent.py`
- `scripts/run_review_editor_server.py`
- `state/config/llm.local.json`

## 3. 已有 PCQQ/forward UI 链路

### 3.1 主消息列表入口

文件：

- `apps/review-editor/src/components/MessageList.vue`

当前 review 页消息列表的关键链路：

```vue
<MessageBubble
  v-else
  :message="row.message"
  :selected="row.message.messageUid === selectedMessageUid"
  :active-card-id="activeCardId"
  :chat-id="chatId"
  :jump-highlighted="row.message.messageUid === flashMessageUid"
  :inline-related-items="inlineRelatedItemsByMessageUid?.[row.message.messageUid] ?? []"
  @select-message="$emit('select-message', $event)"
  @jump-to-message="handleQuotedJump"
  @open-asset="openAsset"
  @open-forward="openForward"
  @select-card="$emit('select-card', $event)"
/>
```

说明：

- `MessageList` 负责按日期插入 separator。
- `MessageBubble` 负责 PCQQ-like 气泡、reply、forward 卡片、asset tile。
- `openForward()` 负责把 forward detail 转成独立窗口或 modal。

不要复制一份新的消息气泡实现到 LLM Sessions。应优先复用 `MessageBubble` / `ForwardRecordViewer` / `openForwardWindow`。

### 3.2 forward 卡片现成实现

文件：

- `apps/review-editor/src/components/MessageBubble.vue`

template 中已有 forward 卡片：

```vue
<button
  v-if="isForwardKind && forwardSummary"
  type="button"
  class="message-card message-card--forward"
  @click.stop="handleForwardOpen"
>
  <p class="message-card__eyebrow">转发聊天记录</p>
  <strong class="message-card__title">{{ forwardSummary.title || "聊天记录" }}</strong>
  <p
    v-for="(line, index) in forwardSummary.previewLines || []"
    :key="`${message.messageUid}-forward-${index}`"
    class="message-card__line"
  >
    {{ line }}
  </p>
  <p
    v-if="!(forwardSummary.previewLines || []).length && forwardSummary.previewText"
    class="message-card__line"
  >
    {{ forwardSummary.previewText }}
  </p>
  <p v-if="forwardSummary.forwardedCount" class="message-card__foot">
    共 {{ forwardSummary.forwardedCount }} 条
  </p>
</button>
```

CSS 已有：

```css
.message-card--forward {
  text-align: left;
  cursor: pointer;
}

.message-card--forward:hover {
  background: linear-gradient(180deg, #ffffff, #f3f8ff);
  border-color: rgba(72, 127, 211, 0.16);
}

.message-card__eyebrow {
  margin: 0 0 3px;
  color: #8e97a5;
  font-size: 10px;
}
```

目标：

- LLM Sessions 的聊天记录折叠卡片应该视觉上接近这个 forward card。
- 可以抽一个 `ForwardSummaryCard` 或 `LlmChatRecordCard`，但样式应从这套 `.message-card--forward` 收敛，不要新造蓝色 inspector 卡片。

### 3.3 forward 打开逻辑

文件：

- `apps/review-editor/src/components/MessageList.vue`

当前逻辑：

```ts
async function openForward(messageUid: string) {
  const message = props.messages.find((item) => item.messageUid === messageUid);
  if (!message) {
    return;
  }
  const detail = forwardDetailFromMessage(message);
  if (!detail) {
    return;
  }
  const enrichedDetail = enrichForwardDetailWithMessages(detail, props.messages);
  const openedAsChildWindow = await openForwardWindow(enrichedDetail);
  if (openedAsChildWindow) {
    previewForward.value = null;
    return;
  }
  previewForward.value = enrichedDetail;
}
```

说明：

- Tauri 环境下优先 `openForwardWindow(enrichedDetail)`。
- 失败或非 Tauri 时 fallback 到 `previewForward`，由 `<ForwardRecordViewer :root="previewForward" />` 显示 modal。
- LLM Sessions 应复用这一模式。

### 3.4 独立窗口实现

文件：

- `apps/review-editor/src/forwardWindow.ts`
- `apps/review-editor/src/ForwardRecordWindowApp.vue`

`forwardWindow.ts` 核心：

```ts
export async function openForwardWindow(detail: ForwardDetail): Promise<boolean> {
  if (!isTauriRuntime()) {
    return false;
  }
  const key = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  if (!storeForwardWindowPayload(key, detail)) {
    return false;
  }
  const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
  const windowRef = new WebviewWindow(label, {
    url: `/?mode=forward-viewer&forwardKey=${encodeURIComponent(key)}`,
    title: detail.title || "转发聊天记录",
    width: 860,
    height: 760,
    minWidth: 680,
    minHeight: 520,
    resizable: true,
    transparent: true,
    decorations: false,
    shadow: false,
    center: true,
  });
  ...
}
```

`ForwardRecordWindowApp.vue` 核心：

```vue
<ForwardRecordViewer
  :root="detail"
  surface="window"
  @close="closeWindow"
/>
```

要求：

- LLM Sessions 的“展开聊天记录”也应调用 `openForwardWindow(detail)`。
- 不要重新实现 Tauri child window。
- 注意 `MAX_FORWARD_PAYLOAD_BYTES = 2_000_000`，超过时会 fallback modal。LLM packet 过大时可以只传必要 `ForwardDetail`，不要把完整 prompt/raw JSON 一起塞进去。

### 3.5 完整聊天记录 viewer

文件：

- `apps/review-editor/src/components/ForwardRecordViewer.vue`

关键能力：

- `surface="modal"`：页面内覆盖层。
- `surface="window"`：独立窗口内嵌。
- 支持 nested forward drill-down。
- 支持 image/video/file/speech/sticker asset 显示。
- 支持 reply preview。
- 支持日期分组。

不要在 LLM Sessions 里重复写一个聊天记录弹窗。应直接使用：

```vue
<ForwardRecordViewer :root="previewForward" @close="previewForward = null" />
```

或在子窗口里复用现有 `ForwardRecordWindowApp.vue`。

## 4. 类型契约和映射

文件：

- `apps/review-editor/src/types.ts`

需要复用的类型：

```ts
export interface ForwardMessageEntry {
  senderId?: string | null;
  senderName?: string | null;
  rawSenderId?: string | null;
  rawSenderName?: string | null;
  aliasSenderId?: string | null;
  aliasSenderName?: string | null;
  avatarUrl?: string | null;
  content?: string | null;
  textContent?: string | null;
  timestampIso?: string | null;
  segments?: TranscriptSegment[];
  replyTo?: ForwardReplyPreview | null;
}

export interface ForwardDetail {
  title?: string | null;
  summaryText?: string | null;
  previewLines?: string[];
  forwardedCount?: number | null;
  messages: ForwardMessageEntry[];
}
```

LLM packet/prompt 中的聊天记录应转换成 `ForwardDetail`：

```ts
type PacketChatRecord = {
  title: string;
  summaryText: string;
  previewLines: string[];
  forwardedCount: number;
  messages: ForwardMessageEntry[];
};
```

字段映射建议：

- `message_uid` / `messageUid` -> synthetic uid only for preview; `ForwardMessageEntry` 本身不要求 uid。
- `timestamp_iso` / `timestampIso` -> `timestampIso`
- `sender_id` / `senderId` -> `senderId` + `rawSenderId`
- `sender_name` / `senderName` -> `senderName` + `rawSenderName`
- `content` / `text_content` / `textContent` / `content_preview` -> `content` + `textContent`
- `segments` -> `segments`
- `reply_to` / `replyTo` -> `replyTo`

资源字段：

- `segments[*].extra.asset_url` / `asset_url` 要保留给 `ForwardRecordViewer` / `forwardRecord.ts`。
- 不要使用 JSONL 原始 `source_path` 当当前机器 truth。
- 当前可显示 URL 应走 backend 已生成的 `asset_url` / `assetUrl`。

## 5. LLM Sessions 当前代码位置

主文件：

- `apps/review-editor/src/components/LlmSessionPage.vue`

当前有这些问题点：

### 5.1 Packet 仍是 inspector 风格

当前 packet template：

```vue
<details class="packet-block" :open="isShortText(entry.message)">
  <summary class="packet-block__head">
    <span class="packet-block__label">Packet</span>
    <span class="packet-block__title">{{ entry.message.title || 'Chat Packet' }}</span>
  </summary>
  <div class="packet-block__body">
    <p v-if="packetBodyText(entry.message)">{{ packetBodyText(entry.message) }}</p>
    ...
    <details v-if="entry.message.jsonPreview" class="raw-fold">
      <summary class="fold__btn">Raw</summary>
      <pre class="raw-pre">{{ formatJsonPreview(entry.message.jsonPreview) }}</pre>
    </details>
  </div>
</details>
```

问题：

- 这更像 debug inspector，不像聊天记录。
- 如果 `jsonPreview` 或 `text` 里有完整 prompt/message context，会变成纯 JSON/类 JSON 阅读负担。
- Raw 在 closed details 中仍然进入 DOM，长 payload 有性能风险。

目标：

- 对能提取聊天记录的 packet/prompt，默认显示 PCQQ-like forward summary card。
- Raw 只作为二级 debug 折叠，不是主视觉。
- Raw 内容最好 lazy render，只有 details open 时才渲染。

### 5.2 Final Report 是裸 `pre`

当前代码：

```vue
<div v-if="activeSession.finalReport" class="turn turn--left">
  <div class="report-block">
    <div class="report-block__head">Final Report</div>
    <pre class="report-block__body">{{ activeSession.finalReport }}</pre>
  </div>
</div>
```

问题：

- 所有内容按同一层级显示。
- `baseline_role=[{...}]`、`shi_delta=[{...}]`、`bearingness=[{...}]` 等功能字段看起来像聊天原文。
- 用户无法一眼区分“原文证据”和“模型/编排派生描述”。

目标：

- 最终报告不要只用裸 `pre`。
- 至少把功能字段行识别成专用块：
  - `功能字段`
  - `模型推断`
  - `非原文`
  - `证据/引用`
- 原文 quote / chat content 应和模型字段视觉分开。

### 5.3 Structured JSON block 只是通用字段预览

文件：

- `apps/review-editor/src/components/LlmStructuredStreamBlock.vue`
- `apps/review-editor/src/lib/structuredStreamPreview.ts`

当前只做：

- probable JSON 检测
- top-level field preview
- Raw fold

问题：

- 它不知道领域 schema。
- parse 成功后也只是 `contract_version`, `analysis_mode`, `direct_evidence_layer` 等字段列表。
- 用户需要看到“这是什么层/字段，是否原文，是否模型推断”。

目标：

- 可以保留 generic fallback。
- 对已知 schema 字段做领域化呈现：
  - `direct_evidence_layer` -> 证据层
  - `structured_inference_layer` -> 推断层
  - `adversarial_hypothesis_layer` -> 反证/对抗假设
  - `unknown_boundary_layer` -> 边界/未知
  - `judgment_verdicts` -> 结论
  - `baseline_role`, `shi_delta`, `bearingness` -> 模型派生字段/非原文
- 不要把数组对象 stringify 后直接塞到正文。

## 6. 推荐实现方案

### 6.1 新增聊天记录提取工具

建议新增：

- `apps/review-editor/src/lib/llmSessionChatRecord.ts`

职责：

- 从 `LlmSessionChatMessage.jsonPreview` / prompt payload / packet payload 中提取聊天记录。
- 输出 `ForwardDetail | null`。
- 输出 compact summary 用于 card。

建议函数：

```ts
export function forwardDetailFromLlmPacket(message: LlmSessionChatMessage): ForwardDetail | null;
export function chatRecordSummaryFromForwardDetail(detail: ForwardDetail): {
  title: string;
  summaryText: string;
  previewLines: string[];
  messageCount: number;
  senderCount: number;
  assetCount: number;
  missingAssetCount: number;
};
```

候选输入路径要兼容：

- `jsonPreview.messages`
- `jsonPreview.selected_messages`
- `jsonPreview.context_messages`
- `jsonPreview.request.inputPacket.messages`
- `jsonPreview.inputPacket.messages`
- `jsonPreview.packet.messages`
- `jsonPreview.message_first_context.message_probes`
- `jsonPreview.message_first_context.message_packet`
- `jsonPreview.working_set.dynamic_sections[]` 中含 message/probe 的 section

注意：

- 有些当前真实 payload 只有 `message_probes`，没有完整 message list。此时仍可生成 preview card，但完整窗口里只显示 probe preview，不要谎称是完整原始聊天。
- title/summary 应明确：
  - `模型输入聊天记录`
  - `16 条 message probes`
  - `223 selected messages summarized`
  - `完整原文不可用，仅显示 packet/probe preview`

### 6.2 新增 LLM chat record card

建议新增：

- `apps/review-editor/src/components/LlmChatRecordCard.vue`

职责：

- 折叠态卡片。
- 视觉复用 `.message-card--forward` 的信息结构。
- 点击时调用 `openForwardWindow(detail)`。
- fallback 到 `ForwardRecordViewer` modal。

不要把完整聊天记录 inline 展开到 transcript 主流里。

伪代码：

```vue
<button type="button" class="llm-chat-record-card" @click="open">
  <p class="message-card__eyebrow">聊天记录</p>
  <strong class="message-card__title">{{ summary.title }}</strong>
  <p v-for="line in summary.previewLines" class="message-card__line">{{ line }}</p>
  <p class="message-card__foot">
    共 {{ summary.messageCount }} 条 · {{ summary.senderCount }} 位发送者
  </p>
</button>

<ForwardRecordViewer :root="previewForward" @close="previewForward = null" />
```

打开逻辑：

```ts
const opened = await openForwardWindow(detail);
if (!opened) previewForward.value = detail;
```

### 6.3 在 LlmSessionPage 中替换 packet/prompt 主显示

修改点：

- `entry.type === 'packet'`
- `entry.type === 'prompt'`

逻辑：

- 如果 `forwardDetailFromLlmPacket(entry.message)` 有结果：
  - 显示 `LlmChatRecordCard`
  - 显示 compact meta chips：assets/missing/tools/evidence gaps
  - Raw 放二级折叠
- 如果没有聊天记录：
  - 保留当前 packet-block fallback

### 6.4 Final report 字段分层

建议新增：

- `apps/review-editor/src/lib/llmFunctionalFieldPreview.ts`
- `apps/review-editor/src/components/LlmFunctionalReportBlock.vue`

目标：

- 解析 `activeSession.finalReport` 或 parsed model JSON 的关键字段。
- 把模型派生字段变成 callout，不让它们像原文聊天一样混入正文。

最低实现也应做到：

- 识别行前缀：
  - `baseline_role=`
  - `shi_delta=`
  - `bearingness=`
  - `core_reason=`
  - `direct_evidence_layer`
  - `structured_inference_layer`
  - `adversarial_hypothesis_layer`
  - `unknown_boundary_layer`
  - `judgment_verdicts`
- 对这些行渲染为 `.functional-field-card`。
- 卡片头显示：
  - `模型派生字段`
  - `非原文`
  - 字段名
- 内容默认折叠或只显示前 2 行。
- 原始聊天 quote / content 仍显示为普通 prose 或引用块。

视觉建议：

- 不用蓝色大面积背景。
- 使用细左边线、浅金/灰绿标签、低饱和色。
- 让“功能字段”和“原文”形成明确区分。

## 7. 当前前端额外问题审查

这些是我看到但用户未必已经指出的问题：

1. `LlmSessionPage.vue` 的 packet/prompt/final report 仍偏 inspector，不像 ChatGPT/OpenWebUI/PCQQ。
2. `report-block__body` 用 `pre` 展示所有最终报告，导致模型派生字段、JSON-ish 数组、普通结论混在同一视觉层。
3. `raw-fold` 现在 closed 状态仍渲染 `<pre>`，长 prompt/raw payload 仍会进入 DOM。建议改为 lazy render。
4. `LlmSessionFeedItem.vue` 看起来是旧方案/未接入主页面，里面也有一套 chat packet UI，容易误导。除非确认被使用，否则不要基于它继续扩展。
5. `LlmStructuredStreamBlock.vue` 已解决“半截 JSON 占屏”，但没有领域 schema 显示，因此 parse 后仍不够可读。
6. LLM Sessions 中 image/missing assets 已有基础可用，但样式和 review 页 asset tile 仍不统一。
7. `assetIcon()` / empty-state 等处有 emoji，后续视觉统一时应换成 SVG/icon 或纯文本标签。
8. Raw debug 内容目前和主阅读内容距离太近，建议统一降级为“开发者 payload”二级入口。
9. 如果未来仍有 Tauri renderer 卡顿，应给 SSE message merge 做 `requestAnimationFrame` 批处理，但当前主要崩溃原因已由 Codex 后端修复。

## 8. 验收清单

必须通过：

- LLM Sessions 中能提取聊天记录的 packet/prompt 默认显示 compact PCQQ forward-like card。
- 点击聊天记录 card，在 Tauri 中打开独立窗口。
- 独立窗口使用现有 `ForwardRecordViewer`，显示 PCQQ-like 消息列表、日期 separator、头像、reply、asset。
- 非 Tauri 或子窗口失败时 fallback 到页面内 `ForwardRecordViewer` modal。
- 主 transcript 不再 inline 展开大段聊天 JSON。
- 功能字段如 `baseline_role`、`shi_delta`、`bearingness` 不再裸文本混在正文里；必须显示为模型派生/非原文字段。
- Raw JSON 仍可查看，但默认二级折叠，且最好 lazy render。
- 不引入新依赖。
- 不改 backend。

验证命令：

```powershell
cd D:\Coding_Project\IsThisShit\apps\review-editor
npx vue-tsc --noEmit
npx vitest run
```

手动验收：

- 打开 `LLM Sessions`。
- 选择真实 session：`live_32bbc7776ce6c8` 或 `live_6fab58045c3264`。
- 不应看到聊天记录区域直接铺大段 JSON。
- 应看到类似 review 页 forward 的聊天记录卡片。
- 点击卡片应打开完整聊天记录窗口。
- 最终报告里的功能字段应有明显“模型派生/非原文”视觉标记。
