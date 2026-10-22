"""Optional, server-only Live sideband. Never exposes the project key to a page."""
import json
import threading
from urllib.parse import quote


def ensure_transport():
    try:
        import websocket
    except ImportError:
        raise ValueError('노을 버전 준비: python -m pip install -r requirements-live.txt') from None
    return websocket


class LiveSideband:
    def __init__(self, session_id, key, on_event, on_error):
        self.session_id, self.key = session_id, key
        self.on_event, self.on_error = on_event, on_error
        self.socket = None
        self.closed = threading.Event()
        self.send_lock = threading.Lock()

    def start(self):
        module = ensure_transport()
        self.socket = module.create_connection(
            'wss://api.openai.com/v1/live/sessions/' + quote(self.session_id, safe='') + '/attach',
            header=['Authorization: Bearer ' + self.key], timeout=8, enable_multithread=True)
        self.socket.settimeout(1)
        threading.Thread(target=self._read, daemon=True, name='bmo-live-sideband').start()

    def _read(self):
        module = ensure_transport()
        try:
            while not self.closed.is_set():
                try:
                    raw = self.socket.recv()
                except module.WebSocketTimeoutException:
                    continue
                if not raw:
                    raise RuntimeError('Live sideband closed')
                # Reflected audio is not retained, transcribed, or sent to the backend.
                if len(raw) > 2_000_000:
                    raise RuntimeError('Live event too large')
                event = json.loads(raw)
                if isinstance(event, dict) and event.get('type') in {
                    'session.started', 'session.closed', 'session.usage.updated', 'session.delegation.created',
                    'session.input_transcript.delta', 'session.output_transcript.delta', 'error'}:
                    self.on_event(event)
        except Exception:
            if not self.closed.is_set():
                self.on_error()
        finally:
            self.close()

    def send(self, event):
        with self.send_lock:
            if self.closed.is_set() or not self.socket:
                raise RuntimeError('Live 제어 연결이 닫혔습니다.')
            self.socket.send(json.dumps(event, ensure_ascii=False))

    def close(self):
        self.closed.set()
        if self.socket:
            try:
                self.socket.close(timeout=1)
            except Exception:
                pass
        self.key = ''
