# GitHub Star 读取与分析

## 先读取用户的 Star

按 onboarding.md 验证 gh 或可用连接器与当前账号。默认不是调研任意仓库链接，而是从该账号实际收藏的仓库开始。

使用 gh 时可以读取当前用户的 Star，按收藏创建时间倒序；star+json 响应包含 starred_at 和 repo：

```bash
gh api user --jq .login
gh api 'user/starred?sort=created&direction=desc&per_page=20' -H 'Accept: application/vnd.github.star+json'
```

最近 20 条请求只读所需页；全部已有收藏或完整基线使用分页并检查执行成功：

```bash
gh api --paginate --slurp 'user/starred?sort=created&direction=desc&per_page=100' -H 'Accept: application/vnd.github.star+json'
```

完整分页输出是各页数组，按页展开后以 repo.id 去重，保留 repo.full_name、repo.html_url 与 starred_at。本地报告仍使用规范 owner/repo 名称，仓库改名时按稳定 repo.id 关联旧档案。不能把 /repos/{owner}/{repo}/stargazers（收藏该仓库的人）误当用户收藏列表。参数与权限以 [官方 Star API 文档](https://docs.github.com/en/rest/activity/starring#list-repositories-starred-by-the-authenticated-user) 及实际工具为准。

无 gh 时先指导安装/登录，或使用确实能列出目标账号 Star 的连接器/已登录页面；不要退化为仅让用户粘贴仓库地址并宣称同步完成。空列表核实账号与响应，不把权限错误当空收藏。

将本批实际列表保存为 archive.md 的收藏清单；按请求范围逐个分析，不按项目热门程度、语言或主观价值丢弃条目。仅未来新增模式首轮按 incremental.md 建基线。

## 再分析收藏仓库

确定每条规范 owner/repo，检索已有报告。用只读 API 或网页读取 README、文档、相关代码和维护信号，材料按问题选读，不运行或安装收藏仓库代码。例如：

```bash
gh api repos/<owner>/<repo> --jq '{stars:.stargazers_count,forks:.forks_count,license:.license.spdx_id,language:.language,pushed:.pushed_at,archived:.archived,issues:.open_issues_count}'
gh api repos/<owner>/<repo>/readme -H 'Accept: application/vnd.github.raw'
gh api repos/<owner>/<repo>/releases/latest --jq '{tag:.tag_name,at:.published_at}'
```

权限或 API 失败可用公开网页并记录降级。latest release 返回 404 不等于停止维护。分页不足只报告实际覆盖范围，不用 stars 单独判断质量。不因调研而自动安装、运行仓库代码或修改项目。

报告回答：它解决什么问题、核心能力与适用场景、技术实现和上手成本、维护与成熟度、相关且有依据的限制、最终判断。可选判断为推荐使用、推荐试用、推荐关注、谨慎评估、暂不推荐，并说明理由；没有运行验证时不能写已验证可用。变化性数据带查询日期，关键结论旁附仓库、文档、代码或 release 的直接来源。

用户另行要求对收藏做比较时使用一致维度，区别未确认和不支持。按 archive.md 保存，不依赖外部索引器。若由 X 帖子引出且项目研究在任务范围内，在两份报告之间建立文件链接，帖子分析仍需完成。
