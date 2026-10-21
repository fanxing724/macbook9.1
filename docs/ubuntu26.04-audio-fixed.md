# Ubuntu 26.04 · MacBook9,1 扬声器修复过程

2026-10-21，本机内置扬声器恢复。新驱动下两次普通桌面语音播放均正常发声，用户明确确认；两次间隔 7 秒，不需要手动写寄存器。随后重启 WirePlumber，配置、四声道硬件参数和普通播放退出码检查也通过。

整机重启/冷启动、系统睡眠恢复、耳机切换、麦克风录音尚未验收。源码增加了耳机格式和切回扬声器的处理，但代码存在不等于实际插拔已经验证。

## 1. 初始状态：服务正常，扬声器完全无声

机器为 MacBook9,1，CS4208 编解码器，实际 codec SSID 为 `106b:6500`。Ubuntu 26.04.1，内核 `7.0.0-38-generic`，内核、headers、Ubuntu 源码包完整版本均为 `7.0.0-38.38`。

升级后旧 DKMS 模块报 `disagrees about version of symbol module_layout`，内核回退到 Generic 驱动。即使 `uname -r` 相同，原来 24.04 HWE 的二进制也不能直接用于 26.04。使用完全匹配的 Ubuntu 源码重新编译，解决了模块加载和 ABI 问题，但仍没有声音。

旧 WirePlumber Lua 音量规则移植到 0.5+ 的 conf 格式后，`api.alsa.soft-mixer=true` 已实际生效；Master、PCM、Line Out 没有静音。PipeWire、WirePlumber 运行正常，播放程序也可正常退出。这些检查均不能证明扬声器已经发声。

## 2. 昨天的失败尝试

扬声器实际走数字转换器 `0x0a` → pin `0x1d`，旧自定义 PCM 使用 `0x04`。`play_a1534()` 在数字转换器上写入四声道格式 `0x4013`，而桌面播放的是双声道 S16_LE / 44100 Hz。

第一轮补丁刷新转换器缓存，并将实际播放格式、流编号镜像到 `0x0a`。能够读到 `0x4011`、stream 1、D0，播放退出码为 0，但用户多次确认仍然无声。一次临时格式切换曾有发声反馈，后续不能复现，没有据此宣布修复。

这些失败结果保留在[2026-10-20 诊断归档](ubuntu26.04-audio.md)中，旧的 `driver.dkms.tar.gz` 和实验安装脚本也保留作历史证据。

## 3. 今天如何找到可复现的修复组合

