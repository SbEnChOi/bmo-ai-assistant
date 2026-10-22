"""Lazy camera imports allow the demo to run without Pi dependencies."""
import io
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time


def normalize_image(data):
    """Validate a local admin upload and keep only a bounded JPEG in memory."""
    if not 0 < len(data) <= 20 * 1024 * 1024:
        raise ValueError("이미지는 20 MB 이하여야 합니다.")
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in ("JPEG", "PNG") or original.width * original.height > 16_000_000:
                raise ValueError("16 MP 이하의 JPG 또는 PNG 이미지만 사용할 수 있습니다.")
            picture = ImageOps.exif_transpose(original).convert("RGB")
            picture.thumbnail((1280, 960))
            output = io.BytesIO()
            picture.save(output, format="JPEG", quality=80)
            return output.getvalue()
    except (UnidentifiedImageError, OSError):
        raise ValueError("JPG 또는 PNG 이미지 파일을 확인하세요.") from None


class Camera:
    def __init__(self, source, image_path=None, camera_index=0):
        self.source, self.image_path, self.camera_index = source, image_path, camera_index
        self.device = None
        self.lock = threading.RLock()

    def capture(self):
        with self.lock:
            return self._capture()

    def _capture(self):
        if self.source == "demo":
            return None
        from PIL import Image, ImageOps
        if self.source == "image":
            p = Path(self.image_path)
            if p.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("20 MB 이하의 이미지를 사용하세요.")
            with Image.open(p) as original:
                picture = ImageOps.exif_transpose(original).convert("RGB")
        else:
            if self.device is None:
                from picamera2 import Picamera2
                device = Picamera2(self.camera_index)
                try:
                    device.configure(device.create_still_configuration(main={"size": (1280, 960), "format": "RGB888"}))
                    device.start()
                    time.sleep(2)
                except Exception:
                    device.close()
                    raise
                self.device = device
            # Discard queued frames: exposure must start after this call, not
            # before the user asked for a photograph (Picamera2 flush contract).
            request = self.device.capture_request(flush=True)
            try:
                picture = request.make_image("main").convert("RGB")
            finally:
                request.release()
        picture.thumbnail((1280, 960))
        output = io.BytesIO()
        picture.save(output, format="JPEG", quality=80)
        return output.getvalue()

    def close(self):
        with self.lock:
            if self.device:
                try:
                    self.device.stop()
                finally:
                    self.device.close()
                    self.device = None


class RemotePiCamera:
    """Ask the Pi's existing camera service for a fresh frame over trusted SSH."""
    def __init__(self, host, user, key_path, project, port=8765):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', host or ''):
            raise ValueError('파이 접속 주소를 확인하세요.')
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user or ''):
            raise ValueError('파이 사용자 이름을 확인하세요.')
        if not key_path or not Path(key_path).is_file():
            raise ValueError('파이 SSH 개인 키 파일을 확인하세요.')
        if not project.startswith('/') or '\n' in project or '\r' in project:
            raise ValueError('파이 프로젝트의 절대 경로를 지정하세요.')
        if not 1 <= port <= 65535:
            raise ValueError('파이 서버 포트를 확인하세요.')
        remote = f'cd -- {shlex.quote(project)} && exec .venv/bin/python -m bmo.remote_capture --port {port}'
        self.command = ['ssh', '-i', str(Path(key_path).resolve()), '-l', user,
                        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                        '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8',
                        host, remote]

    def capture(self):
        try:
            result = subprocess.run(self.command, capture_output=True, timeout=40, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError('파이 카메라 연결 시간이 초과됐어요. 유선 연결과 파이 서버를 확인해 주세요.') from None
        if result.returncode != 0:
            raise RuntimeError('파이에서 촬영하지 못했어요. 파이 카메라와 BMO 서비스가 실행 중인지 확인해 주세요.')
        try:
            return normalize_image(result.stdout)
        except ValueError:
            raise RuntimeError('파이에서 올바른 카메라 사진을 받지 못했어요.') from None

    def close(self):
        pass
