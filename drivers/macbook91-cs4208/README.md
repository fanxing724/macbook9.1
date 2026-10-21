# MacBook9,1 CS4208：2026-10-21 本机验证源码

此目录与本机 `/usr/src/macbook12-audio-driver-0.1` 的编译输入一致，额外附带本说明和 GPL-2.0 的 COPYING。不是独立新上游项目。

- 上游：[leifliddy/macbook12-audio-driver](https://github.com/leifliddy/macbook12-audio-driver)，提交 `4cdfcdbac2db3f300cc45d9679cfd21df6590a8a`。
- 本地补丁：仓库 `patches/0002-cs4208-digital-speaker-stream.patch`，然后应用 `0003-cs4208-four-slot-playback.patch`。
- 完整来源、每个编译输入的 SHA-256 和模块身份：`packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021/manifest.json`。
- 实际加载模块 srcversion：`7DE464D96696BDDA89F5433`。

保留原源码版权注释。内核派生代码按 GPL-2.0 分发；COPYING 随源码提供。专用 ACP profile 的派生来源和 LGPL-2.1-or-later 说明保留在对应配置文件中。

本轮是针对本机的最小增量修复，仍保留上游历史的 `0x04` PCM 路径，以及向实际数字扬声器转换器 `0x0a` 镜像格式和流编号的实现；没有直接换用 issue 72 附件的整套驱动。上游历史代码的模块全局播放状态等结构未在本轮重构。

`patch_cirrus.c` 是上游为旧内核布局保留的文件，本轮验证的 7.0 内核实际编译 `patch_cirrus/cs420x.c`。不应据此声称旧内核也包含或通过了本轮修复。

重新编译时必须使用目标 Ubuntu 内核包匹配的 headers 与 `linux-source`。不要使用内核主版本相同的原版 kernel.org 私有头文件代替 Ubuntu 发行版源码。安装/重编译说明见仓库的 `docs/ubuntu26.04-audio-fixed.md`。
