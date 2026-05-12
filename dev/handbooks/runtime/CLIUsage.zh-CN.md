# CLI 使用手册

对应 canonical 手册：

- [CLIUsage.md](CLIUsage.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_runtime_slice_20260327/source_snapshot/CLI_USAGE.md`

## 这份文件的角色

它是：

- runtime handbook
- operator-facing usage manual

不是：

- repo 入口文档
- runtime profile 报告

## 为什么从根目录迁出

因为 `CLI_USAGE.md` 的职责是：

- 教用户怎么启动
- 怎么登录
- 怎么 watch / export
- 怎么看输出与 manifest

这属于典型的 `runtime handbook`，不该继续放在根目录和平面文档一起混着长。
