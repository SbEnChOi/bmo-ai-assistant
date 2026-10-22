"""Preview or apply a Camera Module v1/v2 configuration on a Raspberry Pi 5."""

import argparse
from datetime import datetime, timezone
import difflib
import os
from pathlib import Path
import re
import shutil
import tempfile


SENSORS = {'ov5647': 'Camera Module v1 OV5647', 'imx219': 'Camera Module v2 IMX219'}


def configured_text(original, port, sensor='ov5647'):
    """Replace one standard v1/v2 overlay; preserve other boot configuration."""
    if port not in (0, 1):
        raise ValueError('Camera port must be 0 or 1.')
    if sensor not in SENSORS:
        raise ValueError('Supported sensors are ov5647 and imx219.')
    overlay = 'dtoverlay=' + sensor + (',cam0' if port == 0 else '')
    lines = original.splitlines()
    camera_indices = [i for i, line in enumerate(lines) if re.match(
        r'^\s*dtoverlay\s*=\s*(ov\d+|imx\d+)', line)]
    supported_overlays = {'dtoverlay=' + name + suffix for name in SENSORS for suffix in ('', ',cam0')}
    if camera_indices and (len(camera_indices) != 1 or lines[camera_indices[0]].strip() not in supported_overlays):
        raise ValueError('A different or multiple manual camera overlay exists; inspect config.txt first.')
    detect = [i for i, line in enumerate(lines) if re.match(r'^\s*camera_auto_detect\s*=', line)]
    if len(detect) != 1 or lines[detect[0]].strip() not in ('camera_auto_detect=0', 'camera_auto_detect=1'):
        raise ValueError('Expected exactly one standard camera_auto_detect setting; inspect config.txt first.')
    lines[detect[0]] = 'camera_auto_detect=0'
    comment = '# BMO: ' + SENSORS[sensor] + ' on CAM/DISP ' + str(port)
    if camera_indices:
        lines[camera_indices[0]] = overlay
        lines = [comment if re.fullmatch(r'# BMO: Camera Module v[12] (OV5647|IMX219) on CAM/DISP [01]', line)
                 else line for line in lines]
    else:
        lines.extend(['', '[all]', comment, overlay])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, choices=(0, 1), required=True)
    parser.add_argument('--sensor', choices=tuple(SENSORS), default='ov5647',
                        help='ov5647 for Camera v1 / Rev 1.3; imx219 for Camera v2')
    parser.add_argument('--apply', action='store_true', help='Requires sudo; backs up config first')
    args = parser.parse_args()
    model = Path('/proc/device-tree/model').read_text().rstrip('\0')
    if not model.startswith('Raspberry Pi 5'):
        parser.error('This script is only for Raspberry Pi 5.')
    config = Path('/boot/firmware/config.txt')
    original = config.read_text()
    try:
        updated = configured_text(original, args.port, args.sensor)
    except ValueError as exc:
        parser.error(str(exc))
    if updated == original:
        print('Camera configuration already matches. No changes made.')
        return
    print(''.join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                                      fromfile=str(config), tofile=str(config) + ' (proposed)')))
    if not args.apply:
        print('Preview only. Add --apply with sudo to save.')
        return
    if os.geteuid() != 0:
        parser.error('Run with sudo to apply this system configuration.')
    backup = config.with_name('config.txt.bmo-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    shutil.copy2(config, backup)
    fd, temporary = tempfile.mkstemp(prefix='.bmo-camera-', dir=config.parent)
    try:
        with os.fdopen(fd, 'w', newline='\n') as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, config.stat().st_mode & 0o777)
        os.replace(temporary, config)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Saved. Backup: ' + str(backup))
    print('Reboot to load the camera driver, then run: rpicam-hello --list-cameras')


if __name__ == '__main__':
    main()
