# local-research · 本地情报调研

一个把 GitHub 项目、抖音内容与 X 帖子/收藏整理成本地 Markdown 文档的 Agent Skill。按主题和来源归档，保留证据范围、历史版本与索引，也支持已有资料综述和增量记录。

这是交给 Agent 执行的工作流指令包，不是独立运行的爬虫或定时服务。它不依赖 Workbench 或作者的本机环境。

## 安装

下载发布的 ZIP 并解压，将其中 `local-research` 文件夹放进 Agent 的技能目录，确保目录下直接有 `SKILL.md`，而不是多嵌套一层文件夹。

对于本地 Codex，可将文件夹放在用户技能目录（默认 `~/.codex/skills/local-research/`；自定义了 `CODEX_HOME` 时为其下的 `skills/local-research/`）。已有同名技能时先保留备份。随后在新会话中检查技能是否出现。其他 Agent 请按其技能加载方式导入整个文件夹；只支持提示词的工具可读取 `SKILL.md`，但也要能访问 `references/`。

## 使用

```text
用 $local-research 调研 https://github.com/owner/repo，保存到本地。

用 $local-research 分析这些 X 帖子，按“开发工具”主题归档。

用 $local-research 分析我提供的视频转写，保存到 ./research。

用 $local-research 对已有 AI 工具报告做比较，输出英文报告。
```

将示例链接替换为实际研究对象。`$local-research` 是 Codex 调用形式，其他宿主使用其支持的调用方式。

输出根目录优先级：本次指定目录 → `LOCAL_RESEARCH_ROOT` 环境变量 → 当前用户主目录下的 `Documents/Research/`。环境变量是供 Agent 读取的约定，不需要额外配置程序。

```text
Research/
  INDEX.md
  开发工具/
    INDEX.md
    github/日期-owner--repo/report.md
    github/日期-owner--repo/sources.md
    x/日期-帖子ID/report.md
    digests/日期-主题/report.md
```

抖音条目保存在主题下的 `douyin/`。证据文件按需保存；`.state/` 仅记录本地增量，`.staging/` 放工具中间产物。仅采集可只产出 sources.md。详细约定见 [归档规则](references/archive.md)。

## 能力与依赖

| 场景 | 需要的能力 | 缺失时 |
| --- | --- | --- |
| 分析本地原文、字幕、旧报告 | Agent 能读取和写入本地文件 | 无文件写入能力则不能完成归档 |
| GitHub 当前项目调研 | 网络读取或只读 API；gh 可选 | 分析提供的材料，注明无法确认当前状态 |
| 抖音 / X 在线收藏 | 平台支持的只读接口，或 Agent 可操作的已登录浏览器 | 使用用户提供的导出或正文 |
| 视频口播分析 | 字幕/转写，或用户已配置的转写工具 | 保存元数据和缺口，不伪造完整分析 |
| 定时增量 | 宿主提供调度工具且用户授权 | 手动运行 |

没有捆绑平台账号、下载脚本、浏览器插件、语音模型或云端密钥。平台界面和访问能力可能变化，工作流要求核实实际页面与工具，不保证无人值守全量采集。

## 数据与共享

默认仅写选定本地归档目录，不自动向知识库发布、不修改平台收藏。联网访问仍由所选工具完成，模型和工具的数据处理方式由使用者的运行环境决定。调研文档、登录数据和收藏记录不属于技能源码，分享技能时不要把个人归档打包进去。

## 维护与验证

入口在 [SKILL.md](SKILL.md)，平台流程在 `references/`，Codex 展示信息在 `agents/openai.yaml`。修改后检查所有相对引用可解析，并分别验证有网络、仅本地材料、缺少转写三种情形的完成状态；不要用格式检查代替真实平台测试。

## 许可证

本指令包采用 [MIT License](LICENSE)。外部平台材料、研究对象与用户归档不因本许可证而改变其原有权利归属。
