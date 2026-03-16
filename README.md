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

1. 准备 Python 3.13 x64
2. 如需本地 `.venv`，可执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. 保证 `NapCat/` 可正常启动
4. 启动 CLI

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
- [requirements.txt](requirements.txt)

### 更新方式

首次拉取推荐直接指定 `runtime` 分支：

```powershell
git clone -b runtime https://github.com/SH7ship24in2022/IsThisShit.git
```

如果你已经 clone 过仓库，但当前不在 `runtime` 分支：

```powershell
git fetch origin
git switch runtime
git pull origin runtime
```

如果你已经在本仓库工作目录中，后续更新直接执行：

```powershell
git pull origin runtime
```

正常情况下，后续 `git pull origin runtime` 只会增量拉取远端新增或变化的内容，然后自动合并到本地当前分支，不会每次重新下载整个仓库。

需要注意的是：

- 如果远端新增了较大的二进制文件，Git 仍然需要把这些新增对象下载下来
- 如果你本地修改过同一份被跟踪文件，更新时可能出现合并冲突
- 对只运行不改代码的协作者来说，保持本地工作区干净，更新通常会最顺滑

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

### 许可证边界说明

当前仓库后续如果添加开源协议，协议仅覆盖我们自行开发和明确拥有分发权的部分。

第三方内容继续遵循它们各自原始协议，包括但不限于：

- `NapCatQQ/` 的上游协议
- vendored `NapCat/` 中第三方组成部分的原始协议
- `src/pypinyin/` 的原始协议

也就是说：

- 我们不会把第三方代码重新声明为只受我们的协议约束
- 我们会为自研部分和第三方部分明确划分边界
- 后续正式公开前，还需要补一份更明确的第三方许可说明清单

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

For a fresh clone, use the `runtime` branch directly:

```powershell
git clone -b runtime https://github.com/SH7ship24in2022/IsThisShit.git
```

If the repository already exists locally but is not on `runtime`:

```powershell
git fetch origin
git switch runtime
git pull origin runtime
```

For normal updates inside an existing `runtime` checkout:

```powershell
git pull origin runtime
```

Under normal conditions, `git pull origin runtime` only downloads the new or changed objects from the remote and then merges them into the local branch. It does not re-download the whole repository every time.

Practical notes:

- large newly added binaries can still make an update feel heavy
- local edits to tracked files can cause merge conflicts
- for operator-only collaborators, keeping the working tree clean usually makes updates smooth

### Optional dependency install

If you prefer a local virtual environment instead of relying on your global Python installation:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then you can keep using the normal start scripts:

```text
start_cli.bat
start_cli_compat.bat
```

### About `NapCatQQ`

`NapCatQQ/` is intentionally not tracked by this repository.

It must remain a separate upstream-trackable checkout so future upstream merges can still be applied when QQ updates require them.

### License boundary

If an open-source license is added later, it should only apply to the parts we authored and clearly control.

Third-party content must continue to follow its original license terms, including but not limited to:

- the upstream `NapCatQQ/` license
- original licenses of third-party components inside vendored `NapCat/`
- the original `pypinyin` license for `src/pypinyin/`

So the correct approach is:

- do not relabel third-party code as if it were covered only by our project license
- define clear path-level boundaries for our code versus upstream/vendor code
- add an explicit third-party notice file before any real public open-source release
