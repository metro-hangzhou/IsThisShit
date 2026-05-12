# Review Editor `LLM Sessions` UI Round 2 Findings

## 本轮目标
在第一轮已经建立真实 capture / diff 方法链的前提下，第二轮不再继续修补“组件细节”，而是直接收页面骨架：

- app shell 对 `sessions` 页单独降噪
- 左 rail 更像 ChatGPT 的会话侧栏
- 中心 transcript 更接近单列聊天流
- composer 更接近 ChatGPT 式底部输入栏
- tool / packet / system 继续弱化，避免压过对话本身

## 直接依据
- ChatGPT Web 真实参考：
  - [state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/chatgpt_web/2026-04-19T18-59-03.043Z)
- Round 1 后 review-editor 真实 capture：
  - [state/ui_reference/review_editor_sessions/2026-04-19T19-22-34.509Z](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/review_editor_sessions/2026-04-19T19-22-34.509Z)
- 真实 diff：
  - [2026-04-19T19-24-18.397Z_ui_reference_diff.md](/mnt/d/Coding_Project/IsThisShit/state/ui_reference/diff_reports/2026-04-19T19-24-18.397Z_ui_reference_diff.md)

## Round 1 之后仍然没对齐的点
### 1. app shell 还是 QQ / debug 壳
虽然 `LLM Sessions` 内部已经开始降卡片感，但整个页面仍然挂在：
- 蓝色 QQ 顶栏
- 偏“桌面工具”味的外壳

这会直接破坏“ChatGPT/Claude 对话界面”的第一感知。

### 2. 左 rail 还不够平
虽然 item 已经变薄，但还偏像“列表卡片”，不是纯会话 rail。

### 3. transcript 仍有过强的“块感”
Round 1 已经移除了大量 chips，但：
- user bubble 仍偏厚
- system / packet 仍偏块
- transcript 最大宽度仍偏窄

### 4. composer 还不够像真正的主输入
Round 1 已经把 picker 浮起来了，但：
- composer 仍然太高
- source bubble 仍偏表单气质
- 输入栏整体还不够像 ChatGPT 主输入栏

## Round 2 实施动作
### A. app shell 层
- `sessions` 页独立应用更浅、更中性的 window bar 样式
- sessions 页 logo 从 `QQ` 切换成更中性的 `AI`
- `sessions` 页内容区改成暖白背景，不再沿用 review 页蓝灰底

### B. 左 rail
- rail 宽度重新拉到 `264px`
- rail 背景更像 ChatGPT 的浅暖灰侧栏
- item 间距继续压小
- active 态改成更轻的面板，而不是明显卡片

### C. transcript
- 主列从 `860px` 增到 `880px`
- transcript 顶部 chrome 再压缩
- context line 继续保留，但信息压到单行
- user bubble 放大一点点宽度，但继续去重卡片感
- assistant/system/tool/packet 继续弱化边界和层级

### D. composer
- 主 shell 高度继续压到 `56px`
- textarea 改为 `resize: none`
- source bubble 继续缩小并更像功能气泡
- picker 维持浮层，不再占用主高度

## 本轮不做
- 还不进入第三轮的 conversation-state 对齐
- 不在这一轮里补复杂动效
- 不改 review 页，只收 `LLM Sessions`

## 当前预期效果
Round 2 不追求“已经完全一样”，而是追求：
- 第一眼骨架更像聊天产品
- QQ / 工具台面感明显下降
- transcript 成为主注意力
- 底部输入成为明确主交互入口
