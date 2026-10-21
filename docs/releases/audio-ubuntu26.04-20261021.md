MacBook9,1 内置扬声器在 Ubuntu 26.04 的修复包。下载下方 Assets 中的 `macbook91-audio-ubuntu26.04-7.0.0-38.38-fixed-20261021.zip`，解压后先运行只读检查：

```bash
python3 scripts/install-audio-26.04-fixed.py --check
```

ZIP 包含驱动源码、已编译模块、原生 DKMS 归档、四声道配置、安装脚本、修复过程与回退说明。附带 `.sha256` 文件用于下载校验。

适用范围：**MacBook9,1 / CS4208 / x86_64 / Ubuntu 26.04 / linux-image-7.0.0-38-generic 完整包版本 7.0.0-38.38**。同一 `uname -r` 的 Ubuntu 24.04 HWE 模块不能混用。

本机已验证：50 个导入符号版本匹配；新驱动下两次普通桌面播放均正常发声，用户明确确认；音频服务重启后的配置和播放参数检查通过。修复组合包括四声道 S16_LE / 44100 Hz、数字转换器声道计数重写、功放 GPIO 保持及专用 WirePlumber profile。

未验收：整机重启/冷启动、系统睡眠恢复、耳机切换、麦克风录音和全新系统安装。发布脚本不会自动热替换模块或重启电脑；恢复前请阅读说明。

[完整修复过程、安装及回退](https://github.com/fanxing724/macbook9.1/blob/audio-ubuntu26.04-20261021/docs/ubuntu26.04-audio-fixed.md)

ZIP SHA-256：

```text
421d78c244cc5b6b7b0504dd29772d50b70c2848c19d62a9cb2bdc76a7081ea4
```
