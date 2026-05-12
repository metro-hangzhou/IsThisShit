# Claude Code Headless Session Note

Date: 2026-04-26

Codex 通过本地 Codex history 还原了此前 Claude Code 的 headless 调用方式。

## 已确认历史命令形态

此前实际使用的是 Windows 宿主机上的 Claude Code：

```powershell
claude -r c9ed3fca-c2fb-48fb-bd28-687eadd7c8c0 --fork-session -p $prompt --model "claude-opus-4.6-fast[1m]" --effort max --output-format stream-json --verbose --permission-mode acceptEdits
```

其中 `-p` 是 `--print` 的短参数。

## 当前持久 session 选择

后续本 lane 固定复用：

```text
07ecedd6-81cc-4f63-bdc6-d3050bfd9e56
```

原因：

- 它是此前 `c9ed3fca...` fork 后承接 LLM Sessions UI 修复的最新项目 session。
- 该 session 最新上下文包含 `llmSessionChatPacketAdapter`、`LlmSessionChatPacketCard` 等 UI 修复记录。
- 用户已经要求不要每个任务重新 fork；因此后续不再使用 `--fork-session`，而是 `claude -r 07ecedd6... -p <prompt>`。

## 后续固定调用模板

```powershell
cd D:\Coding_Project\IsThisShit
$prompt = Get-Content -Raw -Path .tmp\<prompt-file>.md
claude -r 07ecedd6-81cc-4f63-bdc6-d3050bfd9e56 -p $prompt --model "claude-opus-4.6-fast[1m]" --effort max --permission-mode acceptEdits --output-format stream-json --verbose
```

## 协作纪律

- 不再为普通 UI 任务创建新的 Claude Code session。
- 先做阅读理解，再改代码。
- Codex 负责审查 Claude Code 输出、diff、测试结果。
- 如果 Claude Code 多次跳过文档或误解契约，暂停任务并上报用户。
