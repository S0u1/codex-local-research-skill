# 推荐采集方案与安装

这些是本技能推荐的工程接入方案，不表示平台官方许可或无账号风险。先按 onboarding.md 说明实际访问方式与平台规则；用户选择相应接入方案后才安装/连接。已配置可用方案可复用，不重复安装。

| 来源 | 推荐方案 | 是否随包提供 |
| --- | --- | --- |
| GitHub | GitHub CLI `gh` + Star API | 说明在 github.md，安装 gh |
| X | `runesleo/bookmark-digest` 固定版本 + 专用 Chrome CDP 会话 | 外部可选依赖，下面指导安装；不内嵌源码 |
| 抖音 | 宿主浏览器读收藏清单 + `scripts/sync_favorites.py` 下载视频 | 下载脚本已随包提供，Python 3.10+ 即可只下载 |
| 抖音本地转写 | FFmpeg + WhisperX | 可选依赖，安装后显式开启；无需云端 Key |

X CDP 属于非 API 浏览器自动化，X 规则明确限制此方式；抖音下载解析也不是官方授权接口。给出这些技术选项时不能只说“低频即可安全”。用户不选择此方式时保留其已授权的可用接口或手动导入路径，不自动切换方案。

## X：固定版本采集器

该版本导入 `fcntl`，支持 macOS/Linux，**不支持原生 Windows Python**。Windows 使用宿主已支持的浏览器工具，或把采集器和浏览器放在同一个 Linux 环境；不要把 Linux 命令冒充 Windows 安装成功。

下面命令面向 macOS/Linux。首次新装使用独立目录；目录存在时先核实 revision 和用户改动，不覆盖。

```bash
lr_x_root="$HOME/.local/share/local-research/x-cdp"
mkdir -p "$lr_x_root"
git clone https://github.com/runesleo/bookmark-digest.git "$lr_x_root/source"
git -C "$lr_x_root/source" checkout --detach 8cba34b1cb1354924403425598f99ecc30219c33
python3 -m venv "$lr_x_root/venv"
"$lr_x_root/venv/bin/python" -m pip install -r "$lr_x_root/source/requirements.txt" 'websocket-client==1.8.0'
"$lr_x_root/venv/bin/python" "$lr_x_root/source/bookmark_digest.py" --help
```

固定版本来自原 Workbench 的上游记录，已核实远端仍存在；后续升级应重新核对 CLI 和状态语义，不能自动跟随 main。

### 专用 Chrome 与登录

为每个账号设置独立 profile；下例为单账号。macOS 启动命令：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$HOME/.local/share/local-research/x-cdp/chrome-profile" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --remote-allow-origins=http://127.0.0.1:9222 \
  https://x.com/i/bookmarks
```

Linux 替换可执行文件为实际的 `google-chrome` 或 `chromium`。端口被占用时先识别已有进程，不杀死用户浏览器；换端口后所有 CDP/Origin 参数保持一致。用户在专用窗口自行登录 X，不复制默认 Chrome profile 或 cookies。非默认 profile 的要求见 [Chrome 官方说明](https://developer.chrome.com/blog/remote-debugging-port)。

CDP 控制浏览器会话，只接受回环监听；macOS 用 `lsof -nP -iTCP:9222 -sTCP:LISTEN`、Linux 用 `ss -ltnp 'sport = :9222'` 核实。不得将该调试端口开放到局域网/公网，也不使用 `--remote-allow-origins=*`。

### 只执行 collect

将 `lr_archive` 设置为本次选定归档根目录，`lr_account` 替换为核实并清理后的账号标识，不保留示例占位值。全局参数在 collect 前：

```bash
lr_x_root="$HOME/.local/share/local-research/x-cdp"
lr_archive="$HOME/Documents/Research"
lr_account="REPLACE_WITH_VERIFIED_ACCOUNT"
"$lr_x_root/venv/bin/python" "$lr_x_root/source/bookmark_digest.py" \
  --cdp http://127.0.0.1:9222 \
  --state "$lr_archive/.state/x-cdp/$lr_account/collector/state.json" \
  collect --count 20
