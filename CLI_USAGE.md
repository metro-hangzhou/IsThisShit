# CLI Usage

适用对象：已经有一点开发环境基础、知道如何启动 NapCat 的使用者。

## 启动

分享包内推荐直接双击：

```text
start_cli.bat
```

默认会优先尝试在 Windows Terminal 中打开 CLI。
如果你明确想留在当前经典控制台，可先设置：

```cmd
set CLI_AUTO_WT=0
```

如果你已经知道当前终端容易错位，也可以直接双击：

```text
start_cli_compat.bat
```

它会：
- 禁用自动跳转到 Windows Terminal
- 直接强制 `compat` 显示模式

源码仓库或 `main` 运行分支内推荐也直接双击：

```text
start_cli.bat
```

如果仓库内已带便携运行时，启动脚本会优先自动使用：

- `python_runtime/`
- `runtime_site_packages/`

只有这些都不存在时，才需要本机 Python。

如果你更希望自己维护本地虚拟环境，也可以手动执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

也可以手动：

```powershell
python app.py
```

如果终端显示错位，可优先尝试：

```powershell
python app.py --ui compat
```

进入后是 slash REPL。顶层命令都必须以 `/` 开头。

排查问题时优先看：

- `state/logs/cli_latest.log`
- 导出相关问题再一起看同级 `*.manifest.json`

## NapCatQQ 维护说明

`NapCatQQ/` 作为独立上游项目单独维护，不跟随当前仓库分支一起追踪。

当前约定：

- 当前仓库只负责 exporter 和 vendored `NapCat/` 运行面
- `NapCatQQ/` 保持为独立 checkout，方便后续继续合并上游更新
- 当 QQ 更新导致旧版 `NapCatQQ` 不兼容时，需要在 `NapCatQQ/` 那边单独同步上游并合并到我们的自定义分支

## NapCat 配置说明

仓库会自带最小通用 NapCat 配置，保证新 clone 后默认启用：

- `napcat-plugin-builtin`
- `napcat-plugin-qq-data-fast`

但账号级和机器级配置仍然是本地生成的，不会跟随 Git 分支同步：

- `NapCat/config.json`
- `NapCat/napcat/config/webui.json`
- `NapCat/napcat/config/onebot11_*.json`
- `NapCat/napcat/config/napcat_protocol_*.json`
- `NapCat/napcat/config/napcat_*.json`

## 基本流程

1. `/login`
2. `/groups` 或 `/friends`
3. `/watch ...` 做实时/历史查看
4. `/export...` 导出数据

## 常用命令

```text
/help
/login
/groups [keyword]
/friends [keyword]
/watch group <群名或群ID>
/watch friend <好友名或QQ号>
/export group <目标> [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export friend <目标> [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export group_asBatch=<群1,群2,...> [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export friend_asBatch=<好友1,好友2,...> [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export_onlyText ...
/export_TextImage ...
/export_TextImageEmoji ...
/quit
```

`/watch` 模式内可用：

```text
/export [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export_onlyText [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export_TextImage [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/export_TextImageEmoji [time-a time-b] [data_count=NN] [asTXT|asJSONL]
/exit
```

## 目标补全

- 输入 `/watch ` 或 `/export ` 后会补全 `group` / `friend`
- `/export ` 也会补全 `group_asBatch=` / `friend_asBatch=`
- 输入目标名时支持模糊匹配和拼音匹配
- batch 模式里用英文逗号 `,` 分隔多个目标，逗号后会继续弹下一项补全
- `Up` / `Down` 选候选
- `Tab` / `Enter` 接受补全

## 时间表达式

支持两类：

```text
2026-03-07_14-00-21
@final_content
@earliest_content
@final_content-7d-5h-30s
```

说明：

- 两个时间点组成闭区间
- 顺序无所谓，程序会自动处理
- 显式日期支持单数字写法，例如 `2026-3-9_00-00-00`
- 不给时间区间时，默认按最新消息向前导出

## data_count

`data_count=NN` 或 `--data-count NN` 表示只取最近 `NN` 条消息。

规则：

- 不给时间区间：从 `@final_content` 向前跨页取 `NN` 条
- 给了时间区间：在该闭区间内，从最晚消息向前取 `NN` 条
- 不给 `data_count`：按原逻辑导出整个区间

## 导出变体

`/export`

- 保留全部已支持的标准化 segment

`/export_onlyText`

- 只保留文本

`/export_TextImage`

- 只保留文本和图片

`/export_TextImageEmoji`

- 只保留文本、图片、emoji、sticker

默认导出格式是 `TXT`。末尾加：

- `asTXT`
- `asJSONL`

即可显式指定格式。

## 导出结果

导出后会生成：

- 数据文件：`*.txt` 或 `*.jsonl`
- manifest：`*.manifest.json`
- 资源目录：`<stem>_assets/`

资源目录会尽量 materialize：

- 图片
- 视频
- 语音
- 上传文件
- 表情包静态/动态资源

导出完成后 CLI 会打印摘要，包括：

- 实际导出消息数
- 源消息数
- 请求的 `data_count`
- 各 segment 类型计数
- 各资源类型的 expected / actual / missing / error

说明：

- 顶层 CLI 和 `/watch` 内部都会显示阶段性导出进度
- 顶层 CLI / batch 导出的阶段性进度会原地刷新，不会把终端刷满
- 顶层 CLI 会打印更完整的多行摘要
- `/watch` 模式里顶部只显示短结果通知，底部显示紧凑摘要；详细分项仍然写入 manifest

## 常用例子

最新 200 条纯文本好友聊天：

```text
/export_onlyText friend 菜鸡 data_count=200
```

导出某群最近 300 条图文消息：

```text
/export_TextImage group 蕾米二次元萌萌群 data_count=300
```

批量导出多个群最近 100 条：

```text
/export group_asBatch=蕾米二次元萌萌群,哈基米开发群,悦之声女子计算机学院 data_count=100
```

批量导出多个好友在指定闭区间内的消息：

```text
/export friend_asBatch=菜鸡,阿明 2026-3-09_00-00-00 2026-3-10_00-00-00 asJSONL
```

导出某好友过去 7 天的图文+表情消息：

```text
/export_TextImageEmoji friend 菜鸡 @final_content-7d @final_content asJSONL
```

在 watch 模式里导出当前会话最近 150 条：

```text
/export data_count=150
```

在 watch 模式里只导出当前会话最近 120 条图文：

```text
/export_TextImage data_count=120
```

## 调试建议

- 先用 `/watch ...` 确认目标是否正确
- 先小范围用 `data_count=50` 或 `data_count=100` 试导
- 资源找回率看 manifest，不要只看数据文件
