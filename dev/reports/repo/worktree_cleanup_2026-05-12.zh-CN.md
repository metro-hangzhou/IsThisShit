# Worktree cleanup report - 2026-05-12

## 当前结论

当前工作树不是单一功能改动，而是多条开发线叠在一起：

- ORCH / Agent 主线：`src/qq_data_analysis/` 下 Benshi、LLM session、ORCH runtime、group aggregation、result contract 等。
- Review Editor：`apps/review-editor/` 是一套新增 Tauri/Vue 工程及 LLM Sessions UI。
- QQ exporter / NapCat：`src/qq_data_core/`、`src/qq_data_cli/`、`src/qq_data_integrations/napcat/`、`NapCat/napcat/plugins/napcat-plugin-qq-data-fast/` 有真实改动。
- 文档重排：`dev/agents/`、`dev/reports/`、`dev/todos/`、`dev/documents/` 大量迁移和新增。
- 测试矩阵：新增/修改了大量 pytest 和前端 vitest 覆盖。

整理前未跟踪项约 6432 个；补充忽略规则后，未跟踪项降到约 740 个。剩余未跟踪项主要是源码、文档、测试和 review-editor 工程本体，不能当作垃圾清理。

## 已做整理

已更新根目录 `.gitignore`，继续遵守根锚定规则，新增忽略：

- 本地 agent 配置：`/.claude/`、`/.codex`
- 测试临时目录：`/.pytest_*/`、`/pytest-cache-files-*/`、`/Coding_ProjectIsThisShit.tmppytest_basetemp/`
- 文件型临时文件：`/.tmp*`
- 本地运行依赖：`/runtime_site_packages/`
- Review Editor 构建/依赖产物：`/apps/*/node_modules/`、`/apps/*/dist/`、`/apps/*/state/`、`/apps/*/.vite/`、`/apps/*/coverage/`、`/apps/*/src-tauri/target/`
- NapCat 本地运行产物：`/NapCat/napcat/config/`、`/NapCat/napcat/static/assets/`
- 根目录备份包：`/*.zip`
- 本地反馈/抓取材料：`/review_editor_human_feedback_list/`

这一步只降低状态噪音，没有删除源码、文档或测试文件。

## 当前剩余状态

### Tracked 修改

`git ls-files -m` 约 244 个文件；但 `git diff --ignore-space-at-eol --stat` 后真实改动主要集中在约 96 个文件，说明部分 tracked 文件存在行尾/格式噪音。

主要真实改动集中在：

- `src/qq_data_analysis/`
- `src/qq_data_cli/`
- `src/qq_data_core/`
- `src/qq_data_integrations/napcat/`
- `src/qq_data_process/`
- `scripts/`
- `tests/`
- `dev/`

### Tracked 删除

当前有 5 个 tracked 删除：

- `TODOs.md`
- `dev/INDEX.md`
- `dev/todos/analysis_window_selection_review.txt`
- `dev/todos/benshi_master_agent_review.txt`
- `loadNapCat.js`

这些可能是文档迁移或 runtime 入口迁移造成的，但提交前必须逐个确认替代位置，不能直接默认为可删。

### Untracked 新文件

忽略规则收敛后，剩余约 740 个未跟踪项：

- `apps/review-editor/`：约 106 个，属于新增前端/Tauri app 本体。
- `src/qq_data_analysis/`：约 41 个，包含 `llm_sessions/`、`orch/`、review projection/closure 等。
- `tests/`：约 41 个，新测试矩阵。
- `scripts/`：约 34 个，新脚本和脚本索引。
- `dev/reports/` / `dev/plans/` / `dev/agents/`：大量新文档和交接/审查材料。

这些是功能资产，不应清理。

## 风险点

1. 当前分支是 `full-dev`，但显示 `origin/full-dev [gone]`。提交或推送前需要重新确认远端分支策略。
2. `NapCat/napcat/node_modules/...` 有 tracked 修改。由于这些是 vendored runtime 文件，不应和 exporter/ORCH 业务提交混在一起。
3. `NapCat/napcat/static/index.html` 和 `NapCat/napcat/static/assets/` 分属 tracked/untracked runtime 构建结果，提交前要确认是否属于 runtime bundle sync。
4. 大量旧文件可能只是行尾变化。正式拆提交前建议先做一次 line-ending 审计，避免把无意义整文件 diff 混进业务提交。
5. `apps/review-editor/src/components/LlmSessionPage.vue.bak-codex` 是备份文件，应在确认无用后删除或移出提交范围。

## 建议拆分提交

1. Repo hygiene：`.gitignore`、工作树整理报告、必要的索引文档。
2. Review Editor app：`apps/review-editor/`，包含前端、Tauri、UI tests。
3. LLM Session backend：`src/qq_data_analysis/llm_sessions/`、`llm_session_service.py`、server 脚本、相关 tests。
4. ORCH runtime and contracts：`src/qq_data_analysis/orch/`、model result / budget / compact / relation graph 相关测试。
5. Benshi agent result contract：`benshi_*`、prompt/result schema、judgment policy 相关测试。
6. QQ exporter / NapCat media fixes：`src/qq_data_core/`、`src/qq_data_cli/`、`src/qq_data_integrations/napcat/`、NapCat fast plugin。
7. Documentation re-layout：`dev/agents/`、`dev/reports/`、`dev/todos/`、`dev/documents/`。
8. Runtime/vendor decision：单独处理 `NapCat/napcat/node_modules`、`NapCat/napcat/static`、tracked runtime bundle 变化。

## 下一步整理顺序

1. 先确认 5 个 tracked 删除是否都有替代位置。
2. 再把 `apps/review-editor/src/components/LlmSessionPage.vue.bak-codex` 这类备份文件排除或删除。
3. 对 tracked NapCat runtime/vendor 修改做独立审计，不和 ORCH/Editor 提交混合。
4. 对 `git diff --ignore-space-at-eol` 仍存在的 96 个真实改动按上面的提交组分批验证。
5. 每组提交前只跑对应最小测试集；最终合并前再跑全量 pytest / review-editor vitest / Tauri build。