```

Agent 捕获 stdout 的 JSON，确认命令成功及来源健康后，按 archive.md 保存本批清单；错误输出不能覆盖上次成功结果。核对专用窗口的账号，返回条目身份、正文范围和分页标记，再进行分析归档。

只使用 `collect`：不执行上游 `commit`（登记 processed）、`unbookmark-processed`（取消收藏）或上游定时安装脚本。本技能独立记录分析进度，定时由宿主授权后配置。

限制：

- collect 不写 processed 状态，但会创建 state 父目录及锁文件；必须隔离目录与账号，不能使用其他工作流的 state。
- CLI 会过滤有效 processed 条目，因此上游 state 不能代替本技能的增量基线。
- `--count` 上限 200，限制最终返回条数，不限制浏览器滚动/请求数；先切片再过滤，不保证补足数量。
- 检查 `complete`、`truncated`、`inbox_empty`，退出码 0 或 items 为空都不自动代表全库完成/空收藏。
- 不提供分页游标恢复。不能通过增大 count 或反复运行声称已获取超过窗口的全部历史。部分结果可保存分析，覆盖不足时保留原基线与缺口。
- X Articles、线程或视频内容可能不完整；按 x.md 补读并记录限制。

## 抖音：随包下载脚本

**脚本只处理已有视频清单，不登录账号、不读取收藏列表。** 收藏列表仍由已连接的宿主浏览器读取，生成 JSON，例如：

```json
{"items":[{"video_id":"1234","url":"https://www.douyin.com/video/1234","title":"示例：执行前替换为真实收藏"}]}
```

这个 ID 仅展示结构，不得执行为真实采集。将实际清单保存到归档根目录的本批状态目录。下面命令在技能根目录执行，清单与输出占位符替换为实际绝对路径：

```bash
python3 scripts/sync_favorites.py --help
python3 scripts/sync_favorites.py --items-file /absolute/path/favorites.json --output /absolute/archive/.staging/douyin/account --transcriber none
```

Windows 使用已安装的 `py -3` 或对应 Python 路径。下载器仅使用 Python 标准库；不用 Key、不读取浏览器 cookies。优先按数字视频 ID 解析移动端 feed，失败回退到分享页解析；遇到明确 401/403/429 则停止本批，不以回退接口继续绕过限制。非正式接口可能失效，HTTP 200 也不能保证平台未返回验证页；此时记录失败而非反复请求。

输出为 `<output>/<video-id>/video.mp4`、`metadata.json`，可选 `transcript.txt` 与 `transcript.srt`；`.download-state.json` 和 `.download.lock` 只服务下载器。相同账号复用同一 staging 根目录以便断点恢复。不能使用旧脚本的 `--bootstrap`、`--whisperx-dir` 或云转写参数；本版接口以 --help 为准。

已下载后再次用 local 转写会补转写，不因下载状态跳过。失败后修复原因再运行同一清单；身份元数据匹配且具有 MP4 文件头的已有视频可复用；身份不明或格式错误时保留文件并报告冲突，不能自动重新标记为当前条目。下载完成不等于分析完成，仍须读真实内容、生成报告，并将所需证据复制到 archive.md 的正式条目目录。图文单独通过浏览器分析，不送进视频脚本。

同一输出目录只允许一个进程。异常退出遗留 `.download.lock` 时先核对记录的进程已结束，再移除锁；不在仍有任务运行时强行解锁。

### 可选本地转写

推荐单独创建 Python 3.11 虚拟环境，并按 [WhisperX 官方安装说明](https://github.com/m-bain/whisperX) 核对当时支持的 Python/依赖版本。以下安装发生在用户明确授权后：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install whisperx
.venv/bin/whisperx --help
ffmpeg -version
```

Windows 将解释器/命令路径替换为 `.venv\\Scripts\\python.exe` 和 `.venv\\Scripts\\whisperx.exe`。FFmpeg 是独立系统依赖，按 [官方安装入口](https://ffmpeg.org/download.html) 选择实际系统对应方式，并验证 PATH。没有 FFmpeg 时可以只下载，不声称本地转写已就绪。

```bash
python3 scripts/sync_favorites.py --items-file /absolute/path/favorites.json --output /absolute/archive/.staging/douyin/account --transcriber local --whisperx-command .venv/bin/whisperx
```

默认 small、中文、CPU/int8，无需 GPU；可用 `--whisperx-model`、`--whisperx-language` 调整。首次运行会下载模型，需要网络和磁盘空间；语音处理在本机执行。本包不内置模型、不提供云转写，也不需要配置硅基流动 Key。

首次用本次授权范围的一条视频验证下载与非空转写，不为测试扩大收藏范围。未执行真实下载/模型转写时只能说明静态或离线测试通过。
