# Shi CLI 草案

这份文件记录未来面向用户的 shi 分析 CLI facade 方向。

## 状态

当前只是草案。

不属于本阶段实现范围。

## 产品语言

未来 REPL 的用户侧命令语言，预期优先采用更抽象的 slash 命令：

- `/sniff`
- `/eatShit`
- 预留 `/autopsy`

## 边界

- exporter 继续独立
- analysis core 继续独立
- CLI 只做未来的 orchestration facade
- 即使 REPL 命令文本偏黑话，内部 handler / schema 仍应保持正式与稳定

## 当前非目标

- 本阶段不实现这些命令
- 不把新的 CLI 命令耦合进 exporter 或 analysis 内核
