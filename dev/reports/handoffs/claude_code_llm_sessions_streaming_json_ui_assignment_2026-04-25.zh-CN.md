# Claude Code `LLM Sessions` Streaming JSON UI 任务入口

> 日期：2026-04-25  
> 目标受众：Claude Code  
> 当前分工：CC 负责 `LLM Sessions` 前端/UI；Codex 负责 backend/runtime、模型配置、真实链路验收。  
> 本文是本轮 UI-only 调整入口。请先读本文，再定位到文中列出的文件处理。

## 1. 当前问题

真实数据 session 已能完整跑通，后端落盘 artifact 没有 JSON 损坏：

- session: `live_6fab58045c3264`
- source run: `x3c_group_757773326_run_20260417_210641_orch`
- candidate: `group_757773326_candidate_001`
- final event: `session.completed`
- `state/llm_sessions/live_6fab58045c3264/result.json` 可被 Python `json.loads(...)` 正常解析
- `state/llm_sessions/live_6fab58045c3264/events.jsonl` 全部行可解析，坏行数为 `0`
- 本轮实测使用的旧配置为 `gpt-5.4`；Codex 已把后续配置切到 `gpt-5.5`，推理强度不变

用户看到的问题不是 backend artifact 坏了，而是前端流式展示策略不对：

- 模型正在流式输出一个较大的 JSON object。
- 当 JSON 尚未闭合时，UI 把半截 JSON 当成普通 assistant 正文直接摊开。
- 用户看到类似“漏了一个 `}`”的状态，因为流式尾部本来还没到。
- 等整段 JSON 完成并能被解析后，UI 才恢复成较正常的最终展示。
- 这个行为对调试体验很差：中间状态占屏、难读、像错误，但实际上只是未完成流。

## 2. 关键产品要求

不要把 JSON 流“憋到完整 parse 后再一口气显示”。

正确目标是：**增量渲染结构化输出**。

要求：

- 一旦 JSON 中已经出现部分字段或部分可识别结构，就应尽快在 UI 中显示出来。
- 对暂时无法 parse 的尾部片段，只做折叠、降噪、尾部预览或“生成中”状态。
- 不要把完整半截 raw JSON 作为普通 assistant prose 大面积显示。
- 不能牺牲实时性；用户要能边流式输出边观察模型正在生成什么。
- 完成后如果 JSON 可 parse，应切换成稳定的结构化/可读显示。
- 完成后如果 JSON 仍不可 parse，应显示明确的 invalid/incomplete JSON 状态，并默认折叠 raw 内容。

## 3. 不允许的修法

不要做这些：

- 不要等 `llm.response_completed` / `session.completed` 后才显示模型内容。
- 不要简单把所有 JSON 流隐藏到最后。
- 不要把问题推给 backend；本轮 backend 结果已验证完整。
- 不要改模型、prompt、orchestrator、LLM Session backend service。
- 不要为了 UI parse 方便改 `result.json` / `events.jsonl` 的语义契约。

## 4. 期望交互

当 assistant content lane 开始输出 `{` 或 `[`，并且文本暂时不可 `JSON.parse`：

- 显示一个 compact block，例如 `Structured output · streaming`。
- block 内优先展示已能识别的字段摘要，例如已经出现的 top-level key、已闭合的数组项数量、已闭合对象数量、当前字符数。
- 如果实现成本允许，可做浅层 incremental parser 或 tolerant preview：
  - 识别 top-level keys。
  - 已闭合字段显示为 key-value preview。
  - 当前正在生成的字段显示为 `streaming...`。
  - 对长字符串只显示前几行和尾部预览。
- Raw stream 必须可展开查看，但默认折叠。
- Raw 展开高度要限制，避免撑爆 transcript。
- 普通自然语言 assistant 输出仍按原 ChatGPT/OpenWebUI 风格即时流式显示，不要误伤。

完成后：

- 如果完整 JSON 可 parse：
  - 展示最终结构化摘要或当前已有的最终报告 UI。
  - Raw JSON 仍可折叠查看。
- 如果完整 JSON 不可 parse：
  - 显示 `Structured output incomplete/invalid`。
  - 显示最后错误位置或错误信息。
  - Raw JSON 默认折叠，不能占据整屏。

## 5. 可能原因定位

主要看这些文件：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`

当前可疑点：

- `useTranscript.ts` 会把 `assistant_message` / `assistant_reasoning` chunk 通过 `responseId + lane` 去重，只保留每条 lane 的最新累计文本。
- `LlmSessionPage.vue` 的 assistant render 直接调用 `msgText(entry.message)`：
  - `transcriptText || text`
  - 然后渲染到 `.assistant-prose`
- 当累计 text 是一个未闭合 JSON 字符串时，它会被当成普通 prose 显示。

建议做法：

- 在 UI 层增加 `isStructuredStreamingMessage(message)` / `structuredStreamState(message)`。
- 对 probable JSON stream 走专门组件，例如 `LlmStructuredStreamBlock.vue`。
- 该组件负责：
  - probable JSON 判断
  - parse 成功/失败状态
  - partial/tolerant preview
  - raw 折叠
  - 完成态和失败态视觉
- `LlmSessionPage.vue` 只负责分流，不要堆太多 parser 逻辑。

## 6. 允许改动范围

优先改：

- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`

可新增：

- `apps/review-editor/src/components/LlmStructuredStreamBlock.vue`
- `apps/review-editor/src/lib/structuredStreamPreview.ts`
- 对应测试文件

可补测试：

- `apps/review-editor/src/App.test.ts`
- 或新增专门的 structured stream unit test

禁止改：

- `src/qq_data_analysis/llm_session_service.py`
- `src/qq_data_analysis/orch/**`
- `src/qq_data_analysis/benshi_llm_agent.py`
- `scripts/run_review_editor_server.py`
- `state/config/llm.local.json`

## 7. 验收场景

至少覆盖 4 类：

1. 普通自然语言 streaming：
   - 仍然即时显示为 assistant prose。
   - 不被误判为 JSON。

2. 未闭合 JSON streaming：
   - 输入类似 `{"contract_version":"...","direct_evidence_layer":{"observations":[...`。
   - UI 不应显示一整屏 raw JSON 正文。
   - UI 应显示 compact structured streaming block。
   - 已到达的信息应能增量看到，不允许等完整闭合后才出现。

3. 完整 JSON streaming：
   - JSON 完成后 parse 成功。
   - UI 切到稳定 structured/final view。
   - Raw 可展开。

4. 完成但 JSON 仍损坏：
   - UI 显示 invalid/incomplete 状态。
   - Raw 默认折叠。
   - 不阻塞 session completed 状态显示。

## 8. 本地验证命令

在 `apps/review-editor` 下运行：

```powershell
npx vue-tsc --noEmit
npx vitest run
```

如果需要做手动验收：

- 使用已有真实 session `live_6fab58045c3264` 观察最终态。
- 使用 mock/fixture 构造未闭合 JSON chunk 观察流式中间态。
- 不要启动真实模型做 UI 单元验证，除非用户另外批准。

## 9. 交付说明要求

完成后请报告：

- 改了哪些文件。
- 未闭合 JSON streaming 如何展示。
- 已闭合 JSON 如何展示。
- 是否仍保留 raw 展开入口。
- 是否影响普通自然语言 streaming。
- `vue-tsc` / `vitest` 结果。
