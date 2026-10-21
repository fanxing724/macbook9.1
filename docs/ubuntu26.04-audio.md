> 历史归档（2026-10-20）：本文保留当时失败结果。2026-10-21 已在当前会话恢复扬声器，参见[最新修复过程](ubuntu26.04-audio-fixed.md)。

# Ubuntu 26.04 升级后 CS4208 扬声器无声：诊断归档

**状态：未修复。** 本分支保留编译产物和失败实验，方便继续排查。不是可用音频发行版，未执行整机重启或冷启动验收。

## 环境与来源

- MacBook9,1，Ubuntu 26.04.1，x86_64。
- 内核包 `linux-image-7.0.0-38-generic=7.0.0-38.38`；源码 `linux-source-7.0.0=7.0.0-38.38`，headers 同版本。
- 原仓库参考提交：`21be1a3305015df7c065ffa5877b846c46fc7fb1`。
- [驱动上游](https://github.com/leifliddy/macbook12-audio-driver/tree/4cdfcdbac2db3f300cc45d9679cfd21df6590a8a)：`4cdfcdbac2db3f300cc45d9679cfd21df6590a8a`。
- 当前源码在上游基础上应用本仓库 `patches/0002-cs4208-digital-speaker-stream.patch`。它是失败候选方案，不是上游承诺的修复。

## 已证实的发现

旧 DKMS 模块存在 `disagrees about version of symbol module_layout`，内核拒绝加载并使用 Generic 驱动。即使 `uname -r` 相同，24.04 HWE 与 26.04 的预编译模块仍不能直接混用。用匹配的 Ubuntu 源码重新编译后，模块已加载，全部 50 个导入符号版本匹配；**扬声器仍无声**。

旧 WirePlumber Lua 规则迁移为 0.5+ 的 conf 规则后，实时声卡属性已确认 `api.alsa.soft-mixer=true`，但无声问题仍存在。

原播放回调使用 `0x04`，实际扬声器为数字转换器 `0x0a` → pin `0x1d`。原初始化让数字转换器保持四声道 `0x4013`，而播放 PCM 为双声道 S16_LE、44100 Hz。一次临时改成双声道 `0x4011` 后曾收到“有声音”反馈，后续多次重复与持久化尝试均无声，**该结果无法复现，不能据此判定根因**。

当前候选补丁保留原 `0x04` 路径，在 prepare 及耳机切回扬声器时同步实际格式和流编号到 `0x0a`，并刷新转换器缓存。两次独立播放（中间 PCM 关闭）均读到 `0x4011`、stream 1、D0，播放退出码 0；用户确认两次均完全无声。随后临时四声道/双声道切换也报告无声。

## 归档内容与验证边界

`packages/ubuntu26.04/7.0.0-38.38/driver.dkms.tar.gz` 是 DKMS 官方归档格式，包含对应源码、当前内核模块及构建日志。`manifest.json` 记录 SHA-256、源码版本和失败验收结果。完整诊断包还包含补丁、配置、本文与实验安装脚本。没有录音、账户凭据或签名私钥。

| 项目 | 结果 |
| --- | --- |
| 匹配 Ubuntu 源码编译，导入符号 CRC | 通过，50 个符号 |
| 模块加载与 CS4208 绑定 | 通过 |
| WirePlumber 软件音量规则 | 实时属性生效 |
| 两次独立播放的 PCM、转换器格式和退出码 | 通过 |
| 扬声器实际发声 | **失败，用户多次确认无声** |
| 耳机、麦克风、睡眠恢复、整机重启 | 未验收 |
| 归档安装脚本实际安装 | 未执行；仅静态编译及只读预检查通过 |

先只读检查包和当前环境：

```bash
python3 scripts/install-audio-26.04.py --check
```

脚本默认仅预检查。`--install-experimental` 会在 root 下备份并导入这个**已知未解决无声问题**的候选包，供明确要复现实验的人使用，不是推荐修复步骤。脚本核对机型、架构、完整内核包版本与 SHA-256；备份当前源码、DKMS 状态、模块和音量规则到 `/var/backups/macbook91-audio/<时间>/` 并生成 `rollback.sh`。不热加载、不自动重启，不处理蓝牙、Wi-Fi 或合盖策略。

## 重新编译线索

DKMS 归档内 `dkms_source_tree/` 为对应源码。构建依赖 `dkms gcc make` 和与目标内核包完全匹配的 headers、Ubuntu linux-source。上游已支持 Ubuntu 官方源码，勿套用旧 HWE 的 base-version 下载补丁。此次使用单任务 `-j 1` 编译。

归档源码导入 DKMS 后可用下列命令重编译；这是重现实验，不会保证修复声音：

```bash
sudo nice -n 10 dkms build -m macbook12-audio-driver -v 0.1 -k 7.0.0-38-generic --force -j 1
sudo dkms install -m macbook12-audio-driver -v 0.1 -k 7.0.0-38-generic --force -j 1
```

## 独立修复：音频服务重启等待

此前每次服务重启等待约 75 秒，日志出现 Realtime Portal/RTKit NoReply。按照 [PipeWire RT 模块文档](https://pipewire.pages.freedesktop.org/pipewire/page_module_rt.html) 的 `module.rt.args` 配置，绕过无响应的 Portal，继续使用 RTKit。

`config/90-direct-rtkit.conf` 是用户配置片段，分别放在：

- `~/.config/pipewire/pipewire.conf.d/90-direct-rtkit.conf`
- `~/.config/pipewire/pipewire-pulse.conf.d/90-direct-rtkit.conf`
- `~/.config/pipewire/client.conf.d/90-direct-rtkit.conf`

三个 context 合并配置已核对；一次重新启动服务后，取得有效音量响应的实测时间为 **0.802 秒**。这是服务就绪检查，**没有证明扬声器恢复**。此配置未包含在驱动安装脚本的写入范围内。音频服务重启可能恢复音量状态，需重新核对桌面音量。

## 本机备份与回退

本机原配置及各轮模块备份位于 `/var/backups/codex-system-repair/2026-10-20/`（root 私有）。`audio-driver/` 保存最初升级后存在 ABI 问题的模块；`ubuntu-audio-source/`、`ubuntu-audio-source-patched/`、`ubuntu-audio-format-mirror/` 保存各轮替换前状态。最初模块存在 ABI 错误，不能视作可用声音回退点。

初始系统配置 `rollback.sh` 只回退合盖、音量规则和用户桌面配置，**不回退此后编译的驱动或三个 RTKit 片段**。未来运行实验安装脚本产生的备份才适用它生成的专属 rollback.sh。直接 RTKit 配置在本机原先不存在，可逐一移出上述三个目录、再重启用户音频服务来撤回。回退会影响当前播放，应保存相关工作。

驱动回退需要恢复同一轮的源码、DKMS 树和模块，执行 depmod，并另行安排加载时机。没有自动执行重启、关机或对全套 snd 模块卸载。
