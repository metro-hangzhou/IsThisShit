# NapCat Runtime 状态与插件面

> 日期：2026-03-27
> 范围：把本地 `NapCat/` runtime 里的 mutable state、plugin surface、repo-owned launch/state bridge 再拆细一层。

## mutable state 图

### `NapCat/napcat/config/`

当前实际看到的配置面包括：

- `napcat.json`
- `napcat_<uin>.json`
- `napcat_protocol_<uin>.json`
- `onebot11_<uin>.json`
- `plugins.json`
- `webui.json`
- `config/plugins/`

含义：

- 这是 operator/runtime 配置层
- 它是本机可变的
- 应被当成当前运行态，而不是仓库级制度文本

### `NapCat/napcat/cache/`

当前可见的本地缓存至少包括二维码/登录类缓存。

含义：

- 这是临时 runtime cache
- 有诊断价值
- 不是 canonical repo state

### `NapCat/napcat/logs/`

含义：

- 这是 vendored runtime 自己的日志落点
- 它和父仓库侧的 `state/napcat_logs/` 不是一回事

## plugin surface

### 当前随 runtime 存在的插件

当前可见插件目录：

- `napcat-plugin-builtin`
- `napcat-plugin-qq-data-fast`

维护含义：

- `napcat-plugin-builtin`
  - 更像 upstream/runtime reference surface
  - 主要是插件行为样板
- `napcat-plugin-qq-data-fast`
  - 与本仓库 exporter 直接相关
  - 是 repo-relevant integration surface

### plugin 配置镜像面

当前可见的配置镜像：

- `NapCat/napcat/config/plugins/napcat-plugin-builtin/`
- `NapCat/napcat/config/plugins/napcat-plugin-qq-data-fast/`

含义：

- plugin 代码和 plugin 配置是两层不同表面
- 诊断插件问题时要区分：
  - 路由代码不存在
  - 配置没开/配错
  - 改完代码但进程没重启

## generated artifact surface

### `node_modules/`

含义：

- 打包依赖负载
- 变化多，但设计信号很弱
- 除非证据明确指向依赖/打包漂移，否则不要先扎进去

### `static/`

含义：

- WebUI 构建产物层
- 除非任务明确是 WebUI packaging / runtime frontend，否则默认当 generated runtime artifact 看

### `native/`

含义：

- runtime-native 支撑二进制
- 更像打包/启动问题线索，不是普通 exporter 语义线索

## 父仓库侧 launcher / state bridge

### 启动入口

- [start_napcat_logged.bat](../../../start_napcat_logged.bat)

它做的事：

- 定位 vendored launcher
- 在可用时注入 quick-login UIN
- 把 repo-side 日志指针写到 `state/napcat_logs/`
- 必要时通过提权 wrapper 启动 NapCat

### 重启 helper

- [restart_napcat_service.ps1](../../../restart_napcat_service.ps1)

它做的事：

- 识别 repo-scoped 的 NapCat/QQ 相关进程
- 停掉这些进程
- 需要时再重启 launcher

### repo-side 状态

- `state/napcat_logs/`
- `state/config/napcat_quick_login_uin.txt`

含义：

- 这是父仓库自己维护的 operator state
- 它不属于 upstream NapCat source truth

## 操作规则

- 改 plugin 代码之后，必须做真实 NapCat 重启，新路由才会生效
- config drift、launcher drift、plugin-code drift 是三类不同故障
- 遇到 repo/runtime 耦合问题时，先看：
  - launcher bridge
  - plugin 是否存在/是否启用
  - 是否真的完成重启
  - 再进入更深层 runtime/source 阅读
- 不要把 runtime logs/cache 当成 handbook policy 的替代品
