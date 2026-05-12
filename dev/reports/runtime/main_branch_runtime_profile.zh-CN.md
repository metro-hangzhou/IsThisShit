# main 分支运行画像

对应 canonical 英文文件：

- [main_branch_runtime_profile.md](main_branch_runtime_profile.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_runtime_slice_20260327/source_snapshot/README.md`

## 这份文件的角色

它不是根级 repo entry。

它更准确地说是：

- `main` 分支 runtime profile
- 面向运行/验证/更新的运行画像说明

## 它最关键说明的内容

- `main` 分支适合：
  - 日常运行导出器
  - 协作者更新
  - release/debug 运行验证
- 它保留：
  - `app.py`
  - `src/`
  - `NapCat/`
  - `python_runtime/`
  - `runtime_site_packages/`
  - 启动脚本
  - 运行文档
- 它不负责完整开发上下文

## 对应运行手册

- [CLIUsage.zh-CN.md](/d:/Coding_Project/IsThisShit/dev/handbooks/runtime/CLIUsage.zh-CN.md)

## 为什么从根 README 里拆出来

因为根 README 应该回到：

- 仓库入口
- 路由作用

而不应该继续承担这么大块的 `main` 分支运行画像。
