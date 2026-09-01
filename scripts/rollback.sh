#!/usr/bin/env bash
# 完全回滚到纯原装（卸掉扬声器+蓝牙 DKMS 驱动与配置）
set -euo pipefail

echo "==> 卸扬声器驱动"
if [ -x "/usr/src/macbook12-audio-driver-0.1/install.cirrus.driver.sh" ]; then
  (cd /usr/src/macbook12-audio-driver-0.1 && ./install.cirrus.driver.sh --uninstall)
else
  dkms status | grep -q macbook12-audio && echo "手动: dkms remove -m macbook12-audio-driver -v 0.1 --all"
fi

echo "==> 卸蓝牙驱动"
if [ -x "/usr/local/src/macbook12-bluetooth-driver/install.bluetooth.sh" ]; then
  (cd /usr/local/src/macbook12-bluetooth-driver && ./install.bluetooth.sh -u)
elif [ -x "/usr/src/macbook12-bluetooth-driver/install.bluetooth.sh" ]; then
  (cd /usr/src/macbook12-bluetooth-driver && ./install.bluetooth.sh -u)
fi

echo "==> 清配置"
rm -f /etc/wireplumber/main.lua.d/51-macbook-cs4208-softvol.lua

depmod -a
update-initramfs -u
echo "完成，reboot 生效"
