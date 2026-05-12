# Subrepo split report - 2026-05-12

## Result

已把当前主仓拆出两个非破坏性子仓快照：

- ORCH / Agent: `D:\Coding_Project\isthisshit-orch-agent`
- Review Editor: `D:\Coding_Project\isthisshit-review-editor`

主仓已通过 submodule 引用两个 GitHub 子仓：

- `subrepos/orch-agent` -> `https://github.com/metro-hangzhou/isthisshit-orch-agent.git`
- `subrepos/review-editor` -> `https://github.com/metro-hangzhou/isthisshit-review-editor.git`

当前没有物理删除、移动或替换主仓内原有源码目录。主仓里的 `src/qq_data_analysis`、`src/qq_data_process` 仍由父仓跟踪并保留，后续迁移应在单独步骤中做依赖切换和目录瘦身。

`apps/review-editor/` 已作为本地旧工作副本写入父仓 `.gitignore`。正式 review-editor 源码入口是 `subrepos/review-editor`，后续 UI 修改应优先进入该子仓，避免父仓重复显示未跟踪 app 文件。

## Local commits

ORCH / Agent 子仓：

- commit: `eec267ce1adc1b9fcf86462483ebbe1dedd89796`
- branch: `main`
- remote: `https://github.com/metro-hangzhou/isthisshit-orch-agent.git`

Review Editor 子仓：

- commit: `3f4c54329f496d379e0224acc3a526f2a54d6504`
- branch: `main`
- remote: `https://github.com/metro-hangzhou/isthisshit-review-editor.git`

## GitHub status

WSL-side `gh repo create` failed because that token cannot create repositories:

```text
GraphQL: Resource not accessible by personal access token (createRepository)
```

After switching to Windows-side GitHub CLI through Git for Windows Bash, both private repositories were created and pushed:

```bash
gh repo create metro-hangzhou/isthisshit-orch-agent --private --source /d/Coding_Project/isthisshit-orch-agent --remote origin --push
gh repo create metro-hangzhou/isthisshit-review-editor --private --source /d/Coding_Project/isthisshit-review-editor --remote origin --push
```

Push status:

- ORCH / Agent: pushed to `main`.
- Review Editor: pushed to `main`.
- Main repo `.gitmodules` has been updated to GitHub URLs and synchronized.

Known remote risk:

- ORCH / Agent contains `tests/fixtures/testChatRecord/friend_u_m_XfdvBK9H5Q1MFKNMzfgQ_20260111_104240.json` at about `71.12 MB`.
- GitHub accepted the push but warned that it exceeds the recommended `50 MB` file size.
- Do not remove or rewrite this fixture without explicit approval. If repository size becomes a problem, plan a separate LFS or fixture-thinning migration.

## ORCH / Agent split scope

Included:

- `src/qq_data_analysis`
- `src/qq_data_process`
- minimal `src/qq_data_core/__init__.py` and `src/qq_data_core/paths.py`
- ORCH / Benshi / review packet / judgment policy scripts
- ORCH / Benshi / LLM session / review projection tests
- analysis, ORCH observer, and handoff docs needed for continuity

Known transition debt:

- `qq_data_process` is still copied into ORCH repo because current `qq_data_analysis` imports it directly.
- `run_review_editor_server.py` is included as an adapter for current observer flows, but should eventually be split into a thin backend integration package.
- Some scripts still assume the original main repo `state/` layout.

## Review Editor split scope

Included:

- Vue/Tauri app source
- app-level scripts
- UI tests
- frontend contract and handoff docs copied under `docs/from-main`

Excluded by `.gitignore` / rsync rules:

- `node_modules`
- `dist`
- `state`
- `src-tauri/target`
- `.vite`
- `coverage`
- `*.bak-*`

Known transition debt:

- `tauri-dev.mjs` and Tauri shell still assume the parent repo backend layout.
- Backend remains external at `http://127.0.0.1:43127`.
- Contract synchronization is still implicit through TypeScript types and API client code.

## Operational rule added from incident

Do not use `apply_patch` to delete or move large files. The TUI may render deleted file contents and freeze.

For any future delete/move/cleanup:

- ask for user approval first;
- use shell/native file operations after approval;
- for Windows-side repo work under `/mnt/d`, prefer the `better-ps-cmd-skill` path discipline when command quoting or Windows tooling is involved.
