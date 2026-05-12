# Claude Code `LLM Sessions` Final Report UI 验收失败说明与二次修复规格

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 状态：上一轮 `chat packet / forward card` UI 修复后，用户验收仍失败。本文说明失败根因和下一轮只改前端的明确修复范围。  
> 结论：上一轮修复只覆盖了 prompt/packet 分支，没有覆盖最终报告 `activeSession.finalReport` 分支；真实页面中仍裸显示大段 `human_report` 文本。

## 1. 现象

用户在 `LLM Sessions` 真实 session 中仍看到大段原文摊开，例如：

```text
'bearingness': 'core_bearing'
'message_uid': 'msg_6341ec8729eade50'
- priority=text_native_shi_object, group_reaction_echo, ...
- 口吻层输出:
  - 这窗不是那种截图包浆拉满的外卖史...
```

这些内容仍然像普通文本一样撑满主 transcript。用户期望：

- 聊天记录 / packet 默认折叠为 PCQQ forward card。
- 模型派生字段使用功能性字段 UI。
- 最终报告不能把 `baseline_role` / `shi_delta` / `bearingness` / `口吻层输出` 等结构化/功能字段裸显示成普通正文。

## 2. 根因定位

### 2.1 上一轮只处理了 prompt/packet

当前 `apps/review-editor/src/components/LlmSessionPage.vue` 已有：

```vue
<div v-else-if="entry.type === 'prompt'" class="turn turn--left">
  <LlmSessionChatPacketCard
    v-if="packetViewModels.get(entry.key)"
    :model="packetViewModels.get(entry.key)!"
    @open="openLlmChatPacket"
  />
  <details v-else class="prompt-block">
    ...
  </details>
</div>

<div v-else-if="entry.type === 'packet'" class="turn turn--left">
  <LlmSessionChatPacketCard
    v-if="packetViewModels.get(entry.key)"
    :model="packetViewModels.get(entry.key)!"
    @open="openLlmChatPacket"
  />
  <details class="packet-block" :open="isShortText(entry.message)">
    ...
  </details>
</div>
```

这只覆盖 `useTranscript()` 产出的 `prompt` / `packet` entry。

截图里裸显示的内容不是这个分支，而是 final report 分支。

### 2.2 final report 仍然有裸 `<pre>` fallback

当前 `apps/review-editor/src/components/LlmSessionPage.vue` 仍有：

```vue
<div v-if="activeSession.finalReport" class="turn turn--left">
  <div class="report-block">
    <div class="report-block__head">Final Report</div>
    <LlmStructuredStreamBlock
      v-if="finalReportIsJson(activeSession.finalReport)"
      :text="activeSession.finalReport"
      :is-complete="true"
    />
    <pre v-else class="report-block__body">{{ activeSession.finalReport }}</pre>
  </div>
</div>
```

真实 `finalReport` 来自 backend：

```py
"finalReport": _string(_as_record(result_payload.get("analysis_output")).get("human_report")).strip() or None
```

对应文件：

- `src/qq_data_analysis/llm_session_service.py`

这意味着前端拿到的是 `analysis_output.human_report`，不是 raw JSON。

真实样例 `state/llm_sessions/live_6fab58045c3264/result.json` 中：

- `analysis_output.human_report` 长度约 `4687`
- 开头是 `## Benshi Master LLM`
- 包含 `baseline_role=...`、`shi_delta=...`、`bearingness=[{...}]`、`口吻层输出`

因此：

```ts
export function finalReportIsJson(report: string): boolean {
  const t = report.trimStart();
  return t.startsWith("{") || t.startsWith("[");
}
```

返回 `false`，页面必然落入：

```vue
<pre class="report-block__body">{{ activeSession.finalReport }}</pre>
```

这就是用户截图中仍然看到大段纯文本/类 JSON 的直接原因。

### 2.3 `extractDomainFields()` 已写但没有接上最终报告

当前 `apps/review-editor/src/lib/llmSessionChatPacketAdapter.ts` 中已有：

```ts
export function extractDomainFields(parsed: unknown): LlmFunctionalField[] {
  const r = asRecord(parsed);
  const fields: LlmFunctionalField[] = [];
  for (const { key, label, category } of DOMAIN_KEYS) {
    const v = r[key];
    if (v === undefined || v === null) continue;
    ...
    fields.push({ key, label, category, valuePreview: preview, rawValue: v });
  }
  return fields;
}
```