参考同型号实机的 [issue 71](https://github.com/leifliddy/macbook12-audio-driver/issues/71) 和 [issue 72](https://github.com/leifliddy/macbook12-audio-driver/issues/72)，重点检查四声道 TDM、功放 GPIO 和转换器的独立声道计数。只审查了附件源码，没有直接安装附件中的整套驱动。

| 步骤 | 实际操作 | 实际结果 |
| --- | --- | --- |
| 原状态 | 普通桌面双声道播放 | 完全无声 |
| 直接测试 | 暂停音频服务，`hw:0,0` 播放低音量四声道语音，并写 `0x0a / 0x72d / 3` | 用户确认听到 |
| 只改桌面 profile | S16_LE / 44100 Hz / 四声道，普通桌面播放 | 用户仍确认无声 |
| 播放中写声道计数 | 普通桌面播放时显式写 `0x0a / 0x72d / 3` | 用户确认听到 |
| 持久化补丁 | 每次 prepare 和切回扬声器时重写计数，固定四声道，保留 GPIO 配置 | 两次普通播放均正常，用户明确确认 |

一个容易误判的细节：临时写入前，独立声道计数已经读作 `3`。因此本轮**没有读到“计数错误”的直接证据**；观察到的是显式重写后发声，以及将其加入驱动后两次正常播放成功。不把读回正确值当作硬件状态完整，也不把这个现象扩大为已证明的内部锁存机制。

最终补丁同时包含 GPIO 保持逻辑，本轮没有逐项隔离它对恢复发声的贡献。当前结果证明这组修改在本机有效，不能据此推导每一项单独有效。

## 4. 固化到驱动和桌面配置

驱动基于 leifliddy 上游提交 `4cdfcdbac2db3f300cc45d9679cfd21df6590a8a`，在上一轮补丁上增加[本次增量补丁](../patches/0003-cs4208-four-slot-playback.patch)：

- PCM 的最小、最大声道数都固定为 4，保持 S16_LE / 44100 Hz。
- 在扬声器 prepare 和耳机切回扬声器时，向数字转换器显式写 `AC_VERB_SET_CVT_CHAN_COUNT`。这是独立于 `STREAM_FORMAT` 的寄存器。
- 对 `106b:6500` 保持 GPIO mask `0x37`、direction `0x31`、data `0x01`，避免初始化时缩减为 GPIO0。
- 耳机 DAC `0x02` 采用同一 DMA 流的前两个声道，写入双声道格式；实际插拔尚未验收。

保留旧的 `0x04` PCM 路径与对 `0x0a` 的格式、流编号镜像。没有把此次工作描述成对上游驱动结构的全面修正。

[WirePlumber/ACP 配置](../config/macbook91-four-slot/)只提供能匹配该 PCM 的四声道模拟输出，保留输入与 HDMI 映射。`hw:%f`、S16LE / 44100 Hz、simple 上混和软件音量共同保证普通桌面内容进入对应输出格式。普通立体声内容复制到两组声道；四个物理单元各自对应哪个槽位没有单独测量。

本机使用用户目录中的配置和 profile。发布文件将 profile 路径适配到 `/usr/share/macbook91-cs4208/acp/`，便于其他账户恢复；其余有效配置与本机一致。

## 5. 构建和验收证据

| 检查 | 结果 |
| --- | --- |
| Ubuntu 源码、headers、内核包版本一致 | `7.0.0-38.38` |
| 编译 | 本地编译及实际 DKMS 编译成功，nice 10 / idle I/O / 单任务 |
| 导入符号 CRC | 全部 50 个与本机 headers 匹配 |
| 实际加载和磁盘模块 srcversion | `7DE464D96696BDDA89F5433` |
| 普通桌面播放，两次间隔 7 秒 | 均为 S16_LE / 44100 Hz / 4 声道，退出码均为 0 |
| 人耳验收 | 用户确认两次均正常发声 |
| 最终测试期间手动修正寄存器 | 没有 |
| WirePlumber 重启 | profile、硬件参数及普通播放退出码检查通过 |
| 整机重启、冷启动、系统睡眠恢复 | 未测试 |
| 耳机切换、麦克风录音 | 未测试 |
| 发布安装脚本在全新系统实际安装 | 未测试；仅静态检查、只读预检查及归档结构、源码和模块校验；特权 DKMS 导入未执行 |

详细证据：[manifest.json](../packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021/manifest.json)、[playback-validation.json](../packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021/playback-validation.json)、[编译日志](../packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021/build.log)。没有附录音、签名私钥或账号凭据。

## 6. 从发布包恢复

下载仓库首页的完整恢复 ZIP 并解压，或克隆本仓库。以下二进制安装仅适用于 **MacBook9,1 / x86_64 / Ubuntu 26.04 / 内核完整包版本 7.0.0-38.38**。若环境不同，不能跳过版本检查套用二进制。

在解压目录中先做只读检查：

```bash
python3 scripts/install-audio-26.04-fixed.py --check
```

该命令核对机型、架构、内核和 headers 的完整包版本、归档 SHA-256、50 个导入符号版本及目标路径，不改动系统。如果缺少依赖，先安装 `dkms` 和目标内核匹配的 headers，再重新检查。

需要恢复时显式执行：

```bash
sudo python3 scripts/install-audio-26.04-fixed.py --install
```

脚本先备份驱动源码、当前 DKMS 版本目录、模块和本轮系统配置，写出回退脚本，再导入原生 DKMS 归档、安装当前内核模块，并写入四声道 profile、软件音量规则。备份位于 `/var/backups/macbook91-audio/<时间>/`，权限 0700。不会自动热替换正在运行的模块或重启电脑；保存工作后自行重启，再做实际发声验收。

若之前有用户级同名 WirePlumber 规则，它可能覆盖系统规则；应核对 `device.profile-set` 指向的文件仍存在。此发布脚本不擅自删除用户配置。Secure Boot 开启的环境需要自己的模块签名信任流程，本机签名不代表其他机器已信任；本轮没有验证该场景。

在声音设置中选择内置输出，从较低音量开始测试。验证应同时检查硬件格式和实际听感：

```bash
cat /sys/module/snd_hda_codec_cs420x/srcversion
wpctl status
pw-play /usr/share/sounds/alsa/Front_Left.wav
# 播放过程中，在另一个终端检查：
cat /proc/asound/card0/pcm0p/sub0/hw_params
```

应看到 S16_LE / 44100 / 4 声道。文件路径若不存在，使用自己的短音频文件。必须确认扬声器真正发声；不能只看退出码。完整恢复 ZIP 中的安装流程没有重复执行到正在工作的本机，以免干扰已恢复状态。

## 7. 重新编译和回退

归档中的源码与[可浏览源码目录](../drivers/macbook91-cs4208/)编译输入一致。安装归档后，重新编译当前内核需要 `dkms gcc make`，以及与目标内核完整包版本匹配的 Ubuntu `linux-source` 和 headers：

```bash
sudo apt install dkms gcc make linux-headers-7.0.0-38-generic linux-source-7.0.0
# 必须先核对安装的 headers/source 版本为 7.0.0-38.38；不匹配时停止。
dpkg-query -W linux-image-7.0.0-38-generic linux-headers-7.0.0-38-generic linux-source-7.0.0
sudo nice -n 10 ionice -c 3 dkms build -m macbook12-audio-driver -v 0.1 -k 7.0.0-38-generic --force -j 1
sudo dkms install -m macbook12-audio-driver -v 0.1 -k 7.0.0-38-generic --force
```

不要拿 kernel.org 相同主版本的私有头文件代替 Ubuntu 发行版源码。不要把本包复制到别的内核目录。新内核需要重新核对 ABI、编译和人耳验收；旧的 `7.0.0-34-generic` 模块本轮未重编译。

发布安装脚本会打印它生成的 `rollback.py` 绝对路径。需要回退时，以管理员身份执行该脚本，再保存工作、手动重启，以加载上一模块。它只恢复本次备份的五个明确目标；如果目标变成符号链接则停止，要求先核对。用户配置不在系统安装脚本的回退范围内。

本次现场修复的原始备份位于本机 `/var/backups/codex-system-repair/2026-10-21/four-slot-audio/`，它与发布安装脚本未来生成的备份不是同一份。没有上传备份目录，也没有修改 NVRAM、蓝牙、网络或整机睡眠策略。
