# Review Editor `LLM Sessions` UI Round 1 Findings

## 目的
这一轮不是继续凭截图和口头反馈磨 UI，而是基于真实采样结果先固定问题，再按问题做第一轮重构。

本轮依据：
- ChatGPT Web 真实只读 capture：
  - [state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z)
- Review Editor `LLM Sessions` 真实只读 capture：
  - [state/ui_reference/review_editor_sessions/2026-04-19T18-52-33.152Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/review_editor_sessions/2026-04-19T18-52-33.152Z)
- 结构化 diff：
  - [2026-04-19T19-05-32.291Z_ui_reference_diff.md](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/diff_reports/2026-04-19T19-05-32.291Z_ui_reference_diff.md)

说明：
- 当前 ChatGPT capture 抓到的是首页/空对话态，不是已进入某条历史会话后的回答态。
- 但它仍然足以作为这一轮的骨架基线：
  - 左栏样式
  - 主区留白
  - 顶部 chrome 密度
  - composer 位置与高度
  - 页面整体“非控制台化”程度

## 真实差异
### 1. 当前页面仍然太像“调试控制台”
真实 diff 已明确暴露两个高偏差指标：
- strong-card count：`21` vs `3`
- chip count：`52` vs `6`

这不是单个气泡大小的问题，而是整页信息架构错误：
- 顶部有太多状态胶囊
- transcript 前有 session intro 卡
- 每条消息都附很多 chips / meta
- packet/tool 仍然偏“独立卡片块”

结论：
- 当前页面的第一视觉锚点是“卡片和标签”
- 而不是“对话本身”

### 2. transcript 仍然不是普通 AI 对话流
当前 transcript 的阅读路径是：
- 先看大标题
- 再看状态 chips
- 再看 intro 卡
- 再看 user card
- 再看 system/tool/packet 卡

ChatGPT Web 的阅读路径则是：
- 页面几乎不抢注意力
- 直接进入中央主列
- transcript 本身成为主视觉
- composer 贴底且极简

结论：
- 当前 `LLM Sessions` 的主区仍然是“台面 + 调试块”
- 而不是“聊天流 + 附加操作痕迹”

### 3. composer 明显过厚
真实 diff：
- composer height：`208px` vs `56px`

问题不是单纯 textarea 大，而是：
- source picker 占位太重
- 输入栏是表单区，不是聊天输入栏
- hint 文本也在放大底部区域

目标：
- 变成 ChatGPT 风格的底部主输入栏
- source 选择作为功能气泡内嵌
- picker 变成弹出层，不占主布局高度

### 4. 左栏仍然太像卡片列表，而不是会话 rail
当前左栏的问题：
- 每个 item 都是厚边框大卡
- 每项上下间距和内边距过大
- 信息层级像 admin 列表，而不是聊天历史列表

ChatGPT Web 左栏特征：
- rail 更平
- item 更薄
- hover/active 主要靠底色，不靠强边框
- 会话列表自身不抢主区视觉

### 5. assistant / system / tool 没有形成正确层级
当前页面里：
- `user`
  - 蓝色大 bubble
- `assistant/system`
  - 仍有大量卡片感
- `tool`
  - 是卡片或次卡片，不像操作轨迹

更合理的层级应该是：
- `user`
  - 右侧 bubble
- `assistant final`
  - 左侧主阅读正文，弱卡片或无卡片
- `thinking`
  - 折叠块
- `tool / prompt / packet`
  - 工程操作行 + 可折叠详情
- `system`
  - 最弱，只作状态提示

### 6. 顶部 chrome 太厚
当前 sessions 页顶部还有：
- 大标题
- subtitle
- 状态胶囊
- 多枚统计 chip
- reload 按钮

它们加起来形成了明显的“console header”。

这一层必须收缩到：
- 小标题
- 一个状态
- 一枚轻量 reload

统计信息不再顶在 transcript 之前。

## 第一轮重构动作
### A. 页面骨架
- 保留左 rail + 中心 transcript + 底部 composer 三段式
- 删除 `session-stage__meta` 这整条 chips 区
- 删除大面积 session intro 卡，把 source 摘要改成 transcript 顶部的一行弱提示
- 缩小主区 header，把它变成轻量 session title bar

### B. 左 rail
- item 改成薄面板，不再用厚边框卡片
- active 态改成背景高亮 + 极轻边界
- 压缩 subtitle / preview / meta 的行高和留白

### C. transcript
- assistant 最终回答去卡片化，改成更接近普通回答正文
- system 消息改成弱提示块
- tool 调用改成操作行
- packet/prompt 改成折叠数据卡，默认收起
- user bubble 缩小，避免“蓝色大板砖”

### D. composer
- 改成真正的单条主输入栏
- source picker 只作为功能气泡存在
- picker 打开时浮在输入栏上方，不增加 composer 主高度
- 删除底部 hint 行

### E. 顶部
- 标题区极简化
- 统计 chips 移除
- reload 保留但弱化

## 第一轮不做的事
- 不在这一轮里把整个 app shell 改成完全等同 ChatGPT Web
- 不在这一轮里引入右侧 inspector
- 不在这一轮里解决所有 Claude Code 风格 tool timeline 动效
- 不在这一轮里重做数据模型，只重做显示层级与骨架

## 通过标准
第一轮重构完成后，应至少满足：
- 第一眼看上去更像“聊天产品”，不再像调试后台
- transcript 的主注意力高于 chips/card
- composer 明显变薄，接近 ChatGPT 风格底部输入
- 左 rail 明显更平
- tool / packet / system 的视觉层级低于 user / assistant 对话本身
