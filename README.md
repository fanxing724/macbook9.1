# MacBook9,1 (2016 12" MacBook) · Ubuntu 24.04 修复手记

本仓库记录这台机器在 Ubuntu 24.04 上两大硬件顽疾（内置扬声器无声、蓝牙热重启冻死）的
完整诊断过程与最终修复方案，便于系统重装后快速复原。

## 环境

| 项 | 值 |
|---|---|
| 机型 | MacBook9,1 (A1534, Early 2016, Core m3-6Y30) |
| 系统 | Ubuntu 24.04.4 LTS (noble, HWE 栈) |
| 内核 | `7.0.0-30-generic`，**真实上游 base = 7.0.12**（看 `/proc/version_signature`！）|
| 音频 | Cirrus Logic CS4208 (codec SSID `106b:0000`) + legacy HDA（`snd_hda_intel`）|
| 蓝牙 | Broadcom BCM4350C0 UART 37.4MHz Gamay（挂在 `dw-apb-uart.3` / `hci_uart_bcm`）|
| 音频服务 | PipeWire 1.0.5 + WirePlumber 0.4.18 |

## 当前状态

| 硬件 | 状态 | 方案 |
|---|---|---|
| 📢 WiFi (brcmfmac) | ✅ 正常 | 原生 |
| 🔵 蓝牙 | ✅ 已修 | [leifliddy/macbook12-bluetooth-driver](https://github.com/leifliddy/macbook12-bluetooth-driver)（DKMS）|
| 📢 摄像头 (facetimehd) | ✅ 正常 | 原生（facetimehd DKMS）|
| 📢 麦克风 / 耳机 | ✅ 正常 | 原生 |
| 📢 内置扬声器 | ✅ **已修** | [leifliddy/macbook12-audio-driver](https://github.com/leifliddy/macbook12-audio-driver) + 本仓库 [#66 ABI 补丁](patches/0001-ubuntu-base-version-detection.patch) |

---

## 一、内置扬声器（CS4208）修复记录

### 1.1 症状

- 装完系统第一天起内置扬声器完全无声（耳机孔正常、PipeWire 正常出流）。
- `amixer scontrols` 里没有 `Speaker`，混音器只有 `Master`/`Capture` 两件套。

### 1.2 根因（两层）

1. **主线内核没有 MacBook9,1 的 CS4208 功放配置。**
   Apple 把扬声器挂在一条纯数字路径上（DAC `0x0a` → pin `0x1d`，class-D 功放供电走 GPIO0/EAPD），
   功放初始化需要一段 **从 macOS 逆向出来的私有 coef verb 序列**（1383 行）。
   主线 `sound/hda/codecs/cirrus/cs420x.c` 里 SSID 无 `0x6500` 条目，落到 `CS4208_GPIO0`，永远点不亮。
   手写 `user_pin_configs` / `hda-verb` 全部试验无效，唯一可行 = leifliddy 的 out-of-tree 驱动
   （`patch_cirrus_a1534_setup.h` 内含逐寄存器序列，且 `patch_cs4208()` 无条件 `setup_a1534()+play_a1534()`）。
2. **Ubuntu ABI 坑（本仓库补丁要解决的）。**
   上游 issue [#66](https://github.com/leifliddy/macbook12-audio-driver/issues/66)：Ubuntu HWE 内核
   （7.0.0-29 起）回迁了上游 7.0.10+ 对 `struct hda_gen_spec` 的修改。安装脚本按内核名
   `7.0.0-30-generic` 下载 **7.0.0** 源码来编译 → 结构体与本机 headers 不匹配 →
   开机 `UBSAN: array-index-out-of-bounds generic.c:1507` → **声卡整个不注册（连麦克风都挂）**。

### 1.3 修复步骤

```bash
sudo apt install -y dkms gcc make git linux-headers-$(uname -r)

git clone https://github.com/leifliddy/macbook12-audio-driver.git
cd macbook12-audio-driver

# ★ 核心：打上 Ubuntu base 版本自动探测补丁（否则必踩 #66）
patch -p1 < <本仓库>/patches/0001-ubuntu-base-version-detection.patch

# 可选：预先下载真实 base 版本源码缓存，跳过 157MB 重复下载
# （base 版本看 cat /proc/version_signature 最后一个字段，此处 7.0.12）
curl -L -o /tmp/linux-7.0.12.tar.xz https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.0.12.tar.xz

sudo env MACBOOK12_AUDIO_KERNEL_CACHE=/tmp ./install.cirrus.driver.sh --install
sudo update-initramfs -u
reboot
```

补丁作用：prepare 脚本从 `/proc/version_signature` 读取真实上游 base（如 `7.0.12`）
去下载对应源码，**内核升级后也自动跟随**，不再依赖内核名称猜版本。

### 1.4 必做配置

- **软件音量**（扬声器无硬件音量控制，不加此文件音量条无效）：
  ```bash
  sudo mkdir -p /etc/wireplumber/main.lua.d
  sudo cp config/51-macbook-cs4208-softvol.lua /etc/wireplumber/main.lua.d/
  systemctl --user restart wireplumber
  ```
- **硬件放大固定满值**：
  ```bash
  amixer -c 0 sset 'Master' 100% unmute
  amixer -c 0 sset 'Line Out' 100% unmute
  amixer -c 0 sset 'PCM' 100%
  sudo alsactl store
  ```

### 1.5 验证

```bash
cat /proc/asound/cards                    # 有 HDA Intel PCH（不是 no soundcards）
cat /sys/module/snd_hda_codec_cs420x/srcversion   # 是 dkms 新模块的 srcversion
amixer -c 0 scontrols                     # 10 个控制
timeout 4 speaker-test -D hw:0,0 -c 2 -r 48000 -t sine -f 880   # 听得见 = 成功
```

### 1.6 翻车特征与自救

| 症状 | 含义 | 处置 |
|---|---|---|
| 重启后 `no soundcards` + dmesg 有 `UBSAN...generic.c:1507` | 又踩 #66（源码版本不对）| `cd /usr/src/macbook12-audio-driver-0.1 && sudo ./install.cirrus.driver.sh --uninstall`，确认补丁在位后重装 |
| 声卡正常但扬声器无声 | softvol / 功放固化没做 | 做 1.4 |
| 耳机插拔后扬声器不切回 | 正常（驱动带 automute，等 1-2 秒）；持续则 `sudo alsactl restore` | |

### 1.7 回滚（恢复纯原装）

```bash
cd /usr/src/macbook12-audio-driver-0.1 && sudo ./install.cirrus.driver.sh --uninstall
sudo rm -f /etc/wireplumber/main.lua.d/51-macbook-cs4208-softvol.lua
sudo update-initramfs -u && reboot
```

---

## 二、蓝牙（BCM4350C0 UART）修复记录

### 2.1 症状

- 任意 `reboot`（热重启，不断电）后蓝牙芯片冻死：
  `hci0: command 0xfc18 tx timeout` / `BCM: Reset failed (-110)`，
  `bluetoothctl` 报 `No default controller available`，图形界面蓝牙整个消失。
- Apple 的 BCM4350C0 UART 供电/唤醒时序在热重启后进入死状态；
  社区（christophgysin 补丁 / Dunedan mbp-2016-linux#29）确认根因是 `hci_bcm`
  在 power 流程里调 `set_device_wakeup`，Apple 机型 GPIO 表不完整（`Unexpected number of ACPI GPIOs: 0`），
  唤醒调用把芯片卡死。

### 2.2 修复

```bash
git clone https://github.com/leifliddy/macbook12-bluetooth-driver.git
cd macbook12-bluetooth-driver
sudo ./install.bluetooth.sh -i        # DKMS；脚本编译 drivers/bluetooth 并 sed 掉 set_device_wakeup 调用
sudo depmod -a
sudo update-initramfs -u
sudo shutdown -h now                  # ★ 必须冷启动（shutdown 完全断电 30 秒再开机）给芯片复位
```

> 注意：脚本下载内核源码时同样按 `uname -r` 猜版本（7.0.0 → 回落 linux-7.0.tar.xz）。
> 对 `hci_bcm` 影响不致命（我们实测可用），但内核大版本升级后如遇编译失败，
> 把 `install.bluetooth.sh` 里的版本推导改法同音频补丁的思路。

### 2.3 已知的未治愈点

- 内核固件请求：`brcm/BCM.hcd`（按 Board-ID 命名如 `brcm/BCM4350C0-0a5c-xxxx.hcd`），
  linux-firmware 不提供 → 芯片以 **ROM 模式 + 115200 慢波特率** 运行
  （日志中 `failed to write update baudrate` 属此，不影响基本功能）。
- 如能找到 BCM4350C0 UART 的 `.hcd`（mbp16 社区有提取），放 `/lib/firmware/brcm/BCM.hcd` 即生效。
- 万一补丁哪天又失效：`sudo shutdown -h now` 断电 30 秒再开机 = 万能复活（热重启不救）。

### 2.4 回滚

```bash
cd /usr/src/macbook12-bluetooth-driver 2>/dev/null || cd /usr/local/src/macbook12-bluetooth-driver
sudo ./install.bluetooth.sh -u && sudo depmod -a
```

---

## 三、杂项备忘（这台机踩过的坑）

1. **内核升级**：三个 DKMS 模块（facetimehd / macbook12-bluetooth / macbook12-audio）都会自动重编。
   升级后**第一次开机若扬声器异常**，先 `dkms status` + 看 UBSAN，多半是 #66 类版本问题。
2. **SOFA/AVS**：此机内核默认走 legacy HDA，`snd_soc_avs`/`snd_sof_*` 模块虽加载但不占声卡，
   不要被"驱动冲突"带偏方向。
3. **热重载声卡模块** 可能触发 `modprobe: exited with irqs disabled` oops——要换驱动请用 `reboot`，
   别 `modprobe -r` 整个 snd 栈（只换 codec/intel 层可行，风险自负）。
4. `hda-verb` 可玩 `GET/SET_GPIO_DATA`（GPIO0 = 扬声器功放供电），但没 coef 序列光开 GPIO 不出声。
5. PipeWire 停启顺序坑：先停 pipewire 服务再动 ALSA；恢复时先起 `.socket` 再起服务，
   否则默认 Sink 可能钉在 `auto_null`：
   ```bash
   wpctl set-default <sink-id>
   # 或 systemctl --user restart wireplumber
   ```
6. 12 寸 MacBook 的键盘/触控板/背光全部原生，无需额外驱动。

## 四、系统全新装完后

```bash
# 一键复原（联网，需 gcc/dkms/headers 先装好）
sudo bash scripts/install-all.sh
```

## 五、固件残缺侦查结论（2026-09-01 深挖后定稿）

对"驱动加载但 dmesg 报固件缺失"的两条做了穷尽侦查，结论是**都不用补**：

### 5.1 蓝牙 `.hcd` —— 正常，别装

`dmesg` 报 `BCM: firmware Patch file not found, tried: 'brcm/BCM.hcd'` + `failed to write update baudrate (-16)`。

**leifliddy（蓝牙驱动作者）在 [issue #10](https://github.com/leifliddy/macbook12-bluetooth-driver/issues/10) 的官方定论**：
> "Yes, that's normal. Apparently, the Bluetooth controller already contains Apple's custom firmware."
> （正常，控制器 ROM 里自带 Apple 固件。）

- 该 `.hcd` 找不到是**预期行为**，控制器跑 ROM 模式 115200 波特率，功能完整。
- **切勿装通用 `.hcd`**：Apple 固件交换了 device wake / host wake 引脚功能（见 [Dunedan/mbp-2016-linux #29 评论](https://github.com/Dunedan/mbp-2016-linux/issues/29)），装通用固件会破坏引脚行为反而搞坏蓝牙。
- 从 Apple 官方下载的 "Bluetooth Update for MacBook" (157MB DMG) 经 dmg2img + 7z + cpio 逐层提取，确认只有 SMC/EFI 更新包，**里面本就没有裸蓝牙固件**——印证固件就在 ROM 里。

### 5.2 WiFi `brcmfmac4350c2-pcie` —— 只 clm_blob 真缺，且影响小

`dmesg` 报 4 个文件 `failed with error -2`，逐条核对 brcmfmac 实况：

| 文件 | 实况 | 要不要补 |
|---|---|---|
| `...Apple Inc.-MacBook9,1.bin`（定制固件）| 通用版 fallback 成功，7.35.180.133 正常加载 | ❌ |
| `...pcie.txt`（NVRAM 板级配置）| 缺失但**静默兜底**（芯片自带 NVRAM，和 macOS 同源，零报错）| ❌ |
| `...pcie.clm_blob`（法规/信道库）| 明确警告 `device may have limited channels available` | ✅ 真缺 |
| `...pcie.txcap_blob`（TX 功率校准）| 缺失，功能正常 | 🟡 次要 |

- 侦查结论：GitHub / AUR / linux-firmware 官方库**都没有** MacBook9,1 的 clm_blob/txcap_blob，唯一来源是从 macOS `AirPortBrcm4360.kext` 提取（需下载 1.5–6GB 安装器）。
- **影响面**：只限 5GHz 法规信道完整度（DFS 等）；2.4GHz 完全正常。
- **决定**：投入产出比低，**保持现状不补**。日后若强需 5GHz 满血，按"方案草案"（macOS combo update 提取 + 启动 guard 自动回滚）执行即可。

### 5.3 驱动体检总账（17 项全绿）

| 设备 | 驱动 | 来源 |
|---|---|---|
| HD Graphics 515 | i915 | 原生 |
| USB3 xHCI | xhci_hcd | 原生 |
| Serial IO I2C/UART/SPI | intel-lpss | 原生 |
| CSME HECI | mei_me | 原生 |
| HD Audio + CS4208 codec | snd_hda_intel + cs420x | DKMS 改造版 |
| SMBus | i801_smbus | 原生 |
| Apple S3X NVMe | nvme | 原生 |
| BCM4350 WiFi | brcmfmac | 原生（固件见 5.2）|
| FaceTime HD 摄像头 | facetimehd | DKMS |
| PCIe 根端口/主板 | pcieport/skl_uncore | 原生 |
| Apple SPI 键盘/触控板 | applespi | 原生(6.11+) |
| 蓝牙 BCM4350C0 | hci_uart + hci_bcm | DKMS 修补版 |
| 电池 BAT0 | applesmc | 原生 |
| CPU 微码 | intel-microcode | 原生 |
| 38 颗温度探头 | applesmc + coretemp + nvme | lm-sensors 已装 |
| 屏幕背光 | acpi_video0 | 原生 |
| 环境光感（自动亮度）| iio:device0 | 原生 |

dmesg 错误/超时扫描**零条**硬故障（仅上述两条无害固件提示）。内核 taint=12288 仅 DKMS 常规标记（randstruct + 用户请求）。**机器处于完全体状态。**

---

## 六、致谢

- [leifliddy/macbook12-audio-driver](https://github.com/leifliddy/macbook12-audio-driver) —— A1534 CS4208 逆向驱动
- [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro) —— 逆向源头
- [leifliddy/macbook12-bluetooth-driver](https://github.com/leifliddy/macbook12-bluetooth-driver) + christophgysin 补丁 —— 蓝牙
- bugzilla#195671 / Dunedan mbp-2016-linux#29 —— 诊断参考
