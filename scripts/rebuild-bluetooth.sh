#!/bin/bash
# MacBook9,1 蓝牙 DKMS 模块强制重编 + 符号校验
#
# 适用场景：内核包点更新（含 uname -r 不变的 HWE/原生包切换）后蓝牙消失，
# dmesg 出现 "hci_uart: disagrees about version of symbol module_layout"。
# 详见 docs/ubuntu26.04-bluetooth.md。
#
# 用法：sudo bash scripts/rebuild-bluetooth.sh
set -euo pipefail

KVER="$(uname -r)"
NAME="macbook12-bluetooth"
VER="0.1"

[[ $EUID -eq 0 ]] || { echo "需要 root：sudo bash $0"; exit 1; }

echo "==> [1/6] 移除旧 DKMS 构建 ($NAME/$VER, $KVER)"
dkms remove "$NAME/$VER" -k "$KVER" || true

echo "==> [2/6] 重新构建（PRE_BUILD 提取内核树 drivers/bluetooth 并打 christophgysin 补丁）"
dkms build "$NAME/$VER" -k "$KVER"

echo "==> [3/6] 安装"
dkms install "$NAME/$VER" -k "$KVER" --force

echo "==> [4/6] 校验 module_layout CRC 与全部导入符号"
MOD="/lib/modules/$KVER/updates/dkms/hci_uart.ko.zst"
[[ -e $MOD ]] || MOD="/lib/modules/$KVER/updates/dkms/hci_uart.ko"
SYMVERS="/lib/modules/$KVER/build/Module.symvers"
NEW_CRC=$(modprobe --dump-modversions "$MOD" | awk '$2=="module_layout"{print $1}')
KERN_CRC=$(awk '$2=="module_layout"{print $1}' "$SYMVERS")
echo "    模块: $NEW_CRC | 内核: $KERN_CRC"
if [[ -z "$NEW_CRC" || "$NEW_CRC" != "$KERN_CRC" ]]; then
    echo "!! module_layout CRC 仍不匹配，中止（不加载模块）"
    exit 1
fi
MISMATCH=0
while read -r crc sym _; do
    k=$(awk -v s="$sym" '$2==s{print $1; exit}' "$SYMVERS")
    if [[ -n "$k" && "$k" != "$crc" ]]; then
        echo "!! 符号不匹配: $sym 模块=$crc 内核=$k"
        MISMATCH=$((MISMATCH+1))
    fi
done < <(modprobe --dump-modversions "$MOD")
echo "    导入符号不匹配数: $MISMATCH"
[[ $MISMATCH -eq 0 ]] || exit 1

echo "==> [5/6] depmod 并加载 hci_uart"
depmod -a
modprobe hci_uart
sleep 4

echo "==> [6/6] 验证"
dmesg | tail -n 25 | grep -iE "hci|bcm|bluetooth|uart" || true
rfkill list || true
hciconfig -a 2>/dev/null || true
bluetoothctl show 2>&1 | head -8 || true

if bluetoothctl show 2>/dev/null | grep -q "Controller"; then
    echo "=== 修复成功：hci0 已上线 ==="
else
    echo "=== 模块已加载但控制器未出现 ==="
    echo "若 dmesg 有 'command 0xfc18 tx timeout' / 'Reset failed (-110)'，是芯片热重启冻死："
    echo "sudo shutdown -h now 断电 30 秒后冷启动（不要 reboot）。见 docs/ubuntu24.04-history.md 2.3 节。"
    exit 2
fi
