"""Preview/apply MPI5008 GPIO touch on Pi 5; retain the working HDMI/camera setup.

Uses the kernel's existing ADS7846 overlay, not the legacy LCD-show installer.
Wiring and baseline parameters: https://github.com/goodtft/LCD-show/blob/master/LCD5-show
Supported overlay parameters: /boot/firmware/overlays/README (ads7846).
"""

import argparse
from datetime import datetime, timezone
import difflib
import os
from pathlib import Path
import re
import shutil
import tempfile


BEGIN = '# BEGIN BMO MPI5008 TOUCH'
END = '# END BMO MPI5008 TOUCH'
TOUCH = ('dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,'
         'swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900')
BLOCK = '\n'.join((BEGIN, '[all]', 'dtparam=spi=on', TOUCH, END)) + '\n'


def configured_text(original):
    """Append one managed block; reject ambiguous/custom SPI0 touch settings."""
    if BEGIN in original or END in original:
        if original.count(BEGIN) != 1 or original.count(END) != 1 or original.count(BLOCK) != 1:
            raise ValueError('The BMO touch block was edited or is incomplete; inspect config.txt first.')
        # Inspect outside the block too, so a conflicting later edit is not ignored.
        unmanaged = original.replace(BLOCK, '')
    else:
        unmanaged = original
    for raw in unmanaged.splitlines():
        line = re.sub(r'\s+', '', raw.partition('#')[0]).lower()
        if re.match(r'dtparam=(?:[^,]+,)*spi=(?:off|0)(?:,|$)', line):
            raise ValueError('An explicit SPI disable setting exists; inspect config.txt first.')
        if line.startswith('include'):
            raise ValueError('An included configuration exists; inspect its SPI settings first.')
        if line.startswith('dtoverlay='):
            name = line.split('=', 1)[1].split(',', 1)[0]
            if name in ('ads7846', 'piscreen') or name.startswith(('spi0-', 'waveshare')):
                raise ValueError('Another SPI0/touch overlay exists; inspect config.txt first.')
    if BLOCK in original:
        return original
    return original.rstrip('\n') + '\n\n' + BLOCK


def save_config(config, updated):
    """Back up before atomic replacement; return the recoverable backup path."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = config.with_name('config.txt.bmo-display-backup-' + stamp)
    shutil.copy2(config, backup)
    fd, temporary = tempfile.mkstemp(prefix='.bmo-touch-', dir=config.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, config.stat().st_mode & 0o777)
        os.replace(temporary, config)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Requires sudo; backs up config first')
    args = parser.parse_args()
    model_path = Path('/proc/device-tree/model')
    if not model_path.exists() or not model_path.read_text().rstrip('\0').startswith('Raspberry Pi 5'):
        parser.error('This setup is only for Raspberry Pi 5 + MPI5008 on the first 26 GPIO pins.')
    if not Path('/boot/firmware/overlays/ads7846.dtbo').is_file():
        parser.error('The installed Raspberry Pi firmware does not contain ads7846.dtbo.')
    for device in Path('/sys/bus/spi/devices').glob('spi0.*'):
        driver = device / 'driver'
        if driver.exists() and driver.resolve().name not in ('spidev', 'ads7846'):
            parser.error('SPI0 already has a different device: ' + device.name)
    config = Path('/boot/firmware/config.txt')
    original = config.read_text()
    try:
        updated = configured_text(original)
    except ValueError as exc:
        parser.error(str(exc))
    if updated == original:
        print('MPI5008 touch configuration already matches. No changes made.')
        print('If not rebooted yet, reboot and check: xinput list')
        return
    print(''.join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                                      fromfile=str(config), tofile=str(config) + ' (proposed)')))
    if not args.apply:
        print('Preview only. Apply with: sudo python3 tools/configure_pi_display.py --apply')
        return
    if os.geteuid() != 0:
        parser.error('Run with sudo to apply this boot configuration.')
    backup = save_config(config, updated)
    print('Saved. Backup: ' + str(backup))
    print('Reboot to load GPIO touch. HDMI and camera configuration were retained.')


if __name__ == '__main__':
    main()
