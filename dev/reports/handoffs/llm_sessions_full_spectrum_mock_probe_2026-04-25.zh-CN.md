# LLM Sessions Full-Spectrum Mock Probe

日期：2026-04-25

## 目的

在接入真实 orch/data pipeline 前，用一个高覆盖 mock session 验证 `review-editor` 的 LLM Sessions 观察面是否能承载完整运行轨迹：

- 自动发现新 session
- per-session SSE 实时下行
- prompt / packet / raw JSON
- tool requested / completed / failed
- reasoning token stream / content token stream
- 多 asset 展示与 missing asset 折叠
- session materialized review run
- 完成后离线 detail 回看

## 新增 mock 场景

`scripts/start_mock_llm_session.py --asset-scenario full_spectrum`

该场景走现有 `/api/review/llm/session/mock-start`，不新增前端协议。

覆盖内容：

- 3 条输入消息，其中 1 条长文本用于折叠/摘要测试。
- 12 个 asset refs。
- 6 个 renderable assets：image x2、file x1、video metadata x1、speech metadata x1、sticker remote-url x1。
- 6 个 missing assets，用于验证 missing > 2 的折叠显示。
- 3 个 tool request。
- 2 个 tool completed。
- 1 个 tool failed：`hydrate_missing_asset` / `missing_after_napcat`。
- 6 个 token chunk：reasoning x3、content x3。
- `session.materialized_review_run`，用于验证 review bridge 状态字段。

## 实测 session

API 投递：

```powershell
.\.venv\Scripts\python.exe scripts\start_mock_llm_session.py --host 127.0.0.1 --port 43127 --chat-name "FULL SPECTRUM SESSION PROBE" --run-id mock_full_spectrum_20260425 --candidate-id candidate_full_spectrum_001 --chat-id full_spectrum_probe --asset-scenario full_spectrum --delay-scale 4
```

结果：

- session: `mock_916b4bdb65c6ea`
- status: `completed`
- materializedReviewRunId: `mock_916b4bdb65c6ea_review`
- packetCount: 15
- tokenChunkCount: 6

SSE 实时验证：

- session: `mock_86ce0ebd8732e4`
- status: `completed`
- materializedReviewRunId: `mock_86ce0ebd8732e4_review`
- packetCount: 15
- tokenChunkCount: 6

SSE event names:

```text
message: 14
message.delta: 6
session.materialize_started: 1
response.completed: 1
```

SSE event types:

```text
session.mock_plan_created: 1
context.prepared: 1
session.mock_remote_connected: 1
chat_packet.built: 1
prompt.built: 1
tool.requested: 3
tool.completed: 2
tool.failed: 1
judge.started: 1
session.stream_chunk: 6
llm.response_completed: 1
session.materialize_started: 1
session.materialized_review_run: 1
session.completed: 1
```

Packet asset summary:

```json
{"total": 12, "available": 6, "missing": 6, "types": ["file", "image", "speech", "sticker", "video"]}
```

## 已跑验证

```powershell
.\.venv\Scripts\python.exe -m py_compile src\qq_data_analysis\llm_session_service.py scripts\start_mock_llm_session.py
.\.venv\Scripts\python.exe -m pytest tests\test_llm_session_service.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_run_review_editor_server.py -q
cd apps\review-editor
npx vue-tsc --noEmit
npx vitest run
```

结果：

- `tests/test_llm_session_service.py`: 14 passed
- `tests/test_run_review_editor_server.py`: 4 passed
- `apps/review-editor`: 27 vitest tests passed
- `vue-tsc --noEmit`: passed

未跑 `tauri:build`：当前用户正在开着 review-editor 验收页面，未主动关闭 `review-editor.exe`。

## 当前结论

Mock 层已经覆盖原始规划中的核心观察面：prompt、packet、tool、reasoning/content token、asset、missing boundary、materialized review run、SSE 实时下行和离线回看。

可以进入下一步真实数据实测。真实数据实测重点不再是 UI mock 覆盖，而是验证真实 orch 事件是否完整投影为同一套 session 协议，尤其是：

- 真实 `chat_packet.built` 是否带齐 `renderable_assets` / `missing_assets` / `asset_summary`。
- 真实 tool failure 是否进入 `tool.failed` 或等价结构，而不是只落在 raw logs。
- 真实 materialized review run 是否能从 session 跳回 review surface。
