# TODOs.review-editor-round-012

- [x] 建立 `src-tauri` 基础壳
- [x] 增加 `npm run tauri:dev`
- [x] 增加 `npm run tauri:build`
- [x] 保留 Python review server
- [x] 保留 Vite HMR
- [x] 将前端 asset 主路径切到 Tauri 本地资源桥接
- [x] 把目录授权按钮降级为 web fallback
- [x] 跑通前端、后端、Tauri 校验
- [x] 修复桌面壳双标题栏问题：系统窗框不应包住 QQ 自定义顶栏
- [x] 修复蓝色顶栏空白区拖动：显式接入 Tauri `startDragging()`
- [x] 修复自定义最小化 / 最大化 / 关闭逻辑未可靠生效的问题
- [x] 在 Rust 启动时强制执行 frameless 配置，避免仅靠 `tauri.conf` 漏生效
- [x] 修复旧 exe 占线导致新修复未真正进入 release binary 的构建问题
- [x] 启动第二阶段交互迁移：将 `说明 / 边界 / 下一步 / 建议落样本` 下沉到底部 Composer
- [x] 将右侧备注面板收成“摘要 + 长尾字段”，不再作为主快审区
- [x] 将窗口页嵌入式结论表单收成长尾备注区，避免底部和右侧双主交互冲突
- [x] 前端测试改为覆盖底部 Composer 保存链路
