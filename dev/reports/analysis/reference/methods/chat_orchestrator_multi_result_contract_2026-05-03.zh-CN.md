# Chat Orchestrator Multi-Result Contract - 2026-05-03

## 背景

本轮对齐的核心问题是：ORCH live session 不能继续把模型主审输出设计成单个 `final_review`。

原因：

- Review 页面早期能力本来可以展示多个候选对象 / 多个 shi/topic 结论。
- ORCH Observer 是用来审查模型和工具行为的，如果模型只能输出一个结果，人类无法判断它是主动忽略了其他对象，还是契约限制导致只能写一个。
- `final_review` 这种 legacy 字段会让模型、后端和前端继续落回“单结论”惯性，后续再补 UI 会越补越乱。

## 最新契约

模型主审最终 JSON 必须包含：

```json
{
  "review_results": [
    {
      "result_id": "r1",
      "rank": 1,
      "result_kind": "shi",
      "role": "primary",
      "verdict": {
        "label": "possible",
        "confidence": "medium",
        "summary": "一句人类可读结论",
        "reason": "为什么这么判"
      },
      "core_object": {
        "label": "被审阅对象",
        "summary": "对象是什么",
        "why_it_matters": "为什么值得审"
      },
      "evidence": [],
      "boundaries": [],
      "audit_risks": []
    }
  ],
  "primary_result_id": "r1",
  "adjudicated_relation_graph": {
    "nodes": [],
    "confirmed_edges": [],
    "boundary_edges": [],
    "rejected_edges": [],
    "open_questions": []
  },
  "evidence_acquisition_summary": {
    "tool_calls_made": [],
    "why_enough": "为什么当前证据足够，或为什么仍需要保留边界",
    "remaining_limits": []
  }
}
```

## 规则

- 多对象时输出多条 `review_results`，不要合并成一个混合结论。
- 单对象时也输出长度为 `1` 的 `review_results`。
- `primary_result_id` 指向默认最重要、最应该在 Observer 顶部展示的结果。
- 缺失 asset、普通背景话题、单纯资源状态、无命题闲聊不应硬塞进 `review_results`，应进入边界或审计风险。
- 模型输出只包含 `final_review` / `final_reviews` 时，model-led ORCH 验证器必须拒绝。

## 兼容边界

- `final_review` / `final_reviews` 只允许作为历史 session、旧 materializer 或前端兼容读取字段。
- 验证通过后，后端可以从 `review_results[0]` 派生 `final_review` 给旧消费端，但不能反过来把 legacy 字段当作模型合格输出。
- Prompt 不应出现“旧 UI”、“正式主输出”、“前端”、“PCQQ”、“Raw”、“Inspect”等 UI 或实现侧术语。

## 已落实代码点

- `src/qq_data_analysis/orch/engine.py`
  - `_normalize_and_validate_review_results(...)` 现在强制要求原生 `review_results` 非空数组。
  - legacy `final_review` 不再作为模型输出通过条件。
- `scripts/run_chat_orchestrator.py`
  - 命令行摘要从 `final_review` 切到 `review_results` / `primary_result_id` / `primary_review`。
- `scripts/run_orch_calibration_suite.py`
  - 校准 objective 和报告摘要改为多结果契约。
- `tests/test_chat_orchestrator_runtime.py`
  - fake model 输出切为 `review_results`。
  - 增加 final_review-only 拒绝测试。

## Live 验证记录

- 时间：2026-05-03 16:07-16:09 +08:00
- session：`state/llm_sessions/live_fa21dac7cea3e5`
- 输入：`group_analysis::group_analysis_runs_message_first_phase4_specific_case::x3c_group_757773326::run_20260417_210641`
- 模型原始输出：
  - top-level keys = `review_results`, `primary_result_id`, `adjudicated_relation_graph`, `evidence_acquisition_summary`
  - `review_results.length = 3`
  - `primary_result_id = topic_1`
  - 原始模型 JSON 不包含 `final_review` / `final_reviews`
- 后端验证 / 保存：
  - `result.json -> analysis_output.compact_payload.review_results.length = 3`
  - 验证通过后为旧消费端派生 `final_review` / `final_reviews`，但这不是模型输出通过条件。
  - `/api/review/llm/session/live_fa21dac7cea3e5` 返回 `finalReportPayload.reviewResultCount = 3`，`finalReportViewModel.debug.nativeReviewResults = true`。
  - `finalReportViewModel.schemaVersion = llm_final_report_view_v4`。
  - `finalReportViewModel.resultPages.length = 3`，每页包含一个完整的单对象审阅报告 view model。
  - Review Editor 的最终报告卡片右上角显示 `x/n` 与左右切换按钮；默认第 `1` 页为 `primary_result_id` 对应结果。
- 本轮样本结果：
  - `topic_1`：主审对象，围绕 `265K + Z890 吹雪 / AM5-B650-B850 扩展性` 的平台选择争执。
  - `topic_2`：背景话题，围绕移动平台 / 续航 / Panther Lake 等泛技术讨论。
  - `topic_3`：次级话题，围绕 X670E ProArt 重启、RMA、B850 替代方案。
