# Git 分支治理计划

对应 canonical 英文文件：

- [git_branching_plan.md](git_branching_plan.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_branching_slice_20260327/source_snapshot/git_branching_plan.md`

## 这份文件在 cleaned 结构里的角色

它不是一般开发 TODO，也不是稳定 handbook。

它是：

- `branching report / governance plan`

所以它被放进：

- `dev/reports/branching/`

## 它当前最重要的职责

1. 说明 `full-dev / main / runtime` 的角色分工
2. 固定 release sync 的 bundle 思维
3. 固定 launcher / runtime 的分支行为
4. 作为分支治理的长期计划面

## 相关运行手册

- [CLIUsage.zh-CN.md](/d:/Coding_Project/IsThisShit/dev/handbooks/runtime/CLIUsage.zh-CN.md)

## 当前最关键的治理结论

- `full-dev`
  - 本地开发主线
  - 默认不推远端
- `main`
  - operator-facing release branch
  - 可以 auto-update
- `runtime`
  - runtime/release companion branch
  - 要和 `main` 保持功能对齐

## 为什么不继续放在 `dev/documents/`

因为它和：

- [branch_sync_incidents.zh-CN.md](branch_sync_incidents.zh-CN.md)
- [GitBranch_AGENTs.md](/d:/Coding_Project/IsThisShit/dev/agents/GitBranch_AGENTs.md)

共同构成一个明确的 branching / release 面，应该在结构上收束到一起。
