# Ubuntu 26.04 · MacBook9,1 蓝牙修复记录

**2026-10-28：蓝牙控制器恢复，扫描到周围 6 台设备。** 根因与音频（2026-10-21）、摄像头（2026-10-25）相同：10-20 系统从 24.04 升级到 26.04 的过程中，内核包由 `7.0.0-38.38~24.04.4`（24.04 HWE 构建）升级为 `7.0.0-38.38`（26.04 原生构建），`uname -r` 不变、ABI 已变，DKMS 不触发重编，`hci_uart.ko` 停留在 10-14 的旧编译产物，被内核拒绝加载。强制 DKMS 重编后，`module_layout` CRC 与全部导入符号匹配，`hci0` 上线。

至此三个 DKMS 模块（音频 / 摄像头 / 蓝牙）全部针对 26.04 原生内核完成刷新。

## 环境

| 项目 | 实机信息 |
| --- | --- |
| 机器 | MacBook9,1，2016 年 12 英寸 MacBook |
| 系统 | Ubuntu 26.04.1，x86_64 |
| 蓝牙 | Broadcom BCM4350C0 UART 37.4MHz Gamay（`hci_uart_bcm`，serdev `serial1-0`） |
| 内核 | `7.0.0-38-generic` |
| 当前内核镜像和 headers 包版本 | `7.0.0-38.38` |
| 旧 headers 包版本（旧模块的编译对象） | `7.0.0-38.38~24.04.4` |
| DKMS 名称/版本 | `macbook12-bluetooth/0.1`（leifliddy 源 + christophgysin 补丁） |
| 安全启动 | 开启；DKMS 用 shim MOK 自动签名模块，签名不是本次故障原因 |

## 症状

- `bluetoothctl` 报 `No default controller available`，图形界面蓝牙消失。
- `rfkill list` 只有无线网卡，没有蓝牙条目。
- `lsmod` 中没有 `hci_uart`；DKMS 状态却显示 `macbook12-bluetooth/0.1, 7.0.0-38-generic: installed`。

**DKMS 的 installed 状态只表示有编译安装记录，不代表模块能加载。** 启动日志里真正的判决是：

```text
hci_uart: disagrees about version of symbol module_layout
```

旧模块的 `module_layout` CRC 是 `0xd954c786`，当前 headers 要求 `0xe9196a28`。与摄像头故障记录的值完全一致——同源问题。

## 根因时间线（dpkg.log / 文件时间戳）

| 时间 | 事件 |
| --- | --- |
| 10-14 20:28 | `hci_uart.ko` 针对 `7.0.0-38.38~24.04.4`（24.04 HWE headers）编译，CRC `0xd954c786` |
| 10-20 19:17–19:33 | 升级 26.04：headers/镜像包换为 `7.0.0-38.38`（26.04 原生），新 CRC `0xe9196a28`；`uname -r` 不变，**DKMS 不触发重编** |
| 10-21 | 音频模块重编刷新（见 [ubuntu26.04-audio-fixed.md](ubuntu26.04-audio-fixed.md)） |
| 10-24 20:34 | 重启进入 26.04 内核，`hci_uart` 加载被拒，蓝牙消失 |
| 10-26 | 摄像头模块重编刷新（见 [ubuntu26.04-camera.md](ubuntu26.04-camera.md)） |
| 10-28 | 蓝牙模块重编刷新（本文） |

再次印证音频记录中的判断：**即使 `uname -r` 相同，24.04 HWE 与 26.04 的预编译模块也不能混用。** 同 `uname -r` 的内核包点更新/换源后，DKMS 模块是否需要重编不能靠 DKMS 状态判断，要看模块导入符号 CRC 是否与当前 headers 匹配。

## 修复

脚本：[scripts/rebuild-bluetooth.sh](../scripts/rebuild-bluetooth.sh)。要点：

1. `dkms remove` 清除旧构建（避免残留旧二进制被原样重装）。
2. `dkms build` —— PRE_BUILD 复用缓存的 `linux-7.0.tar.xz` 提取 `drivers/bluetooth` 并照旧打 christophgysin 补丁（sed 移除 `set_device_wakeup` 调用，原理见 [ubuntu24.04-history.md](ubuntu24.04-history.md) 二节）。
3. `dkms install --force`；DKMS 用 shim MOK 对新模块签名。
4. **加载前校验**：模块 `module_layout` CRC 必须等于当前 headers 的值，并全量核对所有导入符号，不匹配则中止，不带病加载。
5. `modprobe hci_uart`，核对 dmesg / rfkill / hciconfig / bluetoothctl。

本次未改源码、未改固件、未重启系统。芯片一通话即响应，说明这次不是手记 2.1 节的热重启冻死，纯粹是模块没加载。

## 验证

| 检查 | 结果 |
| --- | --- |
| 新模块 `module_layout` CRC | `0xe9196a28`，与当前 headers 一致 |
| 导入符号 CRC 全量核对 | 0 个不匹配 |
| dmesg | `HCI UART protocol Broadcom registered` → `BCM4350C0 UART 37.4 MHz Gamay USI UHE` → `BCM (003.001.134) build 1532` |
| hciconfig hci0 | `UP RUNNING`，RX/TX errors 均为 0 |
| rfkill | 出现 `hci0: Bluetooth`，软/硬均不阻塞 |
| bluetoothctl show | Controller `78:4F:43:8D:C0:F5`，`Powered: yes` |
| 实际扫描 | `bluetoothctl scan on` 发现 6 台周围设备（含已命名手机） |

加载后 dmesg 中以下三条为 24.04 手记 5.1 节已定论的**预期现象，勿误修**：

- `BCM: firmware Patch file not found, tried: 'brcm/BCM.hcd'`（固件在芯片 ROM 中）
- `failed to write update baudrate (-16)`（ROM 模式 115200 波特率）
- `Unexpected number of ACPI GPIOs: 0`（Apple GPIO 表不完整，正是补丁存在的意义）

## 未验收

- 配对、音频外设、文件传输等实际使用未逐项验收。
- 热重启后是否仍冻死（24.04 手记 2.1 节老症状）本轮未测试；本轮故障是模块从未加载，不是芯片冻死。
- 若日后内核包点更新（尤其 `uname -r` 不变）后蓝牙再次消失，先跑 `sudo bash scripts/rebuild-bluetooth.sh`；若模块加载正常但芯片无响应（`command 0xfc18 tx timeout` / `Reset failed (-110)`），按 24.04 手记 2.3 节冷启动复位。
