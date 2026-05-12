# Review Editor `LLM Sessions` UI Round 3 Findings

## 本轮目标
在 round 2 已经收过 app shell、左 rail、transcript 和 composer 的前提下，本轮基于**首次 ChatGPT conversation-state 真实 capture** 做对齐。

之前 round 1/2 依据的 ChatGPT capture 都是空态首页，这是第一次拿到**带消息对话页**的真实数据。

## 直接依据
- ChatGPT Web conversation-state capture（首次）：
  - [state/ui_reference/chatgpt_web/2026-04-23T08-51-06.750Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/chatgpt_web/2026-04-23T08-51-06.750Z)
  - 包含 4 条消息 (2 user + 2 assistant)
  - 页面标题 "Codex CLI 更新命令"
- Review-editor LLM Sessions capture：
  - [state/ui_reference/review_editor_sessions/2026-04-23T08-54-25.105Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/review_editor_sessions/2026-04-23T08-54-25.105Z)
  - mock session with 15 turns
- 结构化 diff：
  - [2026-04-23T08-57-31.513Z_ui_reference_diff.md](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/diff_reports/2026-04-23T08-57-31.513Z_ui_reference_diff.md)
- ChatGPT Web conversation-state 截图：
  - 已确认真实截图内容

## Round 1-2 之后的改善
从 diff 数据看，以下方面已经明显改善：
- strong card count：24 vs 33（ChatGPT 反而更多，因为它自身有很多 rounded 元素）
- chip count：25 vs 29（已经接近）
- left rail width：264px vs 260px（几乎一致）
- user bubble max width：640px vs 640px（完全一致）

这说明 round 1-2 的去卡片化和 chip 密度压缩是有效的。

## ChatGPT conversation-state 截图真实观察
从截图直接确认的 ChatGPT Web 视觉特征：

### 1. user 消息
- 右对齐
- 浅灰圆角背景（不是蓝色）
- 无边框、无阴影
- 背景色极轻，接近 `#f4f4f4`

### 2. assistant 消息
- **完全无背景色**
- **无边框、无圆角**
- **无阴影**
- 就是纯文字流
- 代码块用独立灰底圆角块
- 下方有小图标行（复制/赞/踩/等）

### 3. header
- 极简：只有模型选择器 + 右侧少量按钮
- 纯白背景 `rgb(255,255,255)`
- 无 border-bottom 视觉线（或极弱）
- 高度 52px

### 4. sidebar
- 260px 宽
- 每个 item 36px 高，极扁
- 无边框，active 态只有轻微背景色变化
- 按日期/类别分组，分组标题是小灰字

### 5. composer
- 56px 高
- 居中于主区下方
- 640px 宽（与消息内容同宽）
- 单行输入栏 + 小发送按钮

### 6. 整体印象
- 极度去装饰化
- 对话本身是唯一的视觉主体
- 没有任何 status chip、meta label、eyebrow、统计信息
- 没有 "Session" / "Context" / "streaming" 等技术状态暴露

## Round 2 之后仍然没对齐的点

### 1. pre-transcript chrome 仍太厚（51px 差距）
- 当前 firstTurnTopOffset = 63px
- ChatGPT = 12px

原因：
- session-stage__header 还在占空间（eyebrow + h1 + subtitle + actions）
- context line 占一行
- spacer 占 10px

ChatGPT 几乎没有 pre-transcript chrome —— header 是 sticky 的，transcript 直接从顶部开始。

### 2. composer 仍偏高（29px 差距）
- 当前 85px
- ChatGPT 56px

原因：
- source bubble 仍占高度
- composer inner padding 仍偏大

### 3. assistant bubble 仍过宽
- 当前 780px
- ChatGPT 640px

ChatGPT 的内容区（包括 user 和 assistant）都限制在 640px 左右。当前 transcript max-width 880px，assistant bubble max-width 780px，都偏宽。

### 4. assistant 消息仍有可见结构
从 ChatGPT 截图确认：assistant 消息是**完全裸**的 —— 没有背景色、没有 border、没有 padding wrapper。当前 review-editor 的 `.session-bubble--assistant` 虽然已经很轻（`padding: 2px 0`），但仍然有 header（badge + time）和明确的 bubble 结构。

### 5. user bubble 背景色不对
ChatGPT user bubble 背景是极浅灰（约 `#f4f4f4`），当前 review-editor 用的是 `#eef4fb`（浅蓝），仍有明显色差。

### 6. session-stage header 不应该存在
ChatGPT 在对话页没有独立的 "Session" header 区域。它的 header 只是 sticky top bar（模型选择器）。当前 review-editor 在 transcript 上方还有一整个 `session-stage__header`（eyebrow + title + subtitle + status + reload），这是最大的"非聊天产品"信号。

### 7. transcript 内的 context line 不应该可见
ChatGPT 对话页没有 "streaming · 3 messages · 3 senders" 这种信息。这属于调试信息，应该隐藏或移到极弱的位置。

## Round 3 实施动作

### A. 删除 session-stage header
- 移除 `session-stage__header` 整个块
- session title 如果需要，改成 sticky top bar 内的一个轻量 label（或者直接不显示，让 transcript 说话）
- status badge 移到 rail item 上或者完全隐去
- reload 按钮移到 rail header 或者 kebab menu

### B. 压 pre-transcript chrome 到 ≤ 20px
- 删除 context line（或把它塞进 rail 的 active session detail）
- 删除 transcript spacer（10px -> 0）
- transcript 直接从顶部开始

### C. composer 压到 56px
- composer inner padding 压缩
- source bubble 进一步缩小或改成 icon-only
- composer shell 整体高度对齐 ChatGPT

### D. 缩窄 transcript + bubble 宽度
- transcript max-width 从 880px 降到 680px
- assistant bubble max-width 从 780px 降到 640px
- user bubble max-width 保持 640px

### E. assistant 消息去结构化
- 移除 `.session-bubble--assistant` 的 header（badge + time）
- assistant 消息变成纯文字流，没有 wrapper
- time 移到 hover 态或者完全隐去
- "Assistant" badge 删除 —— ChatGPT 不标注 role

### F. user bubble 颜色对齐
- 背景色从 `#eef4fb` 改成 `#f4f4f4`
- 保持圆角，但缩小到 18px（ChatGPT 约这个值）

### G. tool / packet / system 继续弱化
- tool 操作行保持 bullet style，但时间戳移到 hover
- packet 默认折叠，更窄
- system 消息变成极轻提示（灰色小字，无块感）

### H. thinking 块微调
- 保持折叠行为
- 但去掉外层 border，改成更轻的分隔
- "Thinking · N chunks" 变成灰色小字

## Round 3 不做
- 不重写 session 数据模型或后端
- 不拆组件（先在 LlmSessionPage.vue 内完成，后续再考虑拆分）
- 不做动效
- 不改 Review 页
- 不做逐像素视觉回归

## 通过标准
Round 3 完成后：
- 第一眼看上去更像 ChatGPT conversation 页面
- 没有 session header 挡在 transcript 前面
- transcript 从页面顶部紧贴开始
- assistant 消息是纯文字流
- composer 高度 ≤ 60px
- tool/packet/system 视觉层级明确低于 user/assistant 对话