但当前问题有两层：

- 该函数只适合 parsed JSON object。
- `activeSession.finalReport` 是 markdown-ish `human_report` string，不是 JSON。
- `LlmSessionPage.vue` 没有把 `human_report` 解析成 functional fields。

所以这个函数对当前验收截图没有产生任何效果。

## 3. 本轮修复目标

本轮目标不是再改 packet card，而是新增/替换 final report 渲染。

需要新增一个 final report 专用组件，例如：

- `apps/review-editor/src/components/LlmFinalReportBlock.vue`
- `apps/review-editor/src/lib/llmFinalReportParser.ts`

然后把 `LlmSessionPage.vue` 中 final report 分支改为：

```vue
<div v-if="activeSession.finalReport" class="turn turn--left">
  <LlmFinalReportBlock :report="activeSession.finalReport" />
</div>
```

禁止继续保留“大段全文 `<pre>` fallback”作为默认展示。

Raw 原文可以保留，但必须默认折叠并懒渲染。

## 4. `LlmFinalReportBlock` 应该怎么显示

### 4.1 高层布局

推荐结构：

```text
Final Report
├─ Summary prose / Markdown prose
├─ Evidence / observation cards
├─ Functional fields
│  ├─ 模型推断: baseline_role / shi_delta / bearingness
│  ├─ 编排字段: priority / deprioritized
│  ├─ 证据边界: media gap / boundary / missing image
├─ Voice / 口吻层输出
└─ Raw report (collapsed)
```

不要求一次做成复杂 report editor，但最低限度必须：

- 不把 `bearingness=[{...}]` 整段显示成 prose。
- 不把 `baseline_role=[...]`、`shi_delta=[...]`、`priority=...` 当普通文本。
- `口吻层输出` 要有单独 section，而不是混在 raw 文本尾部。
- 原始 raw report 默认折叠。

### 4.2 功能字段视觉

复用当前已有：

- `apps/review-editor/src/components/LlmFunctionalFieldBlock.vue`

如果现有组件不足，可以扩展它，但不要再做普通 `<pre>`。

字段分类建议：

```ts
baseline_role      -> model_inference / 模型推断
shi_delta          -> model_inference / 模型推断
bearingness        -> model_inference / 模型推断
priority           -> orchestration / 编排字段
deprioritized      -> orchestration / 编排字段
boundary           -> evidence_boundary / 证据边界
missing image      -> evidence_boundary / 证据边界
口吻层输出          -> model_inference 或 source_quote 旁的独立 voice section
```

`bearingness` 数组尤其要拆开显示。不要显示成：

```text
bearingness=[{'message_uid': '...', 'point_type': '...', ...}]
```

应显示为卡片/行：

```text
[模型推断] 承载度 · msg_d25bd8516...
point_type: text_native_shi_object
bearingness: core_bearing
cue: “吹高通的不买高通机器”
why: 局部文本本身就构成可消费错位点...
```

如果 parser 无法完整解析 Python repr，也至少要用规则截断：

- 按 `{...}` item 尝试拆行。
- 每个 item 最大显示 2-4 个关键字段。
- 解析失败的残余内容进 `Raw report`，不要进入正文。

## 5. Parser 建议

### 5.1 输入形态

真实 `human_report` 不是标准 JSON，而是 Markdown + Python repr / key-value 混合。

样例特征：

```text
## Benshi Master LLM
- 分析对象: ...
- ...
- baseline_role=['...', '...']
- shi_delta=['...', '...']
- bearingness=[{'message_uid': '...', 'point_type': '...', ...}, ...]
- priority=text_native_shi_object, group_reaction_echo, ...
- deprioritized=...
- boundary=...
- 口吻层输出:
  - 这窗不是那种截图包浆拉满...
```

不能只靠 `JSON.parse()`。

### 5.2 最小可行 parser

新增：

- `apps/review-editor/src/lib/llmFinalReportParser.ts`

建议输出：

```ts
import type { LlmFunctionalField } from "./llmSessionChatPacketAdapter";

export interface LlmFinalReportViewModel {
  title: string;
  metaLines: string[];
  proseSections: Array<{
    heading: string;
    lines: string[];
  }>;
  functionalFields: LlmFunctionalField[];
  voiceLines: string[];
  raw: string;
  parserWarnings: string[];
}
```

