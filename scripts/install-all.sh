#!/usr/bin/env bash
# MacBook9,1 Ubuntu 24.04 音频+蓝牙一键复原脚本
# 适用：全新安装 Ubuntu 24.04 (HWE 7.0 内核) 之后
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 0. 前置依赖"
apt install -y dkms gcc make git linux-headers-"$(uname -r)" wget curl

echo "==> 1. 探测本机内核真实上游 base 版本（#66 关键）"
BASE="$(awk '{print $NF}' /proc/version_signature)"
echo "    真实 base = $BASE (内核名: $(uname -r))"

echo "==> 2. 预下载内核源码缓存（可跳过，失败不影响在线下载）"
mkdir -p /tmp/kcache
MAJOR="$(echo "$BASE" | cut -d. -f1)"
curl -fL --retry 2 -o "/tmp/kcache/linux-$BASE.tar.xz" \
  "https://cdn.kernel.org/pub/linux/kernel/v$MAJOR.x/linux-$BASE.tar.xz" || echo "    (缓存下载失败，安装时在线下载)"

echo "==> 3. 扬声器驱动 (macbook12-audio-driver + Ubuntu base 版本补丁)"
rm -rf /tmp/mb91-install; mkdir -p /tmp/mb91-install; cd /tmp/mb91-install
curl -sL -o audio.tar.gz "https://codeload.github.com/leifliddy/macbook12-audio-driver/tar.gz/refs/heads/master"
mkdir -p audio; tar xzf audio.tar.gz -C audio --strip-components=1
cd audio
patch -p1 < "$REPO/patches/0001-ubuntu-base-version-detection.patch"
env MACBOOK12_AUDIO_KERNEL_CACHE=/tmp/kcache ./install.cirrus.driver.sh --install
cd ..

echo "==> 4. 蓝牙驱动 (macbook12-bluetooth-driver)"
curl -sL -o bt.tar.gz "https://codeload.github.com/leifliddy/macbook12-bluetooth-driver/tar.gz/refs/heads/master"
mkdir -p bt; tar xzf bt.tar.gz -C bt --strip-components=1
cd bt
sudo ./install.bluetooth.sh -i
# 本仓库把补丁源码永久化的做法（防止 /tmp 清理导致将来重编译断链）：
mkdir -p /usr/local/src
mv "$(pwd)" "/usr/local/src/macbook12-bluetooth-driver"
rm -f /usr/src/macbook12-bluetooth-0.1
ln -sfn "/usr/local/src/macbook12-bluetooth-driver" /usr/src/macbook12-bluetooth-0.1
cd ..

echo "==> 5. WirePlumber 软音量配置"
mkdir -p /etc/wireplumber/main.lua.d
cp "$REPO/config/51-macbook-cs4208-softvol.lua" /etc/wireplumber/main.lua.d/

echo "==> 6. 初始化 mixer 并保存"
amixer -c 0 sset 'Master' 100% unmute
amixer -c 0 sset 'Line Out' 100% unmute
amixer -c 0 sset 'PCM' 100%
alsactl store

echo "==> 7. initramfs 重建"
update-initramfs -u

echo ""
echo "完成！请执行冷启动（必须 shutdown，别用 reboot，蓝牙芯片需要断电复位）："
echo "   sudo shutdown -h now    # 全黑后再等 30 秒开机"
