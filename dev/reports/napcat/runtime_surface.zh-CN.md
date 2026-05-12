# NapCat Runtime 表面图

> 日期：2026-03-27
> 范围：把本仓库里实际存在的 `NapCat/` 目录拆成 runtime shell、mutable state、plugin surface、generated artifacts、repo launch bridge。

## 为什么要有这份文件

`NapCat/` 不是一种东西。

它现在实际混着：

- 打包后的 runtime shell
- 本地可变 runtime 状态
- 与本仓库直接相关的 plugin 代码
- 生成产物级的 `node_modules` / 静态前端资产
- 父仓库连到 NapCat runtime 的启动/重启桥接脚本

如果不先拆表面，后续很容易把：

- cache
- logs
- plugin
- 打包二进制

全都当成同一类对象来处理，最后不是过度清洗，就是盯错位置。

## canonical 分类

### 1. Vendored runtime shell

`NapCat/` 顶层的打包运行壳：

- `NapCat/index.js`
- `NapCat/package.json`
- `NapCat/node.exe`
- `NapCat/napcat.bat`
- `NapCat/*.dll`
- `NapCat/wrapper.node`
- `NapCat/win64/`

含义：

- 这是随仓库放进来的 NapCat 运行壳
- 应视为 vendored runtime payload
- 不应把它当成项目级架构文档或第一阅读入口

### 2. Runtime root

`NapCat/napcat/` 才是本地打包 NapCat 的实际 runtime root。

这里面又混着几类完全不同的表面：

- mutable runtime state
- 启动/引导脚本
- plugin surface
- 生成的 web / node 资产
- native 运行支撑文件

### 3. Mutable runtime state

`NapCat/napcat/` 里真正的本地可变态：

- `cache/`
- `config/`
- `logs/`

含义：

- 它们反映本机 operator / runtime 状态
- 适合诊断
- 不适合作为稳定架构真相

### 4. Plugin surface

与本仓库最直接相关的 plugin 面：

- `NapCat/napcat/plugins/napcat-plugin-builtin/`
- `NapCat/napcat/plugins/napcat-plugin-qq-data-fast/`
- `NapCat/napcat/config/plugins/`

含义：

- 这里才是 `NapCat runtime` 与 exporter 仓库真正耦合最深的一层
- plugin 代码和 plugin 配置是 repo-relevant integration surface

### 5. Generated runtime artifacts

生成/打包产物层：

- `NapCat/napcat/node_modules/`
- `NapCat/napcat/static/`
- `NapCat/napcat/native/`

含义：

- 这是运行时负载或前端/依赖产物
- 不应把它们当成父仓库设计意图的首要线索
- refactor 不应漂到“泛 node_modules / 静态构建噪声”里去

### 6. Repo launcher bridge

父仓库侧的 NapCat 桥接面：

- [start_napcat_logged.bat](../../../start_napcat_logged.bat)
- [restart_napcat_service.ps1](../../../restart_napcat_service.ps1)
- `state/napcat_logs/`
- `state/config/napcat_quick_login_uin.txt`

含义：

- 这些不是 upstream NapCat 内核
- 但它们属于本仓库真正的运行面
- 也是 operator 最先接触的 runtime bridge

## 不该做什么

- 不要把整个 `NapCat/` 平铺地当成普通父仓库源码
- 不要把 `node_modules/` 的漂移当成项目级架构信号
- 不要把 `cache/`、`logs/` 当成 canonical project state
- 不要把 runtime surface 规则只埋在零散 plugin 或 launcher 里

## 这份 surface 的用途

它应该先回答：

- 本地 runtime state 到底在哪
- `NapCat/` 哪些部分只应视为 vendored shell
- 哪些部分才是 repo-owned integration surface
- 遇到 runtime/plugin 问题时，应该从哪里开始看，而不是直接扎进整棵目录树
