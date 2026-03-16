# QQ Data Exporter Runtime Branch

## 中文说明

这个分支是面向运行、验证和更新的 `runtime` 分支。

它保留了运行 QQ 聊天导出器所需的最小文件集合：

- `app.py`
- `src/`
- `NapCat/`
- 启动脚本
- 运行说明文档

它**不包含**主要面向开发者的内容，例如：

- `dev/`
- `tests/`
- 大部分辅助脚本
- 规划与 review 文档
- 分析 / RAG 子系统源码

### 用途

这个分支适合：

- 日常运行导出器
- 朋友或协作者在线更新
- release / debug 运行验证

如果你需要开发、测试、文档、规划和完整工程上下文，请使用维护者本地保留的 `full-dev` 分支。

### 快速开始

1. 准备 Python 环境
2. 保证 `NapCat/` 可正常启动
3. 启动 CLI

推荐直接双击：

```text
start_cli.bat
```

如果当前终端兼容性较差，可使用：

```text
start_cli_compat.bat
```

更详细的运行说明见：

- [CLI_USAGE.md](CLI_USAGE.md)

### 更新方式

如果你已经在本仓库工作目录中：

```powershell
git pull origin runtime
```

### NapCatQQ 说明

`NapCatQQ/` 不由当前仓库跟踪。

原因是：

- 它需要保留独立的上游合并能力
- 我们当前对 `NapCatQQ` 有自定义分支
- 未来 QQ 更新时，可能需要单独同步 `NapCatQQ` 上游更新再合并

因此当前仓库负责的是：

- exporter 代码
- vendored `NapCat/` 运行面

而 `NapCatQQ/` 应继续作为独立 checkout 单独维护。

## English

This is the `runtime` branch for operating, validating, and updating the exporter.

It keeps the minimal runtime surface:

- `app.py`
- `src/`
- `NapCat/`
- start scripts
- runtime usage docs

It intentionally excludes most developer-facing materials such as:

- `dev/`
- `tests/`
- most helper scripts
- planning and review docs
- analysis / RAG subsystems

### Typical use

Use this branch for:

- running the exporter
- collaborator updates
- release/debug validation

For full development work, tests, planning docs, and complete project context, use the maintainer-only `full-dev` branch kept locally.

### Quick start

Run:

```text
start_cli.bat
```

If your terminal host is unstable or visually broken, use:

```text
start_cli_compat.bat
```

See:

- [CLI_USAGE.md](CLI_USAGE.md)

### Updating

```powershell
git pull origin runtime
```

### About `NapCatQQ`

`NapCatQQ/` is intentionally not tracked by this repository.

It must remain a separate upstream-trackable checkout so future upstream merges can still be applied when QQ updates require them.
