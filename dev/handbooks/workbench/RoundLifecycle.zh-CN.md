# 轮次生命周期

状态：`draft_round_001`

每一轮固定遵循这个顺序：

1. 确认 archive snapshot 已完成
2. explorer 产出 source digest
3. worker 产出 draft
4. reviewer 产出 questions / blockers
5. worker 产出显式响应
6. 打包用户审阅 checkpoint
7. 只有用户明确放行后，才进入下一轮

## 状态提升规则

- `draft -> reviewed`
  - reviewer blocker 数为 0
- `reviewed -> canonical`
  - 用户 gate 明确批准