最小规则：

1. `## ...` 作为 title。
2. 普通 bullet 进入 `proseSections`。
3. 匹配 `baseline_role=` / `shi_delta=` / `bearingness=` / `priority=` / `deprioritized=` / `boundary=` 的行，转成 `functionalFields`。
4. `口吻层输出:` 后续 indented bullet 进入 `voiceLines`。
5. 任何无法分类的大段 repr 不进入正文，只放 raw 折叠。

### 5.3 可选更强 parser

因为 `baseline_role=[...]` 和 `bearingness=[{...}]` 看起来接近 Python literal，可以尝试：

- 把单引号 Python repr 转成 JSON 风格不可靠，不建议直接全局替换。
- 更安全做法：对已知字段做局部 tolerant extraction。
- 可以只提取这些字段：
  - `message_uid`
  - `point_type`
  - `bearingness`
  - `exact_local_cue`
  - `cue_quote_or_token`
  - `core_object_relation`
  - `why`

不需要完美解析每个字段。目标是避免裸摊 raw。

## 6. `LlmStructuredStreamBlock` 也需要接 domain renderer

上一轮新增了 streaming JSON block，但它目前主要显示 top-level key preview。

如果完整 JSON parse 成功且包含：

- `direct_evidence_layer`
- `structured_inference_layer`
- `adversarial_hypothesis_layer`
- `judgment_verdicts`
- `baseline_role`
- `shi_delta`
- `bearingness`

建议不要只显示 `key: {...}`。应复用 `LlmFunctionalFieldBlock` 或 final report parser 的 domain renderer。

这不是本截图失败的唯一根因，但属于同一类问题：模型输出的结构化/功能字段必须有 domain-aware UI。

## 7. 本轮不要碰的部分

上一轮这些工作基本方向正确，不要回滚：

- `LlmSessionChatPacketCard.vue`
- `llmSessionChatPacketAdapter.ts` 中对 `messages` / `message_probes` 的基本适配
- `ForwardRecordViewer` / `openForwardWindow` 复用
- asset thumbnail / missing asset compact display
- raw details 懒渲染

本轮重点是：

- final report
- mixed markdown/Python repr human_report parser
- functional field domain UI
- structured JSON final-state domain renderer

## 8. 验收标准

在用户截图对应 session 中应满足：

- 页面不再出现整屏 `bearingness=[{'message_uid': ...}]` 裸文本。
- 页面不再出现整屏 `baseline_role=[...]` / `shi_delta=[...]` 裸文本。
- `口吻层输出` 显示为独立 section。
- `priority` / `deprioritized` / `boundary` 显示为功能字段 badge/card。
- final report 的自然语言总结仍可读，不被全部藏进 raw。
- Raw report 仍可展开，但默认折叠，关闭时不渲染大 `<pre>`。
- prompt/packet card 和 forward window 行为不回退。

## 9. 推荐测试

在 `apps/review-editor` 下运行：

```powershell
npx vue-tsc --noEmit
npx vitest run
```

建议新增 unit test：

- `llmFinalReportParser` 能识别 `baseline_role=...`。
- `llmFinalReportParser` 能识别 `shi_delta=...`。
- `llmFinalReportParser` 能识别 `bearingness=[{...}]` 并至少抽出 `message_uid` / `point_type` / `why`。
- `llmFinalReportParser` 能把 `口吻层输出:` 后续 bullet 放进 `voiceLines`。
- `LlmFinalReportBlock` 默认不渲染 raw `<pre>`。
- `LlmSessionPage.vue` final report 分支不再包含裸 `<pre>{{ activeSession.finalReport }}</pre>`。

## 10. 是否需要 backend 改动

本轮前端可以先修，不要求 backend。

但有一个后续改进建议：backend detail 目前只暴露：

```py
"finalReport": analysis_output.human_report
```

理想状态下可以额外暴露结构化字段，例如：

```json
{
  "finalReport": "...human readable...",
  "finalReportJson": { "...analysis_output.compact_payload..." },
  "reviewSurfaceGuidance": { ... }
}
```

这能让前端少做 tolerant text parsing。不过这不是本轮阻塞项，除非前端 parser 发现无法稳定覆盖真实报告。

