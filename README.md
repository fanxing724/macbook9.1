# MacBook9,1 · Ubuntu 硬件修复手记

记录 2016 款 12 英寸 MacBook 的音频、蓝牙等硬件修复，并保存对应源码、编译模块和配置，方便日后恢复。

## 2026-10-21：Ubuntu 26.04 内置扬声器已恢复

**本机当前会话已通过人耳验收：两次普通桌面播放均能听到，声音正常，两次之间空闲 7 秒，期间没有手动写寄存器。** 音频服务重启后，四声道配置、硬件参数和普通播放退出码检查也通过。

修复组合是：匹配 Ubuntu 内核 ABI 的驱动、固定 S16_LE / 44100 Hz / 四声道、在播放准备及耳机切回扬声器时显式写入数字转换器的独立声道计数、保留功放 GPIO 配置，以及 WirePlumber 专用 profile 与软件音量。只改音量或只把桌面切成四声道，未能解决本机问题。

**整机重启/冷启动、系统睡眠恢复、耳机切换和麦克风录音尚未验收。** 本次只验证这台机器和下列内核，不承诺其他机型、其他内核或全新安装流程已验证。

| 项目 | 本次验证环境 |
| --- | --- |
| 机型 / 编解码器 | MacBook9,1 / CS4208，codec SSID `106b:6500` |
| 系统 | Ubuntu 26.04.1，x86_64 |
| 内核及 Ubuntu 源码包版本 | `7.0.0-38-generic` / `7.0.0-38.38` |
| 音频服务 | PipeWire 1.6.2 / WirePlumber 0.5+ |
| 实际加载模块 srcversion | `7DE464D96696BDDA89F5433` |
| 编译检查 | 50 个导入符号版本匹配，单任务编译 |

## 下载与使用

- [GitHub Release 发布产物（Assets）](https://github.com/fanxing724/macbook9.1/releases/tag/audio-ubuntu26.04-20261021)
- [完整恢复 ZIP：源码、模块、配置、安装脚本和说明](downloads/macbook91-audio-ubuntu26.04-7.0.0-38.38-fixed-20261021.zip)
- [ZIP SHA-256](downloads/macbook91-audio-ubuntu26.04-7.0.0-38.38-fixed-20261021.zip.sha256)
- [完整修复过程、安装、验证和回退](docs/ubuntu26.04-audio-fixed.md)
- [可检查的驱动源码](drivers/macbook91-cs4208/)
- [原生 DKMS 归档及单独模块](packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021/)
- [本次补丁](patches/0003-cs4208-four-slot-playback.patch) / [四声道配置](config/macbook91-four-slot/)

先解压完整 ZIP 或克隆仓库，进行只读预检查：

```bash
python3 scripts/install-audio-26.04-fixed.py --check
```

同一 `uname -r` 的 Ubuntu 24.04 HWE 模块不能和本包混用。安装需要完整匹配的机型、架构和 Ubuntu 内核包版本；详见说明。发布安装脚本仅完成静态检查和只读预检查，没有在全新系统执行安装验收。本机运行的是相同源码构建的驱动及等效配置。

## 历史记录

- [2026-10-20：ABI 修复后仍然无声的诊断过程](docs/ubuntu26.04-audio.md)，原失败编译包保留在版本目录根部，不要当作今天的恢复包安装。
- [升级前 Ubuntu 24.04 的音频、蓝牙、摄像头等修复手记](docs/ubuntu24.04-history.md)。旧的 `install-all.sh` 和旧安装方法属于该历史环境。

驱动基于 [leifliddy/macbook12-audio-driver](https://github.com/leifliddy/macbook12-audio-driver)；本次也参考了同型号实机的 [issue 71](https://github.com/leifliddy/macbook12-audio-driver/issues/71) 和 [issue 72](https://github.com/leifliddy/macbook12-audio-driver/issues/72)。源码版权与来源说明见[驱动目录](drivers/macbook91-cs4208/README.md)。
