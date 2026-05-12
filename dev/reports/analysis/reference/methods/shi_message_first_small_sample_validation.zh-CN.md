# Shi Message-First 小样本定性验证方案

更新时间：2026-04-16

## 目标

在进入新一轮 live LLM 小样本验证前，明确：

1. 这轮验证不是继续微调旧 `window-first` 分析器。
2. 这轮验证的目标是确认 `message-first` 方向是否真的摆脱了 `forward` 形态绑架。
3. 只有在定性方向正确后，才进入更大样本定量分析。

## 当前前置状态

已完成：

- `message_first_context` 已进入 `BenshiAnalysisPack`
- `message_probes` 现已来自 raw window messages，而不是仅来自 `selected_messages`
- prompt 已把 `message_first_context` 提升为主工作台
- `review_alignment_context.mode` 可正确区分 `message_first_v1`
- focused tests:
  - `tests/test_benshi_message_first.py`
  - `tests/test_benshi_master_agent.py`
  已通过

当前仍是脚手架状态：

- 关系图仍以 reply/local continuation 为主
- `selected_messages` 仍保留为兼容层
- 审核点调度尚未完全切到 message-probe 主导

## 验证目标

这轮小样本必须重点验证这 5 件事：

1. 纯文本 shi 是否能直接成为 `core_bearing`
2. 纯图片/纯视频 shi 是否能直接成为 `core_bearing`
3. `forward` 是否退回到 `carrier/provenance` 语义，而不是继续冒充本体理由
4. routine technical chatter / routine group discussion 是否不再仅因靠近正窗口而被抬高
5. 局部理由是否开始真正描述：
   - 这条 shi 到底是什么
   - 为什么它本体算 shi
   - 它如何被群体消费

## 采样原则

小样本只选高价值窗口，不追求量。

建议优先取样：

- `712`
  - 保留已知 forward-heavy 窗口
  - 同时补一窗 direct-image / direct-text 类型窗口
- `763`
  - 保留更集中、更倾倒式窗口
- `x3c`
  - 保留高反应、高日常噪音窗口，用来检验是否仍会把 routine chatter 抬成 shi

每个 corpus 建议：

- 1 个主窗口
- 最多 2 个窗口

总量：

- 3 到 5 个窗口

## 通过标准

满足以下条件时，才允许进入下一轮大样本：

1. `forward` 不再主导主要理由
   - carrier note 可以出现
   - 但 `shi core` 不能主要由 `forward/nested forward` 描述

2. 至少出现一个非-forward 的真 `core_bearing`
   - 纯文本或纯图像/视频都可以

3. 至少一个已知 routine discussion 负例被正确压低
   - 例如：
     - 电源/充电宝/普通技术讨论
     - 普通群友短接话

4. 审核点理由不再只描述消息形态
   - 必须能读出：
     - `shi object`
     - `core reason`
     - `carrier note`
     - `social consumption`

## 失败信号

出现以下任一情况，说明仍不能进大样本：

1. 主要命中仍靠：
   - forward
   - nested forward
   - image shell
   - reaction density

2. direct text / direct image / direct video 仍缺乏独立命中

3. routine chatter 仍频繁进正审流

4. 模型理由仍在回答：
   - “这是什么 carrier”
   而不是：
   - “这条 shi 到底是什么”

## 执行顺序

1. 先跑 message-first prompt version 的小样本 live run
2. 先不扩人工审核量
3. 只审高价值小样本窗口
4. 根据人工结果判断：
   - 是否继续修关系图
   - 是否继续切审核点调度
5. 通过后再进入大样本批量测试

## 当前结论

到这一步，项目状态是：

- 已经完成 message-first 的第一层结构重构
- 已经具备小样本定性验证条件
- 但还不应直接跳回大样本批量测试

当前最合适的下一步：

- 运行一轮小样本定性验证
- 看 message-first 方向是否真的把 `shi core` 从 `carrier/forward bias` 中剥离出来
