# GitHub 项目调研

先确定规范 owner/repo，检索本地已有报告，聚焦本次变化和未回答问题。安装了 gh 时可使用其只读 API，否则使用可用的 GitHub API 或公开网页，再按问题阅读 README、相关代码、文档、近期 issue 或讨论。

```bash
gh api repos/<owner>/<repo> --jq '{stars:.stargazers_count,forks:.forks_count,license:.license.spdx_id,language:.language,pushed:.pushed_at,archived:.archived,issues:.open_issues_count}'
gh api repos/<owner>/<repo>/readme -H 'Accept: application/vnd.github.raw'
gh api repos/<owner>/<repo>/releases/latest --jq '{tag:.tag_name,at:.published_at}'
```

权限或 API 失败可用公开网页并记录降级。latest release 返回 404 不等于停止维护。分页不足只报告实际覆盖范围，不用 stars 单独判断质量。不因调研而自动安装、运行仓库代码或修改项目。

报告回答：它解决什么问题、核心能力与适用场景、技术实现和上手成本、维护与成熟度、相关且有依据的限制、最终判断。可选判断为推荐使用、推荐试用、推荐关注、谨慎评估、暂不推荐，并说明理由；没有运行验证时不能写已验证可用。变化性数据带查询日期，关键结论旁附仓库、文档、代码或 release 的直接来源。

多项目比较使用一致维度，区别未确认和不支持。按 archive.md 保存，不依赖外部索引器。若由 X 帖子引出且项目研究在任务范围内，在两份报告之间建立文件链接，帖子分析仍需完成。
