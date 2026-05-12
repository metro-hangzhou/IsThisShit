# NapCat Runtime 手册

这份手册记录本仓库围绕 vendored `NapCat/` runtime 的操作规则。

## 范围

这不是 upstream source 手册。

它主要回答：

- 哪些本地 runtime 路径是 operator-managed state
- 哪些文件属于父仓库的 launcher bridge
- 什么情况下 plugin/config 修改后必须做真实重启
- runtime 问题应该先从哪看，而不是一上来就扎进整棵目录树

## 核心规则

- 把 `NapCat/` 视为 vendored runtime shell + mutable local runtime state
- 把 `NapCatQQ/` 视为 upstream/reference source checkout
- 不要把这两棵树都压平成普通父仓库内容
- 以 [start_napcat_logged.bat](../../../start_napcat_logged.bat) 作为 repo-level launch bridge
- 当 plugin/launcher 变更需要干净重启时，用 [restart_napcat_service.ps1](../../../restart_napcat_service.ps1)
- 改了 plugin 代码以后，不要相信旧进程，必须重启 NapCat 才能刷新路由

## 建议配套阅读

- [NapCat_AGENTs.md](../../../NapCat_AGENTs.md)
- [dev/reports/napcat/runtime_surface.zh-CN.md](../../reports/napcat/runtime_surface.zh-CN.md)
- [dev/reports/napcat/runtime_state_and_plugins.zh-CN.md](../../reports/napcat/runtime_state_and_plugins.zh-CN.md)
