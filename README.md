<!-- fanxing-style:start -->
<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://fanxing724.github.io/new-make/fanxing724/projects/macbook9.1/cover.light.svg">
  <img alt="MacBook 9,1 · 修复手记" src="https://fanxing724.github.io/new-make/fanxing724/projects/macbook9.1/cover.svg" width="100%">
</picture>

**旧设备的下一页，写在一次次排查里。**

让一台旧 MacBook 继续工作，需要一点耐心，也需要保留证据。这里记录系统、驱动与硬件的排查过程；实验成功与否，以实际使用结果为准。

<sub>番星 / 星轨手记 · <a href="https://fanxing724.github.io/new-make/fanxing724/projects/style.html">风格样板</a> · <a href="https://fanxing724.github.io/">个人小站</a></sub>
<!-- fanxing-style:end -->

# MacBook9,1 · Ubuntu 硬件修复手记

记录 2016 款 12 英寸 MacBook 的音频、蓝牙等硬件修复，并保存对应源码、编译模块和配置，方便日后恢复。

## 2026-10-28：蓝牙恢复，三个 DKMS 模块全部完成 ABI 刷新

升级 26.04 时内核包由 `7.0.0-38.38~24.04.4`（HWE）换为 `7.0.0-38.38`（原生），`uname -r` 不变但 ABI 已变，DKMS 不重编。音频、摄像头此前已分别重编；本次重编最后一个滞留的 `hci_uart`，`module_layout` CRC 与全部导入符号校验通过后加载，`hci0` 上线并扫描到周围设备。芯片本身未冻死，无需冷启动。

- [完整排查时间线、修复与验证](docs/ubuntu26.04-bluetooth.md)
- [蓝牙模块重编与校验脚本](scripts/rebuild-bluetooth.sh)

## 2026-10-26：摄像头预览恢复，用户确认流畅

更新固定上游驱动后，十分钟持续采集与反复开启通过。FFplay 预览仍被用户评价为“太卡了”；改用有界队列的 GStreamer/Wayland 预览后，用户确认“现在流畅了”。另补齐进程退出时的固件等待与唤醒，SIGINT、SIGTERM、SIGKILL 后均能重新采集，未复现退出超时或 DMA 错误。固件与裁剪实验已回退。测试中出现过传感器警告；重启、睡眠恢复、录像与会议软件仍需分别验收。

- [完整摄像头排查、构建与回退说明](docs/ubuntu26.04-camera.md)
- [本地摄像头预览脚本](scripts/preview-camera.sh)
- [符号校验与采集统计](packages/ubuntu26.04/7.0.0-38.38/camera-20261025/)

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
