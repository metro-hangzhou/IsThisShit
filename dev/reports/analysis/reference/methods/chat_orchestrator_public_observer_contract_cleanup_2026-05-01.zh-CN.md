# Chat Orchestrator Public Observer Contract Cleanup - 2026-05-01

## 背景

前端 ORCH Observer 已经能展示 session 流，但此前后端仍把 worker/工具内部字段直接透传到公开 timeline，例如：

- `message_probe_count=...`
- `anchor_count=...`
- `selected_message_count=...`
- `fetch_topic_cluster_slice`
- `coverage_scope=sender_history:...`
- `derived_hints=["message_count=..."]`

这些字段适合作为 Raw/Inspect 调试信息，不适合作为主线用户可读内容。ORCH 主线应当由后端先给出稳定的人类可审查语义，再由前端渲染。

## 本次改动

### ToolObservation 增加公共观察字段

`src/qq_data_analysis/orch/state.py`

新增字段：

- `display_title`: 主线展示标题，例如“同发送者上下文已返回”。
- `display_summary`: 主线展示摘要，例如“已返回 2 条同发送者聊天记录，用于复核这条判断是否延续同一立场。”
- `target_message_uid`: 本次补证围绕的锚点消息。
- `result_kind`: `messages` / `assets` / `empty` / `boundary` 等结果类型。
- `public_counts`: 人类可读层可以使用的计数，例如 `message_count`、`asset_count`、`missing_asset_count`。

旧字段 `tool_name`、`coverage_scope`、`derived_hints` 保留，只允许 Raw/Inspect 和兼容逻辑使用。

### 工具运行时输出公共摘要

`src/qq_data_analysis/orch/tool_runtime.py`

已为当前内置工具补充公共摘要：

- `expand_window`: 上下文窗口已返回。
- `fetch_reply_chain`: 回复链已返回。
- `fetch_related_assets`: 媒体资源检查已返回，缺失媒体默认是信息边界。
- `fetch_shared_object_context`: 同对象上下文已返回。
- `fetch_sender_history_slice`: 同发送者上下文已返回。
- `fetch_topic_cluster_slice`: 相关话题证据已返回。
- `fetch_forward_tree`: 转发结构已返回。
- disabled external tools: 外部检索未启用。

### Worker prepared summary 改为人类可读

`src/qq_data_analysis/orch/workers/shi_analysis.py`

`build_prepared_summary()` 不再拼接 raw counter 字段，改成自然语言摘要：

```text
窗口内共有 ...；已选 ... 条聊天记录；... 个核心候选锚点；... 条消息探针；... 个媒体缺口仅作为信息边界。
```

同文件的工具观察汇总和 `external_context_notes` 也改为优先使用公共摘要，避免将 `derived_hints` 中的内部标记直接推到主线报告。

### 模型输入包使用公共工具摘要

`src/qq_data_analysis/orch/context_runtime.py`

`tool_results` dynamic section 不再写：

```text
- fetch_sender_history_slice: sender_history_loaded, message_count=...
```

改为：

```text
- 同发送者上下文已返回: 已返回 2 条同发送者聊天记录，用于复核这条判断是否延续同一立场。
```

### Session service 优先使用公共摘要

`src/qq_data_analysis/llm_session_service.py`

`tool.completed` 语义快照现在优先读取：

- `observation.display_title`
- `observation.display_summary`

若旧 session 没有这些字段，继续走历史兼容逻辑。

## 当前边界

- 这次没有删除旧字段，因为历史 session、Raw/Inspect、已有测试仍依赖它们。
- 这次没有继续重构前端 UI。前端应只把新增 public 字段当主线数据源。
- 这次没有改变模型最终报告 schema，只收束 ORCH 公开 observer 事件和模型 context packet。

## 验证

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_chat_orchestrator_runtime.py tests\test_llm_session_service.py -q --basetemp .pytest_tmp_orch_contract
```

结果：`44 passed`

已运行：

```powershell
.\.venv\Scripts\python.exe -m py_compile src\qq_data_analysis\orch\state.py src\qq_data_analysis\orch\tool_runtime.py src\qq_data_analysis\orch\workers\shi_analysis.py src\qq_data_analysis\orch\context_runtime.py src\qq_data_analysis\llm_session_service.py
```

结果：通过。

## 后续主线建议

1. 继续检查 `final_review` schema 是否还有 worker-private/debug 字段进入主线展示。
2. 将 relation graph 的后端数据继续收束为可审查的 source-relation-target 结构，而不是只给前端自然语言摘要。
3. 在真实 live run 上验证 session timeline 不再出现 raw counter 和 raw tool name 主线展示。
4. 前端后续只应使用 `display_title/display_summary/public_counts/result_kind` 做主线渲染，`tool_name/coverage_scope/derived_hints` 仅放 Raw/Inspect。
