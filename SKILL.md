---
name: local-research
description: 调研 GitHub 项目、抖音内容与 X 收藏，生成本地 Markdown 文档并按主题和来源分文件夹归档。用于项目评估、链接分析、收藏或 Star 增量、抖音选题搜索及跨来源综述；适用于希望结果保存在本地文档的任务，明确要求进入 Workbench 时使用 workbench-research。
---

# 本地情报调研

基于 workbench-research 的证据分析方法独立派生。原技能保持不变；本技能不调用原技能入口，也不继承其 Workbench 队列、数据库、凭据、自动化授权或刷新步骤。

## 输出与范围

- 使用本技能执行调研、链接分析、收藏整理或综述时，默认写本地 Markdown。用户明确要求仅口头解释、只读审阅或不保存时，在对话内交付。
- 归档根目录优先使用用户本次指定位置，否则使用 `~/Documents/Research/`（本机 `/Users/drew/Documents/Research/`）。先读取 [本地归档](references/archive.md)，按主题、来源和条目保存并更新索引。
- 只采集请求只保存来源材料与采集状态，不自动扩展为完整分析。指定链接限于指定对象，外链不自动扩大研究范围。
- 不写入 Workbench、NewThings 的 research 目录或旧抖音收藏库；不执行 `research_queue.py`、`research_prepare.py`、`bookmark_workbench.py`、Workbench refresh API 或任何旧看板构建。旧档案仅在与任务相关时只读参考，产物写入本地新档案。
- 不迁移历史资料、不取消平台收藏、不点赞关注或发帖。仅在用户本次明确要求时配置定时任务；不继承原技能中的历史授权。

## 按任务读取

| 任务 | 参考 |
| --- | --- |
| GitHub 评估或比较 | [GitHub 调研](references/github.md) |
| 抖音收藏、指定内容、推荐流或主题搜索 | [抖音采集与分析](references/douyin.md) |
| X 收藏或指定帖子 | [X 分析](references/x.md) |
| Star / 收藏增量、恢复任务 | [本地增量](references/incremental.md) |
| 已有资料综述、跨来源比较 | [资料综述](references/digests.md) |

## 证据与完成

读取实际原文、代码、文档或转写。区分作者主张、已查证事实与分析判断；摘要、卡片和未转写视频不能代表完整内容。变化性事实带查询时间和直接来源链接，缺关键材料时写明限制。

完成前确认报告非空、来源身份一致、证据路径和索引链接有效、状态符合实际。交付主要结论、可点击的绝对文档路径与必要缺口；区分已采集、部分分析和完整分析。无需启动任何本地服务。
