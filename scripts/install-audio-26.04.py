#!/usr/bin/env python3
"""Check or explicitly install an experimental build; speaker audio is unresolved."""
from pathlib import Path
import datetime
import hashlib
import os
import shutil
import subprocess
import sys

KERNEL = '7.0.0-38-generic'
VERSION = '7.0.0-38.38'
BASE = Path(__file__).resolve().parent.parent
PACKAGE = BASE / 'packages/ubuntu26.04/7.0.0-38.38'
ARCHIVE = PACKAGE / 'driver.dkms.tar.gz'
CONF = BASE / 'config/51-macbook-cs4208-softvol.conf'
SOURCE = Path('/usr/src/macbook12-audio-driver-0.1')
DKMS = Path('/var/lib/dkms/macbook12-audio-driver/0.1')
MODULE = Path(f'/lib/modules/{KERNEL}/updates/dkms/snd-hda-codec-cs420x.ko.zst')
NEW_CONF = Path('/etc/wireplumber/wireplumber.conf.d/51-macbook-cs4208-softvol.conf')
OLD_CONF = Path('/etc/wireplumber/main.lua.d/51-macbook-cs4208-softvol.lua')

def run(*args):
    subprocess.run(args, check=True)

def main():
    if sys.argv[1:] not in ([], ['--check'], ['--install-experimental']):
        raise SystemExit('用法：python3 scripts/install-audio-26.04.py [--check | --install-experimental]')
    check_only = sys.argv[1:] != ['--install-experimental']
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBook9,1':
        raise SystemExit('此归档仅针对 MacBook9,1 构建，停止安装。')
    if os.uname().release != KERNEL or os.uname().machine != 'x86_64':
        raise SystemExit('当前内核或架构与编译包不匹配，停止安装。')
    version = subprocess.check_output([
        'dpkg-query', '-W', '-f=${Version}', f'linux-image-{KERNEL}'
    ], text=True).strip()
    if version != VERSION:
        raise SystemExit(f'需要 Ubuntu 内核包 {VERSION}；当前为 {version}。不能混用 24.04 HWE 模块。')
    if not shutil.which('dkms'):
        raise SystemExit('请先安装 dkms：sudo apt install dkms')
    expected = (PACKAGE / 'SHA256SUMS').read_text().split()[0]
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != expected:
        raise SystemExit('编译包校验失败，停止安装。')
    for path in (SOURCE, DKMS, MODULE, NEW_CONF, OLD_CONF):
        if path.is_symlink():
            raise SystemExit(f'检测到需要人工核对的符号链接：{path}')
    if check_only:
        print('机型、架构、完整内核版本、归档 SHA-256 和目标路径预检查通过；未修改系统。')
        return
    if os.geteuid() != 0:
        raise SystemExit('请使用 sudo python3 scripts/install-audio-26.04.py --install-experimental')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path('/var/backups/macbook91-audio') / stamp
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(backup, 0o700)
    targets = {'source': SOURCE, 'dkms': DKMS, 'module': MODULE,
               'new-conf': NEW_CONF, 'old-conf': OLD_CONF}
    existed = {}
    for name, path in targets.items():
        existed[name] = path.exists()
        if path.is_dir():
            shutil.copytree(path, backup / name, symlinks=True)
        elif path.exists():
            shutil.copy2(path, backup / name)
    rollback = ['#!/bin/bash', 'set -euo pipefail', 'test "$(id -u)" = 0']
    for name, path in targets.items():
        if name in ('source', 'dkms'):
            rollback.append(f"rm -rf -- '{path}'")
            if existed[name]:
                rollback.append(f"cp -a -- '{backup / name}' '{path}'")
        elif existed[name]:
            rollback.append(f"mkdir -p -- '{path.parent}'")
            rollback.append(f"cp -a -- '{backup / name}' '{path}'")
        else:
            rollback.append(f"rm -f -- '{path}'")
    rollback.extend([f'depmod -a {KERNEL}', "echo '回退完成；请在保存工作后重启以加载原模块。'"])
    script = backup / 'rollback.sh'
    script.write_text('\n'.join(rollback) + '\n')
    script.chmod(0o700)
    try:
        run('dkms', 'ldtarball', '--archive', str(ARCHIVE), '--force')
        run('dkms', 'install', '-m', 'macbook12-audio-driver', '-v', '0.1',
            '-k', KERNEL, '--force', '-j', '1')
        NEW_CONF.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONF, NEW_CONF)
        NEW_CONF.chmod(0o644)
        OLD_CONF.unlink(missing_ok=True)
    except Exception:
        print(f'安装未完成；备份与回退脚本：{script}', file=sys.stderr)
        raise
    print(f'实验编译包已安装；扬声器无声问题尚未修复。备份：{backup}')
    print('当前内存中的模块不会自动替换；请保存工作后自行重启。不会自动重启电脑。')
    print('后续重新编译还需要与目标内核完全匹配的 linux-source 和 headers。')

if __name__ == '__main__':
    main()
