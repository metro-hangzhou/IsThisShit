# LLM Sessions 实时流与 Failed Fetch 修复说明

> 日期：2026-04-24  
> 目的：记录本轮 Codex 对 `LLM Sessions` 实时流链路和瞬时错误展示的修复，避免后续 Claude Code 重构 UI 时误删。

## 背景

本轮本地 mock API 已验证：

- review API 可通过 `127.0.0.1:43127` 创建 mock session
- session stream 会实时下发 SSE
- 前端在 `LLM Sessions` 页可看到实时 token 输出

但用户观察到：实时流出现前，顶部红条会反复显示 `Failed to fetch`，随后 session 又能正常流式输出。

## 根因

根因不是 UI 渲染，而是前端错误状态策略过于激进：

- `App.vue` 在 `LLM Sessions` 页每 `1500ms` 轮询一次 `fetchLlmSessions()`
- 后端重启、API 刚启动、Tauri 子进程交接、SSE reconnect 窗口内，请求会短暂失败
- 失败时直接写入 `llmSessionError`
- `activeError` 会把 `llmSessionError` 渲染成全局红条
- 下一次请求成功后红条消失，于是表现为“循环 Failed to fetch，然后突然好了”

## 本轮代码改动

### 1. 后端实时事件归一化

文件：

- `src/qq_data_analysis/llm_session_service.py`

改动：

- 修复 active subscriber 收到原始 `events.jsonl` 事件的问题
- 实时队列现在投递 `_build_stream_event(...)` 后的前端事件
- 前端现在能收到 `message`、`message.delta`、`response.completed` 等监听列表内的事件名

验证：

- mock stream 实测输出：
  - packet/tool/prompt: `event: message`
  - token: `event: message.delta`
  - completion: `event: response.completed`

### 2. mock 流节奏参数

文件：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`

改动：

- `start_mock_session(...)` 新增 `delay_scale`
- `/api/review/llm/session/mock-start` 支持 `delayScale` / `mockDelayScale`
- 只影响 mock session，真实 liverun 不受影响

用途：

- 前端验收时可以用 `delayScale: 4` 或 `5` 拉长输出节奏，方便肉眼观察实时 UI。

### 3. 前端瞬时错误抑制

文件：

- `apps/review-editor/src/App.vue`

改动：

- 新增 `llmSessionFetchFailureCount`
- `fetchLlmSessions()` 连续失败达到 `VISIBLE_LLM_SESSION_FETCH_FAILURES = 3` 后才显示红条
- 一旦请求成功，失败计数清零
- live stream 的 `onError` 不再直接写 `llmSessionError`
- live stream 断线时只关闭旧 EventSource 并调度 refresh，让 registry/polling 接管恢复

设计意图：

- API 重启、session 刚创建、SSE reconnect 等短暂窗口不再刷全局红条
- 后端真正长期不可用时，连续失败后仍会显示错误

## 后续 CC 注意事项

如果继续重构 `LLM Sessions` UI，请保留这些行为：

- 不要把每一次后台 polling 失败都升级成全局红条
- live stream 断线应优先走静默 reconnect / refresh
- 只有用户主动操作失败或连续后台失败，才应该显示明显错误
- SSE event names 要覆盖 `message`、`message.delta`、`response.completed`

## 已知环境问题

当前项目 `.venv` 里 `pytest` 启动失败：

- `ModuleNotFoundError: No module named 'iniconfig'`

因此本轮后端用 `py_compile` 和实际 API/SSE 行为验证；pytest 需要先补齐 `.venv` 依赖后再跑。
