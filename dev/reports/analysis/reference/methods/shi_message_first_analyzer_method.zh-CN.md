# Message-First 搬史分析器方法规范

## 目标

把当前 `window-first + carrier-biased` 的搬史分析链，重构成：

- **message-first**
- **relation-bound**
- **core-before-carrier**
- **compact-aware**

的 analyzer。

它首先回答：

1. 这条消息/素材本体是不是 shi
2. 它到底是哪种 shi
3. 为什么它本身算 shi
4. 它是如何通过 relation / carrier / 群体反应被抬成窗口级消费结构的

而不是先回答：

- 这窗像不像吃史
- 有没有 forward
- 有没有 reaction
- 再倒推本体

## 当前架构的结构性问题

当前 analyzer 的最大 choke point 是：

1. `window-first`
   - 先挑异常窗口
   - 再在窗口里找 `shi`

2. `selected_messages-first`
   - 送模主工作台仍然是压缩后的 `selected_messages`
   - 而不是显式的 message probes / relation graph / packet

3. `carrier-biased`
   - `forward`
   - `reaction`
   - 图片/视频壳
   - 媒体缺口
   这些形态信号仍然容易被错误用作 shi 本体代理

4. `relation graph` 缺失
   - 现在很多“上下文”仍是近邻/窗口共存，而不是明确绑定关系

这会直接导致：

- 纯文本 shi 召回偏低
- 单图/单视频 shi 召回偏低
- forward 类表面形态命中偏高
- routine reply / routine technical chatter 容易被误抬

## 第一性原理

搬史分析器的核心目标不是判断：

- 哪种消息**容易**是 shi

而是判断：

- **这条消息本身是不是 shi**

所以推理顺序必须变成：

1. **message probe**
   - 对每条消息做本体判断
2. **relation graph**
   - 判断哪些消息之间存在直接语义/结构关系
3. **message packet**
   - 在有限 ctx 下只保留最有分析价值的局部工作集
4. **window constructor**
   - 让窗口成为 message-first 分析的聚合结果
5. **group aggregation**
   - 再做跨窗群画像和成分分布

## 新骨架

### A. Message Probe

每条消息都先生成 `message probe`：

- `surface_kind`
- `bearingness_hint`
  - `core_bearing`
  - `carrier_only`
  - `social_echo_only`
  - `boundary_only`
  - `off_target`
- `core_signal_score`
- `carrier_signal_score`
- `relation_signal_score`
- `shi_object_hint`
- `core_reason_hint`

要求：

- 纯文本 shi、单图 shi、单视频 shi 必须与 forward 同级
- `forward` 只能回答 carrier / provenance，不能自动升格成本体理由

### B. Relation Graph

上下文只允许通过明确关系进入主分析层：

- reply
- @ 绑定
- forward child / nested forward
- 同一 shi 对象的 lexical uptake
- 群体反应链

禁止把“时间邻近”直接当作主证据。

### C. Message Packet

送模的不是整窗，而是 message-first packet：

- anchors
- relation-bound context
- boundary context
- dropped noise summary

它必须受预算约束：

- 优先保留 `core_bearing`
- 再保留与 anchor 直接绑定的 `carrier_only` / `boundary_only`
- 最后才是辅助上下文

### D. Window Constructor

窗口不再是“天然分析单位”，而是：

- message probes
- relation graph
- packet assembly

的聚合结果。

### E. Group Aggregation

跨窗聚合才回答：

- `group_profile_prior`
- `component_distribution`
- `interaction_feature`
- `carrier_distribution`

## 上下文管理与 compact

### 原则

- 不把完整窗口整坨塞给模型
- 不用 RAG 当主 compact
- 用 prompt-based structured compact

### 输入层次

1. 稳定 analyzer 规则前缀
2. `message_first_context`
3. 必要的 `selected_messages` fallback
4. cross-window recap

### 预算规则

送模裁剪顺序固定：

1. `off_target`
2. `social_echo_only`
3. 重复的 routine carrier
4. 低价值旧 boundary

禁止先裁掉 `core_bearing`。

## Common-Track Gates

### Gate A

- 明确当前旧架构 choke points
- 不再把问题伪装成 prompt tweak

### Gate B

- 写清 message-first contracts
- 写清 relation graph contracts
- 写清 compact/budget rules

### Gate C

反方审查重点：

- 是否仍然在靠 `forward` 形态猜 shi
- 是否仍然把邻近消息当上下文
- 是否在 ctx 紧张时错误丢掉 core-bearing anchors

### Gate D

- 根据 critique 修改设计

### Gate E

- 小样本定性验证
- 不先大样本定量

## 当前实施阶段

当前只完成第一层 scaffolding：

- `message_probes`
- `relation_edges`
- `message_packet`
- `compact_recap`
- prompt payload 中的 `message_first_context`

这还不是完整重构完成态。

当前状态应视为：

- **message-first scaffolding landed**
- **full analyzer still mid-migration**

## 后续实施顺序

1. 把 `message_first_context` 真正变成送模主工作台
2. 把 selected-window selection 退化成上游候选池，而不是主分析单位
3. 把 review scheduling 改成绑定 message probe / packet
4. 再做小样本定性
5. 只有方向确认后，才做大样本定量
