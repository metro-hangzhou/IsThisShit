# Claude Code `LLM Sessions` Chat Packet / Functional Field UI 任务规格

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 本文状态：本轮 UI 任务的主入口，优先级高于此前 `LLM Sessions` UI 交接文档中的同类描述。  
> 分工边界：CC 负责 `apps/review-editor` 前端/UI；Codex 已处理 backend detail 体量爆炸、真实 session detail 稳定性、模型配置和链路验收。

## 1. 用户反馈原文语义

当前 `LLM Sessions` 页面在真实 session 中出现的问题：

- 聊天记录 / prompt packet / model context 直接变成大段 JSON、Python repr 或类 JSON 文本摊开。
- 用户期望这块默认折叠，折叠态显示成 Review 页已实现的 PCQQ 转发聊天记录卡片样式。
- 点击折叠卡片后，打开一个独立窗口展示聊天记录。
- 展开窗口里的聊天记录 UI 应直接照搬 Review 页现有的 PCQQ-like forward viewer，不要再自造一套。
- `口吻层输出`、`baseline_role=[...]`、`shi_delta=[...]`、`bearingness=[...]` 等模型/编排派生字段不应显示成普通聊天原文。
- 派生字段需要有明显视觉标记，让人一眼知道它们是模型输出的功能性字段、描述性字段、证据字段，而不是 QQ 原文。

## 2. 当前分工与禁止范围

Codex 已完成后端稳定性修复：

- completed session detail 不再返回几百 MB。
- detail 中 streaming lane 只保留最新累计 message，避免 O(n^2) 重复累计。
- `tokenChunks` detail 只保留尾部 500 条。
- `events` detail 只保留尾部 1000 条，并附 `eventsTruncated` metadata。
- 大 session detail 已从 `789MB/970MB` 降到 `2MB` 级。
- `tests/test_llm_session_service.py` 已通过。

