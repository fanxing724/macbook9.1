# Ubuntu 26.04 · MacBook9,1 摄像头排查记录

2026-10-25，内置摄像头先因旧模块 ABI 不匹配无法加载。重新编译后短时采集成功，但用户随后报告预览卡住；内核日志确认摄像头固件出现传感器错误和异常。不能将第一轮短时采集成功视为完整修复。

第二轮采用固定上游版本，修正本机仍在使用旧源码的问题。持续采集与反复开启验证结果见本文的验证表；重启、睡眠恢复和真实视频会议仍需分别验收。

## 环境

| 项目 | 实机信息 |
| --- | --- |
| 机器 | MacBook9,1，2016 年 12 英寸 MacBook |
| 系统 | Ubuntu 26.04.1，x86_64 |
| 摄像头 | Broadcom FaceTime HD，PCI ID `14e4:1570` |
| 内核 | `7.0.0-38-generic` |
| 内核镜像和 headers 包版本 | `7.0.0-38.38` |
| DKMS 名称/版本 | `facetimehd/0.7.0.1`；该版本号不能唯一标识源码提交 |
| 最终采用的上游提交 | [`6dc8cd85e87993ff21cb01eb333ff42afb058551`](https://github.com/patjak/facetimehd/commit/6dc8cd85e87993ff21cb01eb333ff42afb058551) |
| 新模块 srcversion | `9A5C9B3DB2BA89880BDB11E` |
| 固件 | `5.60.0`，使用本机已有文件，没有重新下载或重新分发 |
| 固件 SHA-256 | `240ef2e991f1d089d8228ce11d92b66bfa4b3d7289ec4fee228b64a713024330` |
| 驱动报告的传感器尺寸 | `848×588`；不据型号名中的“720p”宣称可采集 1280×720 |

## 第一层故障：模块根本没有加载

本机已有源码、固件和 DKMS 安装记录，但没有 `/dev/video*`。启动日志为：

```text
facetimehd: disagrees about version of symbol module_layout
```

旧模块的 `module_layout` CRC 是 `0xd954c786`，当前 headers 要求 `0xe9196a28`。旧模块导入的 116 个符号中有 61 个不匹配。即使 `uname -r` 和 vermagic 相同，也不能据此认定不同发行版构建的模块 ABI 一致。

先保留旧模块和 DKMS 内核目录，用当前 headers、nice 10、两个编译任务重编译本机已有源码。新模块的 117 个导入符号全部匹配，安装后出现 `/dev/video0`，PipeWire 识别 Apple Facetime HD。640×480、30 fps 短时采集通过；图像亮度存在分布，首尾帧不同，没有保存图像。

## 第二层故障：短时出帧，持续预览后固件崩溃

用户随后报告画面卡住。预览已经退出后，内核日志中仍能确认以下故障链：

1. 大量 `SIF errors`，错误值包括 `0x8a` 和 `0xa8e`。
2. 摄像头固件报告 `Type: 4 (Data Abort)`。
3. 后续出现 `IO: timeout`。

这是摄像头固件侧发生异常的直接证据，不能仅通过更换预览播放器解释。未据此断言硬件损坏。

对照源码发现：

- 本机源码的 `VIDIOC_S_PARM` 存储的是毫秒帧间隔，启动通道时却将该值乘 256 作为帧率传入固件；例如 30 fps 请求会变为约 33 fps 指令，最初 15 fps 测试还曾对应 66 fps 指令，但读回接口始终报告 30 fps。
- 本机源码缺少上游的缓冲区页内偏移、散列表遍历及停止流状态修复。
- 上游已修改裁剪和缩放逻辑，并增加裁剪边界、尺寸及帧率处理。

上述差异是更新源码的依据；本轮没有逐项隔离所有差异对崩溃的贡献，不能把某一处单独归因为已证实的唯一根因。上游缓冲区修改见 [PR #355](https://github.com/patjak/facetimehd/pull/355)。固件哈希与[上游固件提取工具](https://github.com/patjak/facetimehd-firmware)中的 5.60.0 记录一致，因此保留固件和校准文件。

## 第二轮修复

1. 关闭摄像头使用程序；通过卸载、重新加载 `facetimehd` 恢复固件，没有重启系统。崩溃后的卸载过程曾等待超时，不强制卸载模块。
2. 下载并固定上游提交，在用户工作目录以 `nice -n 10 make -j2` 预编译。
3. 另外备份当前 `/usr/src/facetimehd-0.7.0.1`、DKMS 当前内核目录和已重建的模块。
4. 将固定提交的源码放入现有 DKMS 源码目录，再针对当前内核执行 `dkms build --force -j 2`。
5. 卸载摄像头模块，通过 DKMS 安装新模块，重新加载摄像头。
6. 核对实际安装模块的 122 个导入符号，全部与当前 headers 匹配。

不修改声音驱动、系统代理、Codex 或 OpenCode 配置，不重启，不改变内核启动参数。

## 验证

| 检查 | 结果 |
| --- | --- |
| 当前安装源码与固定提交的 23 个跟踪文件一致 | 全部一致，见 source-manifest.json |
| 当前安装模块符号 CRC | 122 个全部匹配，见 upstream-verification.json |
| 持续采集 640×480、30 fps | 完成 600 秒，18,013 帧，约 30.02 fps，退出码 0，无卡死或中断 |
| 十分钟内固件 Data Abort / IO timeout | 均为 0 |
| 十分钟内传感器 SIF 错误 | 116 次，仍未消除 |
| FFmpeg 时间戳 | 出现重复 DTS 警告，仍需继续排查 |
| 重新开启 640×480、15 fps | 15 秒完成，15 个不同的 1 fps 抽样画面，SIF 错误 1 次，无固件崩溃或超时 |
| 再次开启 848×588、30 fps | 15 秒完成，15 个不同的抽样画面，SIF 错误 2 次，无固件崩溃或超时 |
| 再次开启 640×480、30 fps | 15 秒完成，15 个不同的抽样画面，SIF 错误 0 次，无固件崩溃或超时 |
| 用户目视验收、OBS 实际录像、浏览器通话 | 第二轮尚未验收 |
| 重启、冷启动、睡眠恢复 | 尚未验收 |

这次结果说明更新后能完成比原预览更长的持续采集，**并不证明已彻底修复**。第一轮已确认会崩溃，第二轮仍有传感器及时间戳警告；不能将错误隐藏后称为稳定。持续采集、重新开启、实际画面和重启后的可用性是不同的验证层次。

## 复现与重新构建

以下是本机操作的可复查步骤，不是跨机型的一键安装承诺。先关闭所有摄像头程序，核对机型、架构、目标内核和 headers 完整包版本。需要 `git`、`dkms`、`gcc`、`make` 和匹配的 headers。

```bash
uname -r
cat /sys/class/dmi/id/product_name
dpkg-query -W linux-image-7.0.0-38-generic linux-headers-7.0.0-38-generic
dkms status -m facetimehd
modinfo -n facetimehd
```

固定已测试的源码，而不是假定同名 DKMS 版本内容不变：

```bash
git clone https://github.com/patjak/facetimehd.git
cd facetimehd
git checkout --detach 6dc8cd85e87993ff21cb01eb333ff42afb058551
nice -n 10 make -j2
```

安装前至少将 `/usr/src/facetimehd-0.7.0.1`、`/var/lib/dkms/facetimehd/0.7.0.1/7.0.0-38-generic` 和 `modinfo -n facetimehd` 返回的模块文件备份到独立目录；同时保留固件原样。确认没有其他代理或包管理操作正在修改这些目录，再将固定提交的源码安装到对应 `/usr/src` 目录。

本机使用已有 DKMS 注册记录，实际重建命令为：

```bash
sudo nice -n 10 dkms build -m facetimehd -v 0.7.0.1 -k 7.0.0-38-generic --force -j 2
sudo modprobe -r facetimehd
sudo dkms install -m facetimehd -v 0.7.0.1 -k 7.0.0-38-generic --force
sudo modprobe facetimehd
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

如果尚未注册 DKMS 源码，需要另外执行对应版本的 `dkms add`。其他内核不能直接复制本机二进制模块，应使用对应 headers 构建。本机没有 Secure Boot，未验证其他机器的模块签名信任流程。

采集测试只计算帧数，不保存或上传视频：

```bash
timeout 630s ffmpeg -hide_banner -nostdin \
  -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 \
  -i /dev/video0 -an -t 600 -f null -
```

图像应由本人在本机预览验收。OBS 中选择视频采集设备 Apple Facetime HD；本机短时阶段使用 YUYV、640×480、30 fps。

## 回退与资料范围

关闭摄像头程序后，先卸载摄像头模块，再恢复备份源码、DKMS 当前内核目录和模块文件，执行 `depmod -a`。模块可能为 `.ko` 或 `.ko.zst`，恢复时要将本次新模块另行归档，避免两种后缀的不同模块同时残留。只回退摄像头相关目标，不动声音或其他 DKMS 模块。

恢复最早的 ABI 不匹配模块后，摄像头会重新不可用；恢复第一轮重新编译模块则会恢复到“短时可用但持续预览崩溃”的已知问题版本。回退不是稳定性修复。

仓库仅记录技术参数、统计、源码来源和操作，不上传摄像头图像、视频、Apple 固件、用户凭据或模块签名私钥。证据目录：[camera-20261025](../packages/ubuntu26.04/7.0.0-38.38/camera-20261025/)。
