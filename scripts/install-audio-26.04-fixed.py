#!/usr/bin/env python3
"""Check or install the 2026-10-21 MacBook9,1 four-slot audio build."""
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
PACKAGE = BASE / 'packages/ubuntu26.04/7.0.0-38.38/four-slot-20261021'
CONFIG = BASE / 'config/macbook91-four-slot'
SOURCE = Path('/usr/src/macbook12-audio-driver-0.1')
DKMS = Path('/var/lib/dkms/macbook12-audio-driver/0.1')
MODULE = Path('/lib/modules') / KERNEL / 'updates/dkms/snd-hda-codec-cs420x.ko.zst'
RULE = Path('/etc/wireplumber/wireplumber.conf.d/52-macbook91-4ch.conf')
ASSETS = Path('/usr/share/macbook91-cs4208/acp')


def run(*command):
    return subprocess.check_output(command, text=True).strip()


def preflight():
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBook9,1':
        raise SystemExit('此构建仅针对 MacBook9,1。')
    if os.uname().release != KERNEL or os.uname().machine != 'x86_64':
        raise SystemExit('当前内核或架构与编译包不同，停止安装。')
    for package in ('linux-image-' + KERNEL, 'linux-headers-' + KERNEL):
        if run('dpkg-query', '-W', '-f=${Version}', package) != VERSION:
            raise SystemExit(f'{package} 必须为 {VERSION}；不能混用 Ubuntu 24.04 HWE 模块。')
    if not shutil.which('dkms'):
        raise SystemExit('需要 dkms：sudo apt install dkms')
    for line in (PACKAGE / 'SHA256SUMS').read_text().splitlines():
        expected, filename = line.split()
        if Path(filename).name != filename:
            raise SystemExit('校验清单含非法路径。')
        if hashlib.sha256((PACKAGE / filename).read_bytes()).hexdigest() != expected:
            raise SystemExit('文件校验失败：' + filename)
    versions = {}
    for line in Path('/usr/src/linux-headers-' + KERNEL + '/Module.symvers').read_text().splitlines():
        columns = line.split()
        versions[columns[1]] = columns[0].lower()
    imports = run('modprobe', '--show-modversions', str(PACKAGE / MODULE.name))
    for line in imports.splitlines():
        crc, symbol = line.split()[:2]
        if versions.get(symbol) != crc.lower():
            raise SystemExit('模块导入符号版本不匹配：' + symbol)
    for path in (SOURCE, DKMS, MODULE, RULE, ASSETS):
        if path.is_symlink():
            raise SystemExit('目标是符号链接，需要先核对：' + str(path))
    for name in ('52-macbook91-4ch.conf', 'acp/macbook91-cs4208.conf',
                 'acp/macbook91-output-speaker.conf'):
        if not (CONFIG / name).is_file():
            raise SystemExit('缺少完整四声道配置：' + name)
    print(f'机型、架构、完整内核包版本、SHA-256 和 {len(imports.splitlines())} 个导入符号检查通过。')


def main():
    if sys.argv[1:] not in ([], ['--check'], ['--install']):
        raise SystemExit('用法：python3 scripts/install-audio-26.04-fixed.py [--check | --install]')
    preflight()
    if sys.argv[1:] != ['--install']:
        print('仅预检查，未修改系统。')
        return
    if os.geteuid() != 0:
        raise SystemExit('安装请使用 sudo python3 scripts/install-audio-26.04-fixed.py --install')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = Path('/var/backups/macbook91-audio') / stamp
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    backup.chmod(0o700)
    targets = {'source': SOURCE, 'dkms': DKMS, 'module': MODULE, 'rule': RULE, 'acp': ASSETS}
    existed = {}
    for name, path in targets.items():
        existed[name] = path.exists()
        if path.is_dir():
            shutil.copytree(path, backup / name, symlinks=True)
        elif path.exists():
            shutil.copy2(path, backup / name)
    # The rollback restores only the five explicitly backed-up targets.
    rollback = '''#!/usr/bin/env python3
from pathlib import Path
import os, shutil, subprocess
'''
    rollback += f'kernel = {KERNEL!r}\nbackup = Path({str(backup)!r})\n'
    rollback += f'targets = { {name: str(path) for name, path in targets.items()}!r}\n'
    rollback += f'existed = {existed!r}\n'
    rollback += '''if os.geteuid() != 0 or os.uname().release != kernel:
    raise SystemExit('Requires root on the same kernel')
for name, target in targets.items():
    path = Path(target)
    if path.is_symlink():
        raise SystemExit('Review changed symlink before rollback: ' + target)
for name, target in targets.items():
    path = Path(target)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    if existed[name]:
        saved = backup / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if saved.is_dir():
            shutil.copytree(saved, path, symlinks=True)
        else:
            shutil.copy2(saved, path)
subprocess.run(['depmod', '-a', kernel], check=True)
print('Previous files restored. Save work and reboot manually to load the previous module.')
'''
    script = backup / 'rollback.py'
    script.write_text(rollback)
    script.chmod(0o700)
    try:
        subprocess.run(['dkms', 'ldtarball', '--archive', str(PACKAGE / 'driver.dkms.tar.gz'), '--force'], check=True)
        subprocess.run(['dkms', 'install', '-m', 'macbook12-audio-driver', '-v', '0.1',
                        '-k', KERNEL, '--force', '-j', '1'], check=True)
        RULE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONFIG / '52-macbook91-4ch.conf', RULE)
        RULE.chmod(0o644)
        ASSETS.mkdir(parents=True, exist_ok=True)
        for name in ('macbook91-cs4208.conf', 'macbook91-output-speaker.conf'):
            shutil.copyfile(CONFIG / 'acp' / name, ASSETS / name)
            (ASSETS / name).chmod(0o644)
    except Exception:
        print('安装未完成；备份和回退脚本：' + str(script), file=sys.stderr)
        raise
    print('驱动和四声道配置已写入。备份和回退脚本：' + str(script))
    print('当前已加载模块未热替换；保存工作后手动重启，再进行实际发声验收。')
    print('此发布安装流程尚未做全新系统安装验收；本机已验证同源码构建的驱动和等效配置。')


if __name__ == '__main__':
    main()
