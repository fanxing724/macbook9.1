# Ubuntu 26.04 · MacBook9,1 摄像头排查记录

**2026-10-26 更新：当前会话的摄像头预览已通过用户验收。** 更新驱动后持续采集不再崩溃，但 FFplay 预览仍被用户评价为“太卡了”。改用有界队列、单线程转换的 GStreamer/Wayland 预览后，前台显示约 30 fps，用户确认“现在流畅了”。随后还修复了进程退出信号打断硬件停止事务的问题。最终使用固定上游源码加退出补丁，保留原固件，没有保留实验裁剪补丁或备用固件。

预览入口：[scripts/preview-camera.sh](../scripts/preview-camera.sh)。这是本机 Wayland 环境下的实时预览方案，关闭窗口即可结束，不保存影像。驱动测试中曾出现传感器警告，不把这些警告写成已全部消除；重启、睡眠恢复、OBS 录制与视频会议仍未验收。

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
| 上游原版模块 srcversion | `9A5C9B3DB2BA89880BDB11E` |
| 加退出补丁后的模块 srcversion | `46E19D751500A2A061D503B` |
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
| 用户目视验收 | 更新驱动后 FFplay 仍卡；切换 Wayland 预览后，用户确认持续活动、流畅 |
| OBS 实际录像、浏览器通话 | 尚未验收 |
| 重启、冷启动、睡眠恢复 | 尚未验收 |

这次结果说明更新后能完成比原预览更长的持续采集，**并不证明已彻底修复**。第一轮已确认会崩溃，第二轮仍有传感器及时间戳警告；不能将错误隐藏后称为稳定。持续采集、重新开启、实际画面和重启后的可用性是不同的验证层次。

## 2026-10-26：继续区分采集、固件与显示问题

### 原始帧时间与 FFmpeg 时间基

通过 V4L2 直接采集四种模式，每种一分钟。848×588/15 fps、640×480/15 fps、848×588/30 fps、640×480/30 fps 均完成；原始帧时间没有倒退，没有超过 200 毫秒的间隔。后面三组当次测试的 SIF 错误为零，第一组为 13 次，说明不能仅按分辨率或帧率归因。

FFmpeg 改用 `-enc_time_base demux -fps_mode passthrough` 保留原始微秒时间基后，一分钟采集中没有重复 DTS 警告。原始时间戳递增，之前的输出警告不能直接等同于摄像头停止出帧；本轮没有为消除日志而伪造驱动时间戳。

### 固件与裁剪对比：验证后撤销

