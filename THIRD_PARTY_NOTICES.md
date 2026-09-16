# 第三方来源与许可

## 抖音下载方式

- 参考项目：[yzfly/douyin-mcp-server](https://github.com/yzfly/douyin-mcp-server)。
- 原始版权声明：Copyright 2025 yzfly。
- 上游许可：Apache License 2.0，全文保留在 [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt)。
- 本包 `scripts/sync_favorites.py` 改编自本地 douyin-favorites-sync 下载脚本；其分享页解析方式参考该上游项目。脚本按 Apache-2.0 提供，不将其简单归入根目录 MIT 许可。
- 2026-09-16 的修改：显式输出目录、可配置的 WhisperX 可执行文件、严格来源 ID 校验、下载与转写分别恢复、原子状态写入、并发锁及限流停止；移除个人路径、旧 uv checkout 和云端转写配置。

## X 采集器

推荐外部安装 [runesleo/bookmark-digest](https://github.com/runesleo/bookmark-digest)，作者 Leo / runesleo，MIT License，固定参考 revision `8cba34b1cb1354924403425598f99ecc30219c33`。本包不包含该项目源码；安装时保留其原有 LICENSE，使用时仅调用 collect，不取消收藏。

## 可选工具

WhisperX 和 FFmpeg 由用户按需另行安装，遵守各自许可；本包不分发这些工具、模型或账号数据。来源致谢不表示上游作者参与或认可本项目。
