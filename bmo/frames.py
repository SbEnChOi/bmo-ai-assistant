"""Bounded local visual context. Collecting frames never calls an AI API."""
import base64
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import math
import time
from .camera import normalize_image


@dataclass(frozen=True)
class Frame:
    seq: int
    jpeg: bytes
    received: float
    timestamp: str
    source: str
    label: str
    captured: str = ''

    def caption(self, now=None):
        age = max(0, (time.monotonic() if now is None else now) - self.received)
        camera = '파이 카메라' if self.source == 'pi' else 'PC 웹캠'
        timing = '준비된 사진; 실제 촬영 시각 미확인' if self.source == 'prepared' else f'{camera}; 촬영 {self.captured or "시각 미확인"}; {age:.1f}초 경과'
        return f'프레임 #{self.seq}, 서버 수신 {self.timestamp}, {timing}, 순서/이름: {self.label}'

    def public(self, compact=False):
        jpeg = self.jpeg
        if compact:
            from PIL import Image
            with Image.open(BytesIO(jpeg)) as picture:
                picture.thumbnail((512, 384))
                for size in (512, 384, 256, 128):
                    picture.thumbnail((size, size))
                    output = BytesIO()
                    picture.save(output, 'JPEG', quality=60)
                    jpeg = output.getvalue()
                    if len(jpeg) <= 32000:
                        break
        return {'seq': self.seq, 'source': self.source, 'label': self.label,
                'caption': self.caption(), 'image_url': 'data:image/jpeg;base64,' + base64.b64encode(jpeg).decode()}


class FrameBuffer:
    def __init__(self, limit=10, window=10, clock=time.monotonic):
        self.frames = deque(maxlen=limit)
        self.window, self.clock = window, clock
        self.seq = 0
        self.version = 0
        self.last_digest = None
        self.last_pixels = None
        self.generation = 0

    def add(self, data, source='prepared', label='', captured_at=None):
        if source not in ('prepared', 'webcam', 'pi') or not isinstance(label, str):
            raise ValueError('프레임 소스와 이름을 확인하세요.')
        jpeg = normalize_image(data)
        age = 0
        captured = ''
        if source in ('webcam', 'pi') and captured_at is not None:
            if type(captured_at) not in (int, float) or not math.isfinite(captured_at):
                raise ValueError('촬영 시각을 확인하세요.')
            age = time.time() - captured_at
            if not -1 <= age <= self.window:
                raise ValueError('웹캠 프레임이 오래되었습니다. 다시 촬영하세요.')
            captured = datetime.fromtimestamp(captured_at, timezone.utc).isoformat()
            age = max(0, age)
        digest = hashlib.sha256(jpeg).digest()
        pixels = None
        unchanged = digest == self.last_digest
        if source in ('webcam', 'pi'):
            from PIL import Image
            with Image.open(BytesIO(jpeg)) as image:
                pixels = image.resize((24, 18)).convert('RGB').tobytes()
            if self.last_pixels:
                unchanged = sum(abs(a-b) for a, b in zip(pixels, self.last_pixels)) / len(pixels) <= 4
        # Suppress unchanged captures for up to five seconds, then retain a fresh
        # confirmation so a stationary live camera does not appear disconnected.
        if (self.frames and self.frames[-1].source == source and unchanged
                and (source == 'prepared' or self.clock() - self.frames[-1].received < 5)):
            return False
        if self.frames and self.frames[-1].source != source:
            self.clear()
        self.seq += 1
        self.version += 1
        self.frames.append(Frame(self.seq, jpeg, self.clock() - age, datetime.now(timezone.utc).isoformat(), source, label[:100], captured))
        self.last_digest = digest
        self.last_pixels = pixels
        return True

    def clear(self):
        self.frames.clear()
        self.last_digest = None
        self.last_pixels = None
        self.version += 1
        self.generation += 1

    def select(self, count=4):
        now = self.clock()
        recent = [f for f in self.frames if f.source == 'prepared' or now - f.received <= self.window]
        if len(recent) <= count:
            return recent
        return [recent[round(i * (len(recent) - 1) / (count - 1))] for i in range(count)]

    def snapshot(self):
        selected = self.select()
        latest = self.frames[-1] if self.frames else None
        return {'count': len(self.frames), 'selected': len(selected), 'version': self.version, 'generation': self.generation,
                'source': latest.source if latest else '', 'stale': bool(latest and not selected),
                'age_seconds': round(max(0, self.clock() - latest.received), 1) if latest else None,
                'labels': [f.label for f in self.frames]}
