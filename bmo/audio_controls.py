"""Control default PipeWire devices without recording or sending audio."""
import os
import re
import shutil
import subprocess
import sys
import threading


class AudioControls:
    TARGETS = {'speaker': '@DEFAULT_AUDIO_SINK@', 'microphone': '@DEFAULT_AUDIO_SOURCE@'}

    def __init__(self):
        self.command = shutil.which('wpctl') if sys.platform.startswith('linux') else None
        self.lock = threading.Lock()

    def run(self, *args):
        try:
            return subprocess.run([self.command, *args], check=True, capture_output=True,
                                  text=True, timeout=3, env={**os.environ, 'LC_ALL': 'C'}).stdout
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError('오디오 장치를 확인하지 못했어요. USB 연결을 확인하고 다시 시도해 주세요.') from None

    def read(self, device):
        if not self.command:
            return {'available': False, 'volume': None, 'muted': False}
        try:
            info = self.run('inspect', self.TARGETS[device])
            if 'node.name = "auto_null"' in info:
                raise RuntimeError('No physical output')
            value = self.run('get-volume', self.TARGETS[device])
            match = re.search(r'Volume:\s*(\d+(?:\.\d+)?)', value)
            if not match:
                raise RuntimeError('No volume')
            return {'available': True, 'volume': min(100, round(float(match[1]) * 100)),
                    'muted': '[MUTED]' in value}
        except RuntimeError:
            return {'available': False, 'volume': None, 'muted': False}

    def snapshot(self):
        with self.lock:
            return {device: self.read(device) for device in self.TARGETS}

    def set_volume(self, device, volume):
        if not isinstance(device, str) or device not in self.TARGETS or type(volume) is not int or not 0 <= volume <= 100:
            raise ValueError('장치와 0~100 사이의 정수 음량을 지정해 주세요.')
        with self.lock:
            if not self.read(device)['available']:
                raise ValueError('이 장치의 음량 조절을 사용할 수 없어요. 파이의 USB 연결을 확인해 주세요.')
            self.run('set-volume', self.TARGETS[device], str(volume / 100))
            if volume:
                self.run('set-mute', self.TARGETS[device], '0')
            result = self.read(device)
            if not result['available']:
                raise RuntimeError('음량 변경 후 장치 연결이 끊겼어요. 다시 연결해 주세요.')
            return {device: result}
