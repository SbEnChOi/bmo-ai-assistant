"""First installation from a key-free package already uploaded over SSH."""
from pathlib import Path, PurePosixPath
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import json
import zipfile


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    staging = Path(sys.argv[1]).resolve()
    home = Path.home().resolve()
    target = home / "bmo-project"
    unit_path = home / ".config/systemd/user/bmo.service"
    resume = sys.argv[2:] == ["--resume"]
    if staging.parent != home or not staging.name.startswith(".bmo-transfer-"):
        raise SystemExit("Unexpected transfer directory.")
    if target.is_symlink() or unit_path.exists() or (target.exists() and not resume):
        raise SystemExit("Existing BMO installation found; stopping without overwriting it.")
    if resume:
        if not (target / "bmo/app.py").is_file() or not (target / "bmo/private_config.py").is_file():
            raise SystemExit("No installation to resume.")
    else:
        unpacked = staging / "unpacked"
        with zipfile.ZipFile(staging / "BMO-PushToTalk-RPi5.zip") as archive:
            for info in archive.infolist():
                parts = PurePosixPath(info.filename).parts
                if not parts or parts[0] != "bmo-project" or ".." in parts or "\\" in info.filename:
                    raise SystemExit("Unexpected package member.")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise SystemExit("Symlinks are not permitted in the package.")
            archive.extractall(unpacked)
        project = unpacked / "bmo-project"
        project.chmod(0o700)
        config = project / "bmo/private_config.py"
        config.chmod(0o600)
        shutil.copyfile(staging / "private_config.py", config)
        config.chmod(0o600)
        os.rename(project, target)
        (staging / "private_config.py").unlink()

    run(sys.executable, "-m", "venv", "--system-site-packages", str(target / ".venv"))
    if not (target / ".venv-camera").exists():
        (target / ".venv-camera").symlink_to(".venv", target_is_directory=True)
    python = str(target / ".venv/bin/python")
    run(python, "-m", "unittest", "discover", "-s", "tests", "-q", cwd=target)
    run(python, "-c", "from PIL import Image; from picamera2 import Picamera2; print('Pillow and Picamera2 imports: OK')", cwd=target)
    run(python, "-c", "from bmo.app import Engine, parse_args; e=Engine(parse_args(['--provider','openai','--model','gpt-4.1-mini'])); e.close(); print('OpenAI configuration: OK (no API request sent)')", cwd=target)
    run("bash", "start-pi.sh", "--help", cwd=target)

    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        "[Unit]\nDescription=BMO voice assistant\nAfter=network.target\n\n"
        "[Service]\nType=simple\n"
        f"WorkingDirectory={target}\nExecStart=/usr/bin/bash {target}/start-pi.sh --auto-camera --observe --pc-port 8775\n"
        "Restart=on-failure\nRestartSec=3\nUMask=0077\n\n"
        "[Install]\nWantedBy=default.target\n",
        encoding="utf-8",
    )
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "start", "bmo.service")
    for attempt in range(20):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8765/api/state", timeout=2) as response:
                state = json.load(response)
            break
        except OSError:
            if attempt == 19:
                raise SystemExit("Service did not become ready; inspect systemctl --user status bmo.service.")
            time.sleep(0.5)
    for route in ("/admin", "/phone", "/face.js", "/faces/Rosto-01.jpg", "/faces/Rosto-30.jpg"):
        with urllib.request.urlopen("http://127.0.0.1:8765" + route, timeout=3) as response:
            if response.status != 200:
                raise SystemExit("UI check failed: " + route)
    print("Installed:", target)
    print("Service: bmo.service (started; boot autostart is not enabled)")
    print("Status:", json.dumps({key: state[key] for key in ("provider", "source", "voice_ready", "camera_available")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
