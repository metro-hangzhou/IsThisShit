# Review Editor `LLM Sessions` UI 参考采样方法

## 目标
先建立一条**结构化参考采样链**，再做 `LLM Sessions` UI 重构。这样后续不再主要依赖：

- 用户截图
- 自己对 ChatGPT Web 的模糊记忆
- 一轮轮主观“像不像”的口头反馈

而是依赖一套可以重复跑的本地方法：

1. 采样 **ChatGPT Web** 当前真实页面
2. 采样 **review-editor / LLM Sessions** 当前真实页面
3. 输出统一的：
   - `screenshot.png`
   - `layout.json`
   - `dom_excerpt.json`
   - `style_summary.json`
4. 再生成结构化 `diff_report.md`

## 设计原则
### 1. ChatGPT Web 是主真值
当前 `LLM Sessions` 的整体骨架必须向 ChatGPT Web 对齐。Claude Code / Codex 只用来借鉴：

- tool 行
- reasoning 块
- prompt / packet 折叠方式

不作为整体页面骨架真值。

### 2. 先抓“结构”，再抓“像素”
第一阶段不追求视觉逐像素 diff。先抓这几类结构化指标：

- 左栏宽度
- 主列宽度
- transcript 首条消息距离顶部的偏移
- 底部 composer 高度
- user / assistant bubble 的最大宽度
- 强卡片数量
- chips 数量
- turn 数量

这些指标足以快速指出为什么当前页面不像 ChatGPT Web。

### 3. 同构采样
采样 ChatGPT Web 和采样 `review-editor` 必须使用**同一套 bundle 结构**，否则后面的 diff 没法稳定自动化。

## 工具链
### 1. 浏览器捕获脚本
位置：

- `apps/review-editor/scripts/ui_reference/browser_capture.mjs`

职责：

- 自动寻找本机 Chromium 家族浏览器
- 通过 Chrome DevTools Protocol 启动远程调试浏览器
- 打开目标页面
- 根据 profile 执行少量自动交互
- 输出 screenshot + layout/dom/style 三类 JSON

当前支持的浏览器候选：

- `360ChromeX.exe`
- `msedge.exe`
- `chrome.exe`

也支持 `--browser-exe` 显式传入。

### 2. 页面 profile
位置：

- `apps/review-editor/scripts/ui_reference/profiles.mjs`

当前内建：

- `review-editor-sessions`
- `chatgpt-web`

profile 负责定义：

- 等待哪些 selector 出现
- 需要执行哪些自动点击/等待动作
- 用哪些 selector 提取 sidebar / transcript / composer / bubble / chips 等结构

### 3. Review Editor 采样入口
位置：

- `apps/review-editor/scripts/ui_reference/capture_review_editor_sessions.mjs`

职责：

- 可选地先调用本地 `/api/review/llm/session/mock-start`
- 再打开 `review-editor` web 页面
- 自动切到 `LLM Sessions`
- 自动选中第一个 session
- 落地 capture bundle 到：
  - `state/ui_reference/review_editor_sessions/<timestamp>/`

### 4. ChatGPT 采样入口
位置：

- `apps/review-editor/scripts/ui_reference/capture_chatgpt_reference.mjs`

职责：

- 启动可调试 Chromium
- 打开 ChatGPT Web
- 等主内容 / composer 出现
- 落地 capture bundle 到：
  - `state/ui_reference/chatgpt_web/<timestamp>/`

### 5. Diff 生成器
位置：

- `apps/review-editor/scripts/ui_reference/compare_ui_references.mjs`

职责：

- 读取两个 capture bundle
- 比较关键布局指标
- 生成：
  - `state/ui_reference/diff_reports/<timestamp>_ui_reference_diff.md`
  - 同名 `.json`

## 产物格式
每次 capture 固定输出：

- `capture_manifest.json`
- `layout.json`
- `dom_excerpt.json`
- `style_summary.json`
- `screenshot.png`

### `layout.json`
包含：

- 页面标题与 URL
- viewport
- sidebar/header/main/transcript/composer 的矩形
- turnCount
- strongCardCount
- chipCount
- user / assistant 最大 bubble 宽度
- 首条 turn 与 transcript 顶部的偏移

### `dom_excerpt.json`
只保留可读摘要：

- 左栏前几项 session/chat 文字摘要
- transcript 前几条 turn 的文本摘要
- composer 文本摘要

### `style_summary.json`
只保留关键节点的粗粒度 computed style：

- display
- position
- padding
- margin
- borderRadius
- boxShadow
- backgroundColor
- fontSize
- lineHeight

## 推荐工作流
### 1. 先采样 ChatGPT Web
示例：

```bash
cd apps/review-editor
node scripts/ui_reference/capture_chatgpt_reference.mjs --headed
```

如果要指定浏览器：

```bash
node scripts/ui_reference/capture_chatgpt_reference.mjs --browser-exe "C:\\Program Files (x86)\\360\\Chrome\\Application\\360ChromeX.exe" --headed
```

### 2. 再采样本地 `LLM Sessions`
示例：

```bash
cd apps/review-editor
node scripts/ui_reference/capture_review_editor_sessions.mjs --headed
```

这个脚本默认会先打一个 mock session，再自动进入 sessions 页。

### 3. 最后生成 diff
示例：

```bash
cd apps/review-editor
node scripts/ui_reference/compare_ui_references.mjs \
  --reference ../../state/ui_reference/chatgpt_web/<ref-dir> \
  --candidate ../../state/ui_reference/review_editor_sessions/<candidate-dir>
```

## 如何用 diff 指导重构
后续每轮 `LLM Sessions` 重构都应该按这个顺序：

1. 跑一次当前候选 UI capture
2. 跟最近一次 ChatGPT capture 做 diff
3. 先改：
   - transcript 宽度
   - 左栏结构
   - 顶部 chrome
   - 底部 composer 关系
   - 强卡片数量
   - chips 密度
4. 再改视觉细节：
   - 圆角
   - 阴影
   - padding
   - 动效

## 当前限制
### 1. ChatGPT DOM 本身会变
因此 `chatgpt-web` profile 只做第一层 heuristics，不承诺永久稳定。它的价值是：

- 快速建立真实参考
- 给未来几轮 UI 重构提供方向

不是建立一个永远不坏的 web scraper。

### 2. 这是结构 diff，不是像素 diff
当前还没有上逐像素视觉回归。原因是这一步首先要解决：

- AI 怎么更高效地“读懂”自己页面和 ChatGPT 的差异

而不是先做一套昂贵的视觉测试体系。

## 结论
当前 `LLM Sessions` 的下一阶段 UI 工作，不应再主要依赖“用户截图 + 自己记忆 + 主观调 UI”。  
必须先跑这条参考采样链，把：

- ChatGPT Web 的真实结构
- review-editor 当前结构

都转成结构化 bundle 和 diff report，再据此继续重构。
