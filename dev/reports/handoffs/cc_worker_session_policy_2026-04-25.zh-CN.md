# Claude Code worker session policy

日期：2026-04-25

固定 CC 工作会话：

- session id: `07ecedd6-81cc-4f63-bdc6-d3050bfd9e56`
- project: `D:\Coding_Project\IsThisShit`
- 用途：review-editor `LLM Sessions` / ORCH debugger observer 前端呈现层。

执行约定：

- 后续给 CC 下发同一项目任务时，默认 resume 这个 session。
- 不要每个任务都 `--fork-session`，避免上下文断裂和 session 数膨胀。
- 只有这个 session 明确不可用时，才更换固定 session，并在本文档记录替换原因。

验收顺序：

- UI 开发阶段优先启动 `apps/review-editor` 的 Vite/Vue dev server 自查页面和交互，不要默认先打 Tauri 包。
- 常规自查顺序：`npx vue-tsc --noEmit`、`npx vitest run`、`npm run dev` 实际打开页面检查。
- 只有代码检查、单测、dev server 页面验收都过后，才执行 `npm run build` 或 `npm run tauri:build` 做最终打包验证。