本轮 CC 不要改这些文件：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/benshi_llm_agent.py`
- `src/qq_data_analysis/orch/**`
- `scripts/run_review_editor_server.py`
- `state/config/llm.local.json`

CC 可以改这些前端文件：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/components/LlmStructuredStreamBlock.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/types.ts`

CC 可以新增这些前端文件：

- `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`
- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`
- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`
- 对应 `*.test.ts`

不要把本任务做成 backend schema 变更。优先在前端 adapter 层兼容已有事件 payload。

## 3. 已有 Review 页 PCQQ / forward UI 必须复用

### 3.1 `MessageList.vue` 是 Review 页消息流入口

文件：

- `apps/review-editor/src/components/MessageList.vue`

关键模板：

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

<MessageAssetViewer :asset="previewAsset" @close="previewAsset = null" />
<ForwardRecordViewer :root="previewForward" @close="previewForward = null" />
```

关键逻辑：

```ts
import { enrichForwardDetailWithMessages, forwardDetailFromMessage } from "../forwardRecord";
import { openForwardWindow } from "../forwardWindow";

async function openForward(messageUid: string) {
  const message = props.messages.find((item) => item.messageUid === messageUid);
  if (!message) return;
  const detail = forwardDetailFromMessage(message);
  if (!detail) return;
  const enrichedDetail = enrichForwardDetailWithMessages(detail, props.messages);
  const openedAsChildWindow = await openForwardWindow(enrichedDetail);
  if (openedAsChildWindow) {
    previewForward.value = null;
    return;
  }
  previewForward.value = enrichedDetail;
}
```

实现含义：

- Review 页已经具备“点击 forward 卡片 -> Tauri 子窗口 -> 失败 fallback 到 modal”的完整链路。
- `LLM Sessions` 不应再实现第二套聊天记录窗口。
- 正确路线是把 LLM session 中的聊天记录 / packet 转成 `ForwardDetail`，然后复用 `openForwardWindow(detail)` 和 `<ForwardRecordViewer :root="detail" />`。

### 3.2 `MessageBubble.vue` 已有 forward 折叠卡片

文件：

- `apps/review-editor/src/components/MessageBubble.vue`

当前 forward 卡片模板：

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

相关 CSS 语义：

```css
.message-card {
  border: 1px solid rgba(31, 45, 68, 0.08);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff, #f7f9fc);
}

.message-card--forward {
  text-align: left;
  cursor: pointer;
}

.message-card--forward:hover {
  background: linear-gradient(180deg, #ffffff, #f3f8ff);
  border-color: rgba(72, 127, 211, 0.16);
}

.message-card__eyebrow {
  color: #8e97a5;
  font-size: 10px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

实现建议：

- 最好抽出一个共享组件，例如 `ForwardSummaryCard.vue`，让 Review 页和 `LLM Sessions` 都使用它。
- 如果不抽共享组件，也可以在 `LlmSessionChatPacketCard.vue` 中复制最小必要结构，但视觉必须和 `.message-card--forward` 收敛。
- 不要继续使用蓝色 inspector card、packet debugger card 这类和 PCQQ/ChatGPT 都不一致的视觉。

### 3.3 `ForwardRecordViewer.vue` 是完整聊天记录窗口

文件：

- `apps/review-editor/src/components/ForwardRecordViewer.vue`

关键 props：

```ts
const props = defineProps<{
  root: ForwardDetail | null;
  surface?: "modal" | "window";
}>();
```

它已经支持：

- 日期分组。
- sender avatar。
- sender name / timestamp。
- reply quote。
- text bubble。
- image / video / file / speech assets。
- missing asset 状态。
- nested forward drilldown。
- `MessageAssetViewer` 预览。

这正是 LLM Sessions 中“点击聊天记录卡片后弹出一个独立窗口显示聊天记录”的目标 UI。

### 3.4 `forwardWindow.ts` 是独立窗口打开入口

文件：

- `apps/review-editor/src/forwardWindow.ts`

关键代码：

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
}
```

注意：

- localStorage payload 上限为 `MAX_FORWARD_PAYLOAD_BYTES = 2_000_000`。
- 如果 payload 太大或 Tauri window 创建失败，应 fallback 到页面内 `<ForwardRecordViewer>` modal。
- LLM Sessions 的 card click 逻辑可以直接复用这个返回 boolean 的模式。

### 3.5 `forwardRecord.ts` 是类型适配核心

文件：

- `apps/review-editor/src/forwardRecord.ts`

关键函数：

```ts
export function forwardDetailFromMessage(message: {
  forwardDetail?: ForwardDetail | null;
  segments?: TranscriptSegment[];
}): ForwardDetail | null {
  if (message.forwardDetail) {
    return message.forwardDetail;
  }
  const forwardSegment = (message.segments || []).find((segment) => segment.type === "forward");
  return forwardDetailFromSegment(forwardSegment);
}
```

这说明 `ForwardRecordViewer` 消费的核心类型不是 `ChatMessageVM`，而是 `ForwardDetail`。

`LLM Sessions` 需要做的不是“复制 MessageList”，而是：

1. 从 session event payload / `jsonPreview` 中识别聊天记录。
2. 转成 `ForwardDetail`。
3. 折叠态用 forward summary card。
4. 点击态复用 `openForwardWindow(detail)` / `ForwardRecordViewer`。

## 4. 目标架构

### 4.1 新增 adapter：`llmSessionChatPacketAdapter.ts`

建议新增：

- `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts`

职责：

- 只做数据适配，不做 DOM。
- 输入：`LlmSessionChatMessage` 或 `msg.jsonPreview`。
- 输出：
  - `ForwardDetail | null`
  - `summary`
  - `functionalFields`
  - `sourceKind`
  - `warnings`

建议类型：

```ts
import type { ForwardDetail, ForwardMessageEntry } from "../types";

export type LlmPacketSourceKind =
  | "raw_messages"
  | "message_probes"
  | "prompt_context"
  | "functional_only"
  | "unknown";

export interface LlmFunctionalField {
  key: string;
  label: string;
  category: "model_inference" | "orchestration" | "evidence_boundary" | "source_quote" | "debug";
  valuePreview: string;
  rawValue?: unknown;
  messageUid?: string | null;
}

export interface LlmChatPacketViewModel {
  sourceKind: LlmPacketSourceKind;
  title: string;
  summaryLines: string[];
  forwardedCount: number;
  senderCount?: number;
  assetSummary?: string;
  detail: ForwardDetail | null;
  functionalFields: LlmFunctionalField[];
  rawPreview?: unknown;
  warnings: string[];
}
```

### 4.2 Adapter 需要兼容的数据来源

真实 session 中可能出现这些形态，不要只兼容一种：

#### A. 完整消息数组

优先从这些路径找：

```ts
jsonPreview.messages
jsonPreview.selected_messages
jsonPreview.selectedMessages
jsonPreview.input_packet.messages
jsonPreview.inputPacket.messages
jsonPreview.request.input_packet.messages
jsonPreview.request.inputPacket.messages
```

如果找到数组，尽量按 `ForwardMessageEntry` 映射：

```ts
function messageToForwardEntry(raw: Record<string, unknown>): ForwardMessageEntry {
  return {
    senderId: stringField(raw, "sender_id") || stringField(raw, "senderId") || null,
    senderName: stringField(raw, "sender_name") || stringField(raw, "senderName") || null,
    rawSenderId: stringField(raw, "raw_sender_id") || stringField(raw, "rawSenderId") || null,
    rawSenderName: stringField(raw, "raw_sender_name") || stringField(raw, "rawSenderName") || null,
    avatarUrl: stringField(raw, "avatar_url") || stringField(raw, "avatarUrl") || null,
    content: stringField(raw, "content") || null,
    textContent: stringField(raw, "text_content") || stringField(raw, "textContent") || null,
    timestampIso: stringField(raw, "timestamp_iso") || stringField(raw, "timestampIso") || null,
    segments: normalizeSegments(raw.segments),
    replyTo: normalizeReply(raw.reply_to ?? raw.replyTo),
  };
}
```

#### B. `message_first_context.message_probes`

真实 `llm.prompt_built` 常见形态：

```text
jsonPreview.message_first_context.message_probes[]
jsonPreview.messageFirstContext.messageProbes[]
```

probe 不是原始聊天记录，而是模型输入前的分析摘要。它通常包含：

- `message_uid`
- `timestamp_iso`
- `sender_id`
- `sender_name`
- `content_preview`
- `asset_types`
- `message_tags`
- `has_forward`
- `forward_depth`
- `missing_media_count`
- `reply_target_preview`
- `bearingness_hint`
- `core_reason_hint`
- `shi_object_hint`
- `evidence_basis`

处理要求：

- 可以把 `content_preview` 映射为 viewer 中的一条消息预览，但必须标记 sourceKind = `message_probes`。
- 折叠卡片标题不要写“原始聊天记录”，应写类似“模型输入聊天摘要”。
- viewer 内如果沿用 `ForwardRecordViewer`，需要在卡片旁加醒目 badge：`摘要 / 非原文完整记录`。
- probe 的 `bearingness_hint`、`core_reason_hint`、`shi_object_hint`、`evidence_basis` 不应塞进普通 message text，应进入 `functionalFields`。

#### C. 只有 `message_packet` / `working_set`

真实 payload 中也可能只有：

```text
message_first_context.message_packet
working_set.stable_prefix
working_set.dynamic_sections
working_set.source_stats
```

这不是聊天记录。处理要求：

- 不要假装它是 PCQQ 聊天记录。
- 显示为“编排上下文 / packet metadata”功能块。
- raw 默认折叠。
- 显示 `included_message_uids`、`anchor_message_uids`、`source_stats` 等摘要。

### 4.3 新增 `LlmSessionChatPacketCard.vue`

建议新增：

- `apps/review-editor/src/components/LlmSessionChatPacketCard.vue`

职责：

- 折叠态卡片。
- 视觉贴近 `MessageBubble.vue` 中的 `.message-card--forward`。
- 点击后打开子窗口或 fallback modal。

建议 props：

```ts
const props = defineProps<{
  model: LlmChatPacketViewModel;
}>();
```

建议 emits：

```ts
const emit = defineEmits<{
  (event: "open", detail: ForwardDetail): void;
}>();
```

折叠态应该显示：

- eyebrow：`聊天记录` / `模型输入摘要` / `Packet metadata`
- title：chat name、session title 或 `Prompt packet`
- stats：`223 messages · 16 senders · 8 assets · 6 missing`
- preview lines：最多 3 行。
- source badge：`原文` / `摘要` / `编排字段`
- evidence badge：`missing media: 6` / `evidence gaps: 3`

不要在卡片内显示完整 JSON。

### 4.4 点击展开逻辑

建议在 `LlmSessionPage.vue` 中维护：

```ts
const previewForward = ref<ForwardDetail | null>(null);

async function openLlmChatPacket(detail: ForwardDetail) {
  const opened = await openForwardWindow(detail);
  if (opened) {
    previewForward.value = null;
    return;
  }
  previewForward.value = detail;
}
```

模板底部复用：

```vue
<ForwardRecordViewer :root="previewForward" @close="previewForward = null" />
```

不要新增第二套 full-screen chat viewer。

### 4.5 `LlmSessionPage.vue` 集成点

当前 `LlmSessionPage.vue` 中 packet 区域大致是：

```vue
<div v-else-if="entry.type === 'packet'" class="turn turn--left">
  <details class="packet-block" :open="isShortText(entry.message)">
    ...
    <div class="packet-block__body">
      <p v-if="packetBodyText(entry.message)">{{ packetBodyText(entry.message) }}</p>
      ...
      <details v-if="entry.message.jsonPreview" class="raw-fold">
        <summary class="fold__btn">Raw</summary>
        <pre class="raw-pre">{{ formatJsonPreview(entry.message.jsonPreview) }}</pre>
      </details>
    </div>
  </details>
</div>
```

目标：

- 在 `entry.type === 'packet'` 或 `entry.type === 'prompt'` 时，先尝试 `buildLlmChatPacketViewModel(entry.message)`。
- 如果 adapter 返回 `detail` 或可展示 summary，则优先渲染 `LlmSessionChatPacketCard`。
- 原 `packet-block` 中的 asset chips 可以保留在 card 下方，但不要取代 PCQQ chat card。
- raw 必须默认折叠，并且关闭时不要渲染大 `<pre>`。参考 `LlmStructuredStreamBlock.vue` 的 `rawOpen` 方案。

伪代码：

```vue
<LlmSessionChatPacketCard
  v-if="chatPacketModel(entry.message)"
  :model="chatPacketModel(entry.message)!"
  @open="openLlmChatPacket"
/>
```

注意：不要在 template 中重复调用重计算重解析函数。应在 computed 中预处理，或在 `useTranscript` 后扩展 entry view model。

## 5. 功能字段必须从普通文本中分离

### 5.1 问题字段示例

用户截图中出现的大段内容包括：

```text
- 口吻层输出:
  - baseline_role=[{'message_uid': 'msg_d25bd...', 'baseline_role': '...'}]
  - shi_delta=[{'message_uid': 'msg_d25bd...', 'shi_delta': '...'}]
  - bearingness=[{'message_uid': 'msg_d25bd...', 'point_type': '...'}]
```

这些不是 QQ 原文，而是模型或 orchestrator 的派生字段。

### 5.2 推荐视觉分类

新增或扩展：

- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`

分类：

```ts
type FunctionalFieldCategory =
  | "source_quote"        // 原文引用
  | "model_inference"    // 模型推断
  | "orchestration"      // 编排字段
  | "evidence_boundary"  // 证据缺口/边界
  | "debug";             // 调试字段
```

显示要求：

- `source_quote`：标成 `原文引用`，弱卡片。
- `model_inference`：标成 `模型推断`，使用更醒目的左边框或 badge。
- `orchestration`：标成 `编排字段`，使用 neutral/monospace key label。
- `evidence_boundary`：标成 `证据边界`，使用 amber/warning style。
- `debug`：默认折叠。

不要这样显示：

```text
baseline_role=[{...}]
shi_delta=[{...}]
```

应显示成类似：

```text
[模型推断] baseline_role
msg_d25bd... · 超出 routine topic 的具体错位总结
notes: 高通话题本身是基线，但“吹的人自己不买”不是普通数据讨论。

[模型推断] shi_delta
msg_d25bd... · 把抽象点从芯片谁强提升成立场表演与实际购买行为打架的可消费错位对象。
```

### 5.3 结构化输出渲染扩展

现有文件：

- `apps/review-editor/src/components/LlmStructuredStreamBlock.vue`
- `apps/review-editor/src/lib/structuredStreamPreview.ts`

当前能力：

- JSON streaming 时显示 top-level key preview。
- raw 默认折叠。

需要扩展：

- 完整 JSON parse 成功后，如果存在下列 domain keys，应使用 domain-aware section，不要只显示 generic `key: {...}`：
  - `direct_evidence_layer`
  - `structured_inference_layer`
  - `adversarial_hypothesis_layer`
  - `judgment_verdicts`
  - `baseline_role`
  - `shi_delta`
  - `bearingness`
  - `transport_facts`
  - `evidence_gaps`
  - `media_boundary`
- domain renderer 可以复用 `LlmFunctionalFieldBlock`。
- raw 仍可展开，但默认折叠。

## 6. 当前前端审查发现

这些是 Codex 读代码后发现的 UI/实现问题，建议本轮一起处理：

1. `LlmSessionPage.vue` 的 final report 仍是：

```vue
<pre class="report-block__body">{{ activeSession.finalReport }}</pre>
```

这会把模型结构化字段、Python repr、JSON-like 文本全部当成普通报告原文显示。应改成：

- 如果是 JSON：走 `LlmStructuredStreamBlock` / domain-aware renderer。
- 如果是 markdown/prose：按 ChatGPT prose 显示。
- 如果里面含 `baseline_role=[...]` 这类字段：拆成 functional field block。

2. `packet-block` / `prompt-block` 中 raw `<pre>` 即使 `<details>` 关闭，当前 Vue 仍可能先生成大字符串。

当前模式：

```vue
<details v-if="entry.message.jsonPreview" class="raw-fold">
  <summary class="fold__btn">Raw</summary>
  <pre class="raw-pre">{{ formatJsonPreview(entry.message.jsonPreview) }}</pre>
</details>
```

建议使用局部 open state，只有展开 Raw 时才渲染 `<pre>`。`LlmStructuredStreamBlock.vue` 已经这样做：

```vue
<details class="ss-block__raw" @toggle="handleRawToggle">
  <summary class="fold__btn">Raw</summary>
  <pre v-if="rawOpen" class="raw-pre">{{ rawText }}</pre>
</details>
```

3. `LlmSessionFeedItem.vue` 看起来是较早的 LLM session feed 组件，但当前 `LlmSessionPage.vue` 没有直接使用它。

不要把它当成目标设计来源。它不是 PCQQ/ChatGPT 风格，也没有复用 Review 页 forward viewer。

4. `assetIcon()` 仍返回 emoji：

```ts
case "image": return "🖼";
case "speech": return "🎤";
case "file": return "📄";
case "sticker": return "🎭";
```

这不是主要问题，但如果本轮顺手调整，建议改为内联 SVG 或文字 badge，和 Review 页视觉一致。

5. `chatPacketModel(entry.message)` 之类 adapter 不能在模板中重复调用。

真实 packet 可能很大。请使用 computed map 或在 transcript entry 构造时挂 view model，避免重复 JSON parse。

6. 真实 `message_first_context.message_probes` 不等于完整聊天记录。

如果只拿到 probes，应在 UI 上标成 `模型输入摘要 / 非完整原文`，不要误导用户以为窗口里是完整 PCQQ 原文。

## 7. 验收标准

完成后必须满足：

- 在 `LLM Sessions` 页面，聊天记录 / packet / prompt context 默认不会以整屏 JSON 或 Python repr 显示。
- 折叠态显示为 PCQQ forward card 风格。
- 点击卡片在 Tauri 中优先打开独立 forward window。
- 子窗口打开失败时 fallback 到页面内 `ForwardRecordViewer` modal。
- forward viewer 使用 Review 页现成 UI，能显示 sender、time、reply、image、video、file、speech、nested forward。
- `message_probes` 场景标记为摘要，不冒充完整原文。
- `baseline_role`、`shi_delta`、`bearingness`、`口吻层输出` 等字段有功能性 badge/callout，不再裸文本摊开。
- Raw JSON 保留入口，但默认折叠；关闭时不要渲染大 `<pre>`。
- 普通 assistant prose 和 streaming token 显示不能被破坏。
- 已有 asset thumbnail / lightbox 行为不能回退。

## 8. 推荐测试

在 `apps/review-editor` 下运行：

```powershell
npx vue-tsc --noEmit
npx vitest run
```

建议新增测试覆盖：

- adapter 能从 `jsonPreview.messages` 生成 `ForwardDetail`。
- adapter 能从 `message_first_context.message_probes` 生成摘要型 `ForwardDetail` 和 `functionalFields`。
- `LlmSessionChatPacketCard` 折叠态显示 stats / preview lines。
- 点击 card 时 emit/open detail。
- raw details 关闭时不渲染 raw `<pre>`。
- structured output 中 domain keys 能进入 functional field block。

手动验收 session：

- `live_32bbc7776ce6c8`
- `live_6fab58045c3264`
- 最新真实 `x3c_group_757773326_run_20260417_210641_orch` live session

## 9. 交付说明格式

完成后请回复：

- 改了哪些文件。
- 哪些 UI 复用了 `ForwardRecordViewer` / `openForwardWindow`。
- 完整 messages 与 message probes 两种数据形态分别如何显示。
- 功能字段如何分类显示。
- raw JSON 是否默认折叠且懒渲染。
- `vue-tsc` / `vitest` 结果。
- 是否还有需要 Codex 处理的 backend/schema gap。

