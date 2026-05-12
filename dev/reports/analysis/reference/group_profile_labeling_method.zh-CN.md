# 群画像方法组件说明

这份文档不再记录具体 `.py` 里的 heuristics，而是描述**方法插件 + 运行器的配合方式**。每个方法以 markdown 插件定义，脚本只是负责装配数据和写出 artifacts。

## 当前方法集合

- [methods/group_portrait_method.zh-CN.md](methods/group_portrait_method.zh-CN.md) — 群画像聚合策略
- [methods/user_profile_method.zh-CN.md](methods/user_profile_method.zh-CN.md) — 群友画像评分/头衔生成
- [methods/group_distribution_method.zh-CN.md](methods/group_distribution_method.zh-CN.md) — 结构分布汇总

每个方法插件都定义以下内容：

1. `input contract`：analysis window runs、distribution context、sampling metadata 等。
2. `rules`：必须遵守的归一化/评分/统计步骤。
3. `output schema`：向 artifacts 输出的字段，包括 status、warning、ratio 等。
4. `limitations`：禁止将 prototype 结果误读为 production 结论，声明 unknown gap。

## 运行器职责

当前脚本（例如 `scripts/run_benshi_group_full_chain.py`）执行以下流程：

1. 抽取 `analysis_window_runs`、`multimodal_summary`、`sampling_metadata`。
2. 按照所需方法加载对应 md 插件并求值。
3. 把插件输出写入：
   - `group_profile.md`（含 warning block + method status）。
   - `group_distribution.json`（含 sampling/ posterior status）。
   - `user_profiles.json`（含 heuristic persona heads + confidence）。
   - `shi_distribution_radar.svg`（所需 family counts from method）。
4. 记录 `run_manifest` 中的 `implementation_status`、`known_gaps`、`sampling_status`。

当前额外约束：

- `社交焦点候选` 不能由 reply-target-only 的匿名 numeric id 直接触发
- `user_profiles.json` 的最终产品层输出应是：
  - `headline_candidates`
  - `headline_evaluations`
- 不应继续使用误导性的 `all_profiles`

## 替换指南

想替换某个方法，只需：

1. 编辑对应 md 插件（遵循输入/输出约定）。
2. 让脚本重新加载 `methods/<name>.md`（可通过 importer 插槽或配置指向新的模板）。
3. 尤其注意保留 warning block，在 `group_profile.md` 与 `run_manifest` 中同步更新。

## 一句话总结

脚本负责数据与 artifact，方法逻辑由这些 markdown 插件定义。不需要改 `.py` 就能替换 persona、画像、分布，真正实现可热插拔。
