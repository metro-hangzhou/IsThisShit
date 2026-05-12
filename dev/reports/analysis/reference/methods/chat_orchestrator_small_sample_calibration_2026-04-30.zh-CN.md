# Chat Orchestrator Small-Sample Calibration - 2026-04-30

## 目的

本轮不是做大规模评分，而是验证 ORCH 本体在真实 materialized review run 上是否满足当前技术路线：

- message-first probes 先看 QQ 原文消息与素材本体。
- relation graph 只表达可解释的证据关系，不把普通共现当成关系。
- worker 依据 evidence gap 补工具，不在已经有关系证据时重复发工具。
- 没有核心对象时必须停在 `insufficient_evidence`，不能为了凑结论而 completed。
- ORCH Observer / review-editor 后续只消费人类可读 public contract；raw/debug 只能留在 Raw/Inspect。

## 样本

输出目录：

```text
.tmp/orch_small_sample_calibration_20260430/
```

本轮覆盖 4 个窗口：

| session | source run | outcome | tools | relation edges | notes |
| --- | --- | --- | --- | ---: | --- |
| `sample_x3c_specific_w1` | `state/group_analysis_runs_message_first_phase4_specific_case/x3c_group_757773326/run_20260417_210641` | `completed` | sender history, topic cluster, assets | 6 | 典型 direct text + missing image boundary。 |
| `sample_763_phase2_w1` | `state/group_analysis_runs_message_first_phase2/amd_guanren_group_763328502/run_20260417_003634` | `uncertain / insufficient_evidence` | expand window, reply chain, topic cluster, shared object | 0 | 无核心对象，应停在不确定。 |
| `sample_712_small_fixed_w1` | `state/group_analysis_runs_message_first_small_one_fixed/amd_guanren_group_712742342/run_20260417_001344` | `completed` | reply chain, shared object, assets | 1 | 小窗口 direct anchor + media boundary。 |
| `sample_712_batch_w1` | `state/group_analysis_batch_runs/20260416_015227/analysis_runs/amd_guanren_group_712742342/run_20260416_015228` | `completed` | topic cluster, shared object, assets, forward tree | 6 | 大窗口多 anchor + media/forward boundary。 |

## 本轮发现并修复的问题

### 1. `fetch_shared_object_context` runtime crash

现象：

- `sample_763_phase2_w1` 和 `sample_712_small_fixed_w1` 初次跑到 shared-object tool 时崩溃。
- 异常是 `NameError: keywords is not defined`。

原因：

- `FetchSharedObjectContextTool.invoke(...)` 的 observation hints 引用了不存在的局部变量。

修复：

- `src/qq_data_analysis/orch/tool_runtime.py`
- observation hints 改为稳定的计数字段：
  - `shared_object_context_loaded`
  - `message_count=<n>`
  - `returned_count=<n>`

### 2. 无核心对象窗口被误完成

现象：

- 某些窗口在所有本地补证工具跑完后仍然没有 core probe，但旧逻辑可能没有剩余 tool request，于是看起来像 `completed`。

正确语义：

- 没有核心对象时，ORCH 不能假装已经判断完成。
- 如果 `expand_window` / `fetch_reply_chain` / topic / shared object 等本地证据都无法形成 core，应输出 unresolved `missing_core_object`，并以 `insufficient_evidence` 停止。

修复：

- `src/qq_data_analysis/orch/workers/shi_analysis.py`
- 当 `core_probes` 为空且可用本地工具已经耗尽时，追加不可自动修复的 `missing_core_object` gap：
  - `suggested_tools=[]`
  - `notes=["core_object_unresolved_after_local_tools"]`

验证：

- `sample_763_phase2_w1` 最新结果：
  - `status=uncertain`
  - `stop_reason=insufficient_evidence`
  - `evidence_gap_types=["missing_core_object"]`

### 3. relation graph same-sender 误报

现象：

- `sample_763_phase2_w1` 的 top probes 基本都是 `[system message]` / `off_target`。
- 旧 `same_sender_continuation` 规则把这些系统噪声之间的连续发送误判成 12 条关系边。

正确语义：

- relation graph 不是消息共现图。
- `same_sender_continuation` 只应表达“同发送者延续同一对象/话题/立场”的证据关系。
- 两端都是 `off_target` 时必须禁止建边。
- 如果一端是 `off_target`，除非存在明确 topic overlap，否则也不应因为“同发送者”自动建边。

修复：

- `src/qq_data_analysis/benshi_message_first.py`
- same-sender 建边逻辑新增约束：
  - 两端都是 `off_target`：直接跳过。
  - 一端是 `off_target` 且无 topic overlap：跳过。

验证：

- 新增测试：
  - `test_message_first_context_does_not_bind_same_sender_noise_without_topic_overlap`
- `sample_763_phase2_w1` 最新 `relation_edge_count=0`。

## 当前验证命令

```text
./.venv/Scripts/python.exe -m pytest tests/test_benshi_message_first.py tests/test_chat_orchestrator_runtime.py -q
```

结果：

```text
24 passed
```

真实小样本命令示例：

```text
./.venv/Scripts/python.exe scripts/run_chat_orchestrator.py \
  state/group_analysis_runs_message_first_phase4_specific_case/x3c_group_757773326/run_20260417_210641 \
  --window-index 1 \
  --output-root .tmp/orch_small_sample_calibration_20260430 \
  --session-id sample_x3c_specific_w1 \
  --objective "small sample calibration: x3c specific case"
```

## 当前判断

本轮 ORCH 本体方向成立：

- direct text anchor 能稳定成为正审对象。
- media missing 保持为 boundary/info，不会单独变成 warning 结论。
- 无核心对象窗口能停在 `insufficient_evidence`。
- relation graph 已经能被 worker 用来减少冗余 tool planning。

但 relation graph 仍是启发式 v1.5，需要继续在更多窗口上校准：

- `same_sender_continuation` 已收窄，但仍需要验证它不会把普通闲聊连续发言误当证据。
- `shared_asset_continuation` 对 image/sticker/file 的意义需要配合前端关系图审阅。
- `local_context` 置信度低，只能作为观察线索，不能作为强判定依据。

## Observer / UI 后续要求

由于 relation graph 已经进入 ORCH contract，review-editor 后续必须支持关系图观察能力：

- 默认展示人类可读关系，而不是 `edge_type` / `message_uid` 原字段。
- 按 anchor 聚合：
  - reply
  - @ binding
  - same sender continuation
  - shared asset continuation
  - nested forward parent/child
  - explicit uptake
  - local context
- 每条关系都要能跳到或展开对应 QQ 原文，QQ 原文使用 PCQQ 风格引用卡。
- relation graph 是 ORCH 调试观察器的核心功能之一，用于判断 agent 为什么认为这些消息属于同一对象/同一推理链。
- 稍重的 UI/UX 设计和交互实现交给 Claude Code；Codex 负责数据契约、边界、测试和验收。

## 下一步

1. 收束 ORCH public observer contract，确保 UI 默认只拿人类可读 event/report 字段。
2. 把 worker-private payload 继续限制在 Raw/Inspect 和 artifacts。
3. 为 relation graph 输出增加稳定 public summary，供 CC 实现前端关系图。
4. 再跑一轮 GPT-5.5 live judge，验证最终 `final_review` 不再依赖 deterministic fallback。
