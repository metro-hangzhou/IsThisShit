# Codex `LLM Sessions` C 任务单

> 日期：2026-04-23  
> 范围：真实 backend / runtime gap  
> 约束：不碰 sessions 前端主显示层文件

## 1. 这轮我负责什么
我这轮只负责 `C`：

- 真实 continue current session
- 正式 replay / resume control plane
- `live review runs` 作为正式 review 数据源
- 如有必要，补 session summary/patch 的 materialized 状态字段

## 2. 当前锁定写集
这轮我只碰 backend/runtime 侧文件：

- `src/qq_data_analysis/llm_session_service.py`
- `scripts/run_review_editor_server.py`
- `src/qq_data_analysis/review_service.py`
- 对应 backend tests / 文档

这轮我不碰：

- `apps/review-editor/src/App.vue`
- `apps/review-editor/src/components/LlmSessionPage.vue`
- `apps/review-editor/src/composables/useTranscript.ts`
- `apps/review-editor/src/api.ts`
- `apps/review-editor/src/types.ts`

原因很直接：
- 这些文件当前交给 Claude Code 做 A+B
- 我要避免和它改同一批文件

## 3. 这轮 C 的正式目标

### C1. continue current session
当前问题：
- UI 会暗示“继续输入当前 session”
- 实际却还是新建 session

这轮 backend 目标：
- 形成真正的 `session/:id/input` 或等价 continue 入口
- 明确多 turn session 的 runtime 语义
- 不再让 continue 只是文案

### C2. replay / resume control plane
当前问题：
- backend 只有 retry-like 与内部 replay 逻辑
- 没有正式用户级 control plane

这轮 backend 目标：
- 明确 replay / resume / retry 的边界
- 给前端留出稳定 control surface

### C3. live review runs discoverability
当前问题：
- live session 已 materialize review packets
- 但 review source discovery 不把 `state/llm_sessions/*` 当成正式 review run source

这轮 backend 目标：
- 让 materialized live session 能被正式 discover
- 形成真正的 live review runs 数据源

### C4. materialized 状态的 summary/patch 暴露
当前问题：
- detail 里有 overlay manifest
- event 里也有 materialized packet
- 但 summary / sessionPatch 未正式暴露 materialized 状态

这轮 backend 目标：
- 如果前端后续需要在 rail / registry 层直接知道 “this session is materialized”
- 那么 summary / patch 要补稳定字段

## 4. 这轮不做
- 不做 sessions 前端视觉重构
- 不改 transcript 表达
- 不在这一轮里同时接前端 UI

如果 backend 新增了字段或接口：
- 我只在文档里写给 CC 怎么接
- 不直接并发去改前端

## 5. 交接给前端的方式
我完成 C 之后，必须额外产出：

1. backend 变更摘要  
2. 新增接口 / 字段说明  
3. 哪些字段需要 `api.ts/types.ts` 接线  
4. 对 CC 的前端接线建议

这样 CC 可以继续在自己的写集里接线，不需要我碰它的文件。
