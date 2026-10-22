"""Update an existing Pi installation from a key-free ZIP, with source rollback."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile


def command(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--mode', choices=('live', 'realtime'), default='live')
    args = parser.parse_args()
    home = Path.home().resolve()
    target = home / 'bmo-project'
    unit = home / '.config/systemd/user/bmo.service'
    if target.is_symlink() or not (target/'bmo/private_config.py').is_file() or not unit.is_file():
        raise SystemExit('An existing, non-symlink BMO installation and user service are required.')
    secret_hash = hashlib.sha256((target/'bmo/private_config.py').read_bytes()).hexdigest()
    with urllib.request.urlopen('http://127.0.0.1:8765/api/state', timeout=4) as response:
        if json.load(response).get('realtime', {}).get('active'):
            raise SystemExit('End the current voice session before updating.')
    unit_text = unit.read_text()
    if len(re.findall(r'^ExecStart=.*$', unit_text, re.M)) != 1:
        raise SystemExit('Expected exactly one ExecStart in the BMO service.')
    backup = home/'bmo-backups'/time.strftime('final-%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    backup.chmod(0o700)
    shutil.copy2(unit, backup/'bmo.service')
    new_files = []
    with tempfile.TemporaryDirectory(prefix='.bmo-update-', dir=home) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(args.archive) as archive:
            for item in archive.infolist():
                parts = PurePosixPath(item.filename).parts
                if not parts or parts[0] != 'bmo-project' or '..' in parts or '\\' in item.filename:
                    raise SystemExit('Invalid ZIP member.')
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise SystemExit('Symlink ZIP entries are forbidden.')
                if any(part in ('.ssh', 'certs', '.venv', '.venv-camera', '.venv-live') for part in parts):
                    raise SystemExit('Private environment in ZIP.')
            archive.extractall(staging)
        project = staging/'bmo-project'
        blank = project/'bmo/private_config.py'
        if blank.read_bytes() != b'OPENAI_API_KEY = ""\nANTHROPIC_API_KEY = ""\n':
            raise SystemExit('Expected empty private configuration template.')
        python = str(target/'.venv-camera/bin/python')
        command(python, '-m', 'unittest', 'discover', '-s', 'tests', '-q', cwd=project)
        paths = [p for p in project.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                 and p.relative_to(project).as_posix() != 'bmo/private_config.py']
        for source in paths:
            relative = source.relative_to(project)
            destination = target/relative
            if not destination.resolve().is_relative_to(target) or destination.is_symlink():
                raise SystemExit('Destination outside project.')
            if destination.exists():
                saved = backup/'source'/relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
            else:
                new_files.append(relative.as_posix())
        (backup/'new-files.json').write_text(json.dumps(new_files))
        stopped = False
        try:
            command('systemctl', '--user', 'stop', 'bmo.service');stopped = True
            for source in paths:
                destination = target/source.relative_to(project)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            launcher = 'start-pi-live-noeul.sh' if args.mode == 'live' else 'start-pi.sh'
            new_unit = re.sub(r'^ExecStart=.*$',
                f'ExecStart=/usr/bin/bash {target}/{launcher} --auto-camera --observe --pc-port 8775', unit_text, flags=re.M)
            unit.write_text(new_unit)
            assert hashlib.sha256((target/'bmo/private_config.py').read_bytes()).hexdigest() == secret_hash
            command('systemctl', '--user', 'daemon-reload')
            command('systemctl', '--user', 'restart', 'bmo.service')
            for attempt in range(40):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8765/api/state', timeout=2) as response:
                        state = json.load(response)
                    assert state['dialogue_mode'] == args.mode
                    assert state['observation']['enabled']
                    break
                except (OSError, AssertionError, KeyError):
                    if attempt == 39:
                        raise RuntimeError('Updated service did not become ready.')
                    time.sleep(.5)
            print('BACKUP', backup)
            print('UPDATED', json.dumps({k:state[k] for k in ('dialogue_mode','source','voice_ready')}, ensure_ascii=False))
            print('PRIVATE_CONFIG_PRESERVED True')
        except BaseException:
            if stopped:
                command('systemctl', '--user', 'stop', 'bmo.service')
                for saved in (backup/'source').rglob('*'):
                    if saved.is_file():
                        shutil.copy2(saved, target/saved.relative_to(backup/'source'))
                for relative in new_files:
                    path = target/relative
                    if path.resolve().is_relative_to(target) and path.is_file():
                        path.unlink()
                shutil.copy2(backup/'bmo.service', unit)
                command('systemctl', '--user', 'daemon-reload')
                command('systemctl', '--user', 'start', 'bmo.service')
            raise


if __name__ == '__main__':
    main()