- 从 Apple 官方 HTTPS Boot Camp 包中提取 `S2ISP-01.55.00`，保留安装包与提取文件哈希。该版本也能采集，但一分钟仍有 8 次 SIF 警告，随后恢复原有 5.60.0 / `S2ISP-01.57.00` 固件及校准文件。没有把 Apple 二进制上传仓库。
- 测试允许自动曝光动态降低帧率；实际降低到约 7 fps，且仍有传感器警告。用户确认光线充足，未将其归因于房间暗，也没有保留该设置。
- Apple 官方规格为该机型标注 [480p 摄像头](https://support.apple.com/en-gb/112033)。据此及上游相关实机记录，临时测试仅针对 MacBook9,1 的 640×480 裁剪窗口，90 秒 2,702 帧，但仍有 70 次 SIF 警告，未证明改善。补丁未安装到 DKMS，临时模块已卸载，恢复磁盘上的原上游模块。
- PipeWire 实际应用路径连续取到 1,800 帧，正常 EOS，无固件异常或超时。最初显式 GStreamer USERPTR 测试因 fakesink 不提供导入缓冲池而协商失败，这是测试管线不完整，不是驱动失效证据。

参考线索：[同传感器固件与几何讨论 #326](https://github.com/patjak/facetimehd/issues/326)。其他机型的 CMPE 电源补丁没有应用到本机。模式数据、无效尝试与最终状态见 [round3 证据](../packages/ubuntu26.04/7.0.0-38.38/camera-20261025/round3/)。

### 真正的使用验收：修正预览显示通路

用户最初确认画面能活动，但紧接着指出“太卡了”，因此没有据“有画面”结束任务。FFplay 的本次观测 CPU 约 19.7%；改用 GStreamer 的 Wayland 原生输出，固定 640×480/YUY2/30 fps，单线程转换为 BGRx，并让最多两个缓冲的队列丢弃过期帧，避免显示积压。

新管线初期前台实际显示约 30 fps，CPU 约 13%，用户确认“现在流畅了”。较长统计中显示端有丢帧，部分时段平均显示帧率低于 30；丢弃旧画面是延迟策略的一部分，窗口遮挡也可能影响呈现，但本轮没有隔离证明每次丢帧的原因。不能据相机标称 30 fps 宣称所有帧都被显示。

本机“摄像头预览”菜单已切换到这条管线。录像/会议软件有自己的显示、编码与缓冲策略，需要分别实测，不能用本次预览替代。

```bash
sh scripts/preview-camera.sh
```

最终入口使用 [camera-preview.py](../scripts/camera-preview.py) 创建 GTK 原生窗口，依赖系统 Python 的 PyGObject、GTK 3、GStreamer、v4l2src、videoconvert、gtkwaylandsink 以及运行中的 Wayland 桌面。本机这些依赖已存在，没有为预览增加常驻服务。当前 initramfs 未包含 facetimehd，不需要为本次摄像头模块更新重建启动镜像；整机重启仍未实测。

命令行 Wayland 管线在一次自动退出中留下了进程，因此最终入口没有继续依赖命令行退出行为。原生窗口关闭时，在工作线程中把管线切到 NULL，同时保持 GTK 主循环继续分发 Wayland 事件，待最后的显示缓冲返回后再销毁窗口、退出。只退出本预览自己的进程；没有录制需要写入文件的 EOS 尾部。

安装到本机默认菜单入口后，原生窗口持续显示三十秒并自动正常退出，退出码 0、无残留进程。再次打开并发送 SIGTERM，也以退出码 0 正常结束，停止约 0.285 秒，摄像头模块引用计数恢复为 0；无 IO 超时、摄像头 DMA 错误、Data Abort、SIF 错误或程序警告。见 native-preview-verification.json。没有将命令行预览的强制退出结果冒充为原生程序正常退出。

### 退出时的超时与 DMA 错误

三分钟 Wayland 自动预览在 SIGTERM 结束时，记录到一次 `IO: timeout`，随后出现三条摄像头 DMA 写访问错误；当时没有 SIF 错误或固件 Data Abort，后续短时重新采集也成功，不能把它混同于第一轮的持续预览固件崩溃。

源码中的 `fthd_channel_wait_ready()` 使用 `wait_event_interruptible_timeout()`，把收到信号返回的负值也当作超时。进程退出时带着待处理信号，已发出的固件停止命令因此可能尚未完成，驱动就进入释放缓冲区的路径。补丁使已提交事务以原有两秒上限完成等待，并配套把 IRQ 唤醒改为 `wake_up_all()`，同时唤醒不可中断等待者。

首轮只修改等待而未配套修改唤醒，造成命令等到定时器上限才完成；这个本地试验模块未写入 DKMS，测试发现后即修正。最终补丁只修改两个文件，不修改采集几何、帧率、声音、系统 IOMMU 设置或启动参数。

临时加载最终补丁后，分别对本轮自己启动的 GStreamer 采集进程发送 SIGINT、SIGTERM、SIGKILL，每次随后重新采集 30 帧。三组均重新采集成功，停止分别耗时约 0.266、0.166、0.116 秒；没有 IO 超时、摄像头 DMA 错误、Data Abort 或 SIF 错误。信号退出码 -15/-9 是测试预期，不是错误退出验收失败。此验证没有终止任何无关进程。

随后将这两个修改文件写入已有 DKMS 源码，备份原上游源码、模块和当前内核 DKMS 构建目录，再经 DKMS 构建、签名、安装与加载。磁盘模块和实际加载模块的 srcversion 均为 `46E19D751500A2A061D503B`，122 个导入符号全部匹配。安装后的模块重复三种退出/重开测试全部通过，停止分别约 0.166、0.116、0.115 秒，没有上述错误；详见 final-installed.json、shutdown-verification.json。没有上传签名私钥或含私钥的 DKMS 归档。

补丁：[0004-facetimehd-complete-command-on-exit.patch](../patches/0004-facetimehd-complete-command-on-exit.patch)。其范围是进程退出信号引发的提前释放；真实硬件永久失去响应时的全面恢复机制，本轮没有验证或承诺。

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
# 将 /path/to/macbook9.1 替换为本修复记录仓库的实际路径。
git apply /path/to/macbook9.1/patches/0004-facetimehd-complete-command-on-exit.patch
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

关闭摄像头程序后，先卸载摄像头模块，再恢复备份源码、DKMS 当前内核目录和模块文件，执行 `depmod -a`。模块可能为 `.ko` 或 `.ko.zst`，恢复时要将本次新模块另行归档，避免两种后缀的不同模块同时残留。只回退摄像头相关目标，不动声音或其他 DKMS 模块。退出补丁安装前另外保留了固定上游源码及模块的备份；恢复该备份可保留上游修复，但会重新暴露本次退出信号问题。

恢复最早的 ABI 不匹配模块后，摄像头会重新不可用；恢复第一轮重新编译模块则会恢复到“短时可用但持续预览崩溃”的已知问题版本。回退不是稳定性修复。

仓库仅记录技术参数、统计、源码来源和操作，不上传摄像头图像、视频、Apple 固件、用户凭据或模块签名私钥。证据目录：[camera-20261025](../packages/ubuntu26.04/7.0.0-38.38/camera-20261025/)。
