"""BMO push-to-talk server: one robot, one bounded conversation in memory."""
import argparse
import base64
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import unquote
from .audio import MAX_AUDIO, OpenAISpeech, validate_audio
from .audio_controls import AudioControls
from .emotions import fallback_emotion, normalize_emotion
from .camera import Camera, RemotePiCamera, normalize_image
from .conversation import Conversation
from .frames import Frame, FrameBuffer
from .observation import Observation
from .realtime import Realtime
from .live import Live
from .photo_intent import requests_photo, FRESH_PHOTO_NOTE

WEB = Path(__file__).with_name("web")


class Cancelled(Exception):
    pass


class Engine:
    def __init__(self, args):
        self.args = args
        self.camera = (RemotePiCamera(args.pi_host, args.pi_user, args.pi_key, args.pi_project, args.pi_port)
                       if args.source == 'ssh-pi' else Camera(args.source, args.image, args.camera_index))
        self.llm = Conversation(args.provider, args.model)
        self.speech = OpenAISpeech(args.stt_model, args.tts_model, args.voice) if args.provider != "mock" else None
        self.lock = threading.RLock()
        self.work = threading.Lock()
        self.epoch = 0
        self.reset_epoch = 0
        self.origin_epoch = {"phone": 0, "pc": 0}
        self.active_origin = ""
        self.busy = False
        self.phase = "idle"
        self.error = ""
        self.history = []
        self.events = deque(maxlen=24)
        self.calls = deque()
        self.total_calls = 0
        self.next_turn = 0
        self.queued = 0
        self.scene_mode = args.scene_mode
        self.admin_image = None
        self.image_name = ""
        self.image_version = 0
        self.reply_id = 0
        self.last_audio = None
        self.last_reply = ""
        self.reply_records = deque(maxlen=8)
        self.presence = {"phone": 0, "pc": 0}
        self.token = secrets.token_urlsafe(32)
        self.pair_code = secrets.token_urlsafe(12)
        self.sessions = {}
        self.pair_attempts = deque()
        self.frames = FrameBuffer()
        self.realtime = Realtime(self)
        self.live = Live(self)
        self.audio_controls = AudioControls()
        self.phone_activity = {'phase': 'unknown', 'until': 0}
        self.foreground_serial = 0
        self.photo_serial = 0
        self.last_photo = None
        self.observation = Observation(self)

    def voice_busy(self):
        return bool(self.realtime.active or self.realtime.ending or self.live.active or self.live.ending)

    def voice_session(self):
        if self.live.active or self.live.ending:
            return self.live
        if self.realtime.active or self.realtime.ending:
            return self.realtime
        return self.live if self.args.dialogue_mode == 'live' else self.realtime

    def snapshot(self):
        with self.lock:
            return {"busy": self.busy, "phase": self.phase, "provider": self.args.provider,
                    "source": self.args.source, "camera_available": self.args.source != "demo",
                    "events": list(self.events), "error": self.error, "calls": self.total_calls,
                    "token": self.token, "voice_ready": self.speech is not None,
                    "queued": self.queued, "active_origin": self.active_origin,
                    "scene_mode": self.scene_mode,
                    "frames": self.frames.snapshot(), "realtime": self.voice_session().snapshot(),
                    "dialogue_mode": self.args.dialogue_mode,
                    "photo": ({"id": self.photo_serial, "captured_at": self.last_photo.captured}
                              if self.last_photo else None),
                    "observation": self.observation.snapshot(),
                    "image_name": self.image_name, "image_version": self.image_version,
                    "reply_id": self.reply_id,
                    "last_reply": self.last_reply, "audio_ready": self.last_audio is not None,
                    "replies": [{"id": item["id"], "text": item["text"], "audio_ready": item["audio"] is not None,
                                 "emotion": item.get("emotion", "평온"),
                                 **({"kind": "proactive", "expires_at": item['expires_at'],
                                     "observation_generation": item['observation_generation']}
                                    if item.get('kind') == 'proactive' else {})}
                                for item in self.reply_records],
                    "phone_online": time.monotonic() - self.presence["phone"] < 5,
                    "pc_online": time.monotonic() - self.presence["pc"] < 5,
                    "next_in": max(0, round(self.next_turn - time.monotonic(), 1))}

    def mark_presence(self, role):
        if role in self.presence:
            with self.lock:
                self.presence[role] = time.monotonic()

    def activity(self, phase):
        if phase not in ('idle', 'permission', 'listening', 'transcribing', 'thinking', 'synthesizing', 'speaking', 'hidden'):
            raise ValueError('화면 활동 상태를 확인하세요.')
        with self.lock:
            if phase != 'idle' and phase != self.phone_activity['phase']:
                self.foreground_serial += 1
            self.phone_activity = {'phase': phase, 'until': time.monotonic() + 8}

    def reserve_observation(self, epoch):
        with self.lock:
            if epoch != self.epoch:
                return False
            if self.args.provider == 'mock':
                return True
            now = time.monotonic()
            while self.calls and now - self.calls[0] >= 3600:
                self.calls.popleft()
            if len(self.calls) >= max(0, self.args.max_calls - 20):
                return False
            self.reserve(epoch)
            return True

    def announce_observation(self, text, emotion, generation, epoch, serial, scene, received):
        def eligible():
            return (epoch == self.epoch and serial == self.foreground_serial and not self.queued
                    and not self.voice_busy()
                    and self.phone_activity['phase'] == 'idle' and time.monotonic() < self.phone_activity['until']
                    and time.monotonic() - self.presence['phone'] < 5
                    and self.observation.notice_valid(generation, scene, received))
        if not self.work.acquire(blocking=False):
            return False
        try:
            with self.lock:
                if self.busy or not eligible():
                    return False
                self.busy, self.phase = True, 'synthesizing'
            try:
                voice = None
                if self.speech:
                    self.reserve(epoch)
                    voice = self.speech.synthesize(text)
                with self.lock:
                    if not eligible():
                        return False
                    self.reply_id += 1
                    emotion = normalize_emotion(emotion)
                    self.last_reply, self.last_audio = text, voice
                    self.reply_records.append({'id': self.reply_id, 'text': text, 'audio': voice,
                        'emotion': emotion, 'kind': 'proactive', 'expires_at': time.time() + 20,
                        'observation_generation': generation})
                    self.events.append({'role': 'assistant', 'text': text, 'emotion': emotion, 'origin': 'observation'})
                    self.history.append({'role': 'assistant', 'content': '[주변 관찰 후 먼저 건넨 말] ' + text})
                    self.history = self.history[-12:]
                    return True
            finally:
                with self.lock:
                    self.busy, self.phase = False, 'idle'
        finally:
            self.work.release()

    def set_image(self, data, name=""):
        jpeg = normalize_image(data)
        with self.lock:
            self.admin_image = jpeg
            self.image_name = Path(name).name[:100] or "업로드한 사진"
            self.image_version += 1
            self.scene_mode = "upload"

    def clear_image(self):
        with self.lock:
            self.admin_image = None
            self.image_name = ""
            self.image_version += 1
            if self.scene_mode == "upload":
                self.scene_mode = "off"

    def capture_preview(self):
        if self.args.source == 'demo':
            raise ValueError('카메라가 설정되지 않았습니다.')
        if not self.work.acquire(timeout=20):
            raise ValueError('다른 요청을 처리 중이에요. 잠시 후 카메라를 확인해 주세요.')
        try:
            with self.lock:
                epoch = self.epoch
                self.busy = True
                self.phase = 'capturing'
            jpeg = self.camera.capture()
            self.check(epoch)
            return jpeg
        except Cancelled:
            raise ValueError('카메라 촬영이 취소됐어요.') from None
        finally:
            with self.lock:
                self.busy = False
                self.phase = 'idle'
            self.work.release()

    def capture_requested_photo(self, epoch, valid=lambda: True):
        """One exposure per request. Never fall back to a cached/uploaded image."""
        if self.args.source not in ('pi', 'ssh-pi'):
            raise ValueError('새 사진을 찍을 파이 카메라가 연결되지 않았어요.')
        obs = self.observation
        with obs.capture_lock:
            with self.lock:
                self.check(epoch)
                if not valid():
                    raise Cancelled()
            with obs.lock:
                generation = obs.generation
            jpeg = self.camera.capture()
            if not jpeg:
                raise ValueError('새 사진을 촬영하지 못했어요. 이전 사진은 사용하지 않아요.')
            with self.lock:
                self.check(epoch)
                if not valid():
                    raise Cancelled()
                with obs.lock:
                    if generation != obs.generation or obs.closed.is_set():
                        raise Cancelled()
                    frame = obs.replace_photo(jpeg)
                self.photo_serial += 1
                frame = Frame(self.photo_serial, frame.jpeg, frame.received, frame.timestamp,
                              'pi', '사용자 요청 후 새 촬영', frame.captured)
                self.last_photo = frame
                return frame

    def set_scene_mode(self, mode):
        if mode not in ("off", "camera", "upload", "frames"):
            raise ValueError("장면 모드를 확인하세요.")
        with self.lock:
            if mode == "camera" and self.args.source == "demo":
                raise ValueError("카메라가 설정되지 않았습니다.")
            if mode == "upload" and self.admin_image is None:
                raise ValueError("먼저 PC에서 사진을 업로드하세요.")
            if mode == "frames" and not self.frames.select():
                raise ValueError("먼저 사진 묶음을 올리거나 PC 웹캠을 시작하세요.")
            self.scene_mode = mode

    def cancel(self, clear=False, origin=None):
        with self.lock:
            if origin:
                self.origin_epoch[origin] = self.origin_epoch.get(origin, 0) + 1
            else:
                self.reset_epoch += 1
            if origin is None or origin == self.active_origin:
                self.epoch += 1
                self.phase = "cancelling" if self.busy else "idle"
            if clear:
                self.observation.clear()
                self.history.clear()
                self.events.clear()
                self.error = ""
                self.last_audio = None
                self.last_reply = ""
                self.reply_records.clear()
                self.reply_id += 1

    def check(self, epoch, phase=None):
        with self.lock:
            if epoch != self.epoch:
                raise Cancelled()
            if phase:
                self.phase = phase

    def reserve(self, epoch):
        with self.lock:
            self.check(epoch)
            now = time.monotonic()
            while self.calls and now - self.calls[0] >= 3600:
                self.calls.popleft()
            if len(self.calls) >= self.args.max_calls:
                raise ValueError("시간당 API 요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.")
            self.calls.append(now)
            self.total_calls += 1

    def turn(self, question=None, audio=None, mime=None, use_camera=False, origin="pc"):
        with self.lock:
            if self.voice_busy():
                raise ValueError("실시간 대화를 먼저 종료해주세요.")
            if self.queued >= 3:
                raise ValueError("대기 중인 요청이 많습니다. 잠시 후 다시 시도하세요.")
            queued_epoch = self.reset_epoch
            queued_origin_epoch = self.origin_epoch.get(origin, 0)
            self.queued += 1
        acquired = self.work.acquire(timeout=120)
        with self.lock:
            self.queued -= 1
        if not acquired:
            raise ValueError("대기 시간이 길어 요청을 처리하지 못했어요. 다시 시도하세요.")
        try:
            with self.lock:
                if self.voice_busy():
                    raise ValueError("실시간 대화를 먼저 종료해주세요.")
                if queued_epoch != self.reset_epoch or queued_origin_epoch != self.origin_epoch.get(origin, 0):
                    return {"cancelled": True}
                wait_seconds = max(0, self.next_turn - time.monotonic())
            if wait_seconds:
                time.sleep(wait_seconds)
            with self.lock:
                if self.voice_busy():
                    raise ValueError("실시간 대화를 먼저 종료해주세요.")
                if queued_epoch != self.reset_epoch or queued_origin_epoch != self.origin_epoch.get(origin, 0):
                    return {"cancelled": True}
                self.next_turn = time.monotonic() + self.args.min_turn_seconds
                epoch = self.epoch
                self.busy = True
                self.active_origin = origin
                self.error = ""
                history = [dict(item) for item in self.history]
                scene_mode = self.scene_mode
                uploaded_image = self.admin_image if scene_mode == "upload" else None
                frames = self.frames.select() if scene_mode == "frames" and use_camera else []
            try:
                if audio is not None:
                    if not self.speech:
                        raise ValueError("모의 모드는 음성을 인식하지 않습니다. 텍스트 또는 시연 버튼을 사용하세요.")
                    mime = validate_audio(audio, mime)
                    self.check(epoch, "transcribing")
                    self.reserve(epoch)
                    question = self.speech.transcribe(audio, mime)
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 3000:
                    raise ValueError("질문은 1~3000자로 입력해주세요.")
                question = question.strip()
                jpeg = None
                fresh_photo = requests_photo(question)
                if fresh_photo:
                    self.check(epoch, 'capturing')
                    frames = [self.capture_requested_photo(epoch)]
                    history = []  # Earlier scene descriptions are not evidence for this photo.
                elif use_camera and scene_mode != "off":
                    if scene_mode == "frames":
                        with self.lock:
                            frames = self.frames.select()
                        if not frames:
                            raise ValueError("최근 프레임이 없습니다. 사진을 올리거나 PC 웹캠을 다시 시작하세요.")
                    elif scene_mode == "upload":
                        if uploaded_image is None:
                            raise ValueError("PC에서 업로드한 사진이 없습니다.")
                        jpeg = uploaded_image
                    elif self.args.source == "demo":
                        raise ValueError("카메라가 설정되지 않았습니다. PC에서 장면 모드를 확인하세요.")
                    else:
                        self.check(epoch, "capturing")
                        jpeg = self.camera.capture()
                observation = FRESH_PHOTO_NOTE if fresh_photo else self.observation.context()
                if not jpeg and not frames:
                    frames = self.observation.frames()
                self.check(epoch, "thinking")
                if self.args.provider != "mock":
                    self.reserve(epoch)
                extra = {'observation': observation} if observation else {}
                if frames:
                    extra['frames'] = frames
                reply = self.llm.reply(question, history, jpeg, **extra)
                emotion = normalize_emotion(getattr(reply, 'emotion', fallback_emotion(str(reply))))
                reply = str(reply)
                self.check(epoch)
                voice = None
                warning = ""
                if self.speech:
                    try:
                        self.check(epoch, "synthesizing")
                        self.reserve(epoch)
                        voice = self.speech.synthesize(reply)
                    except Cancelled:
                        raise
                    except (ValueError, RuntimeError) as exc:
                        warning = f"답변은 완료했지만 음성 생성에 실패했어요. {exc}"
                with self.lock:
                    self.check(epoch)
                    remembered = question + ("\n[이 질문에는 당시 사진이 첨부되었음. 사진 자체는 이력에 보관하지 않음.]" if jpeg or frames else "")
                    self.history.extend([{"role": "user", "content": remembered}, {"role": "assistant", "content": reply}])
                    self.history = self.history[-12:]
                    self.events.append({"role": "user", "text": question})
                    self.events.append({"role": "assistant", "text": reply, "emotion": emotion})
                    self.events[-2]["origin"] = origin
                    self.reply_id += 1
                    self.last_audio = voice
                    self.last_reply = reply
                    self.reply_records.append({"id": self.reply_id, "text": reply, "audio": voice, "emotion": emotion})
                    return {"question": question, "reply": reply, "warning": warning, "emotion": emotion,
                            "audio": base64.b64encode(voice).decode() if voice else None,
                            "audio_type": "audio/mpeg", "reply_id": self.reply_id,
                            "mock": self.args.provider == "mock"}
            except Cancelled:
                return {"cancelled": True}
            except (ValueError, RuntimeError) as exc:
                with self.lock:
                    if epoch == self.epoch:
                        self.error = str(exc)
                raise
            finally:
                with self.lock:
                    self.busy = False
                    self.phase = "idle"
                    self.active_origin = ""
        finally:
            self.work.release()

    def close(self):
        self.observation.close()
        self.realtime.close()
        self.live.close()
        self.cancel(clear=True)
        with self.work:
            self.camera.close()


def handler_for(engine):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *args):
            pass

        def send(self, code, body, mime="application/json; charset=utf-8", cookie=None, cache="no-store"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            for key, value in {"Content-Type": mime, "Content-Length": str(len(body)),
                "Cache-Control": cache, "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "Permissions-Policy": "microphone=(self), camera=(self)",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
                self.send_header(key, value)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            hosts.update(engine.args.allowed_host)
            return self.headers.get("Host", "").lower() in hosts

        def same_origin(self):
            origin = self.headers.get("Origin")
            scheme = "https" if engine.args.tls_cert else "http"
            return origin is None or origin == f"{scheme}://{self.headers.get('Host')}"

        def authenticated(self):
            if not engine.args.tls_cert or engine.args.auto_connect:
                return True
            try:
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
                session = cookies.get("bmo_session")
                with engine.lock:
                    return session is not None and engine.sessions.get(session.value, 0) > time.monotonic()
            except Exception:
                return False

        def admin_local(self):
            return self.client_address[0] in ("127.0.0.1", "::1")

        def read_body(self, limit):
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Content-Length가 필요합니다.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= limit:
                raise ValueError("요청 크기가 허용 범위를 벗어났습니다.")
            data = self.rfile.read(length)
            if len(data) != length:
                raise ValueError("요청 전송이 완료되지 않았습니다.")
            return data

        def read_json(self, limit=16384):
            data = json.loads(self.read_body(limit))
            if not isinstance(data, dict):
                raise ValueError("JSON 객체가 필요합니다.")
            return data

        def do_GET(self):
            if not self.valid_host() or (engine.args.auto_connect and not self.same_origin()):
                return self.send(403, {"error": "허용되지 않은 접속 주소입니다."})
            if self.path in ("/api/state", "/api/state?role=phone", "/api/state?role=pc"):
                if not self.authenticated():
                    return self.send(401, {"pair_required": True})
                if self.path.endswith("role=pc") and not self.admin_local():
                    return self.send(403, {"error": "PC 로컬 관리자 화면에서만 사용할 수 있습니다."})
                if self.path.endswith("role=phone"):
                    engine.mark_presence("phone")
                elif self.path.endswith("role=pc"):
                    engine.mark_presence("pc")
                return self.send(200, engine.snapshot())
            if self.path == '/api/audio-levels':
                if not self.authenticated():
                    return self.send(401, {"error": "연결이 필요합니다."})
                return self.send(200, engine.audio_controls.snapshot())
            if self.path.startswith("/api/audio/"):
                if not self.authenticated():
                    return self.send(401, {"error": "연결이 필요합니다."})
                with engine.lock:
                    audio = next((item["audio"] for item in engine.reply_records
                                  if self.path == f"/api/audio/{item['id']}"), None)
                return self.send(200, audio, "audio/mpeg") if audio else self.send(404, {"error": "재생할 음성이 없습니다."})
            if self.path == "/api/admin/image":
                if not self.admin_local() or not self.authenticated():
                    return self.send(403, {"error": "PC 로컬 관리자 화면에서만 사용할 수 있습니다."})
                with engine.lock:
                    image = engine.admin_image
                return self.send(200, image, "image/jpeg") if image else self.send(404, {"error": "업로드한 사진이 없습니다."})
            if self.path == "/":
                name = "phone.html" if not self.admin_local() or "iphone" in self.headers.get("User-Agent", "").lower() else "index.html"
                return self.send(200, self.page(name), "text/html; charset=utf-8")
            if re.fullmatch(r"/faces/Rosto-(?:0[1-9]|[12][0-9]|30)\.jpg", self.path):
                return self.send(200, (WEB / self.path.lstrip("/")).read_bytes(), "image/jpeg",
                                 cache="private, max-age=3600")
            if self.path == "/admin" and not self.admin_local():
                return self.send(403, {"error": "PC 로컬 관리자 화면에서만 사용할 수 있습니다."})
            assets = {"/admin": ("index.html", "text/html; charset=utf-8"),
                      "/phone": ("phone.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/phone.js": ("phone.js", "text/javascript; charset=utf-8"),
                      "/audio-controls.js": ("audio-controls.js", "text/javascript; charset=utf-8"),
                      "/observation.js": ("observation.js", "text/javascript; charset=utf-8"),
                      "/face.js": ("face.js", "text/javascript; charset=utf-8"),
                      "/emotions.js": ("emotions.js", "text/javascript; charset=utf-8"),
                      "/realtime.js": ("realtime.js", "text/javascript; charset=utf-8"),
                      "/live.js": ("live.js", "text/javascript; charset=utf-8"),
                      "/mic-focus.js": ("mic-focus.js", "text/javascript; charset=utf-8"),
                      "/mic-focus-core.js": ("mic-focus-core.js", "text/javascript; charset=utf-8"),
                      "/mic-focus-worklet.js": ("mic-focus-worklet.js", "text/javascript; charset=utf-8"),
                      "/frames.js": ("frames.js", "text/javascript; charset=utf-8"),
                      "/phone.css": ("phone.css", "text/css; charset=utf-8")}
            if self.path not in assets:
                return self.send(404, {"error": "없는 경로입니다."})
            name, mime = assets[self.path]
            self.send(200, self.page(name), mime)

        def page(self, name):
            content = (WEB / name).read_bytes()
            if name == 'phone.html':
                content = content.replace(b'content="realtime" data-dialogue-mode',
                                          ('content="' + engine.args.dialogue_mode + '" data-dialogue-mode').encode())
            return content

        def do_POST(self):
            if not self.valid_host() or not self.same_origin():
                return self.send(403, {"error": "허용되지 않은 접속입니다."})
            try:
                if self.path == "/api/pair":
                    if not engine.args.tls_cert or engine.args.auto_connect:
                        return self.send(400, {"error": "이 서버는 연결 코드 없이 바로 접속합니다."})
                    data = self.read_json()
                    code = data.get("code", "")
                    with engine.lock:
                        now = time.monotonic()
                        while engine.pair_attempts and now - engine.pair_attempts[0] >= 60:
                            engine.pair_attempts.popleft()
                        if len(engine.pair_attempts) >= 5:
                            return self.send(429, {"error": "연결 시도가 많습니다. 1분 후 다시 시도하세요."})
                        engine.pair_attempts.append(now)
                        if not isinstance(code, str) or not secrets.compare_digest(code, engine.pair_code):
                            return self.send(403, {"error": "연결 코드를 확인해주세요."})
                        session = secrets.token_urlsafe(32)
                        engine.sessions = {k: v for k, v in engine.sessions.items() if v > now}
                        if len(engine.sessions) >= 10:
                            engine.sessions.pop(next(iter(engine.sessions)))
                        engine.sessions[session] = now + 43200
                    return self.send(200, {"ok": True}, cookie=f"bmo_session={session}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=43200")
                if not self.authenticated():
                    return self.send(401, {"error": "서버 터미널의 연결 코드로 먼저 연결해주세요.", "pair_required": True})
                if not secrets.compare_digest(self.headers.get("X-BMO-Token", ""), engine.token):
                    return self.send(403, {"error": "화면을 새로고침해주세요."})
                if self.path.startswith("/api/admin/") or self.path == "/api/chat" or self.path == "/api/reset":
                    if not self.admin_local():
                        return self.send(403, {"error": "PC 로컬 관리자 화면에서만 사용할 수 있습니다."})
                if self.path == '/api/audio-levels':
                    data = self.read_json()
                    result = engine.audio_controls.set_volume(data.get('device'), data.get('volume'))
                elif self.path == '/api/observation':
                    data = self.read_json()
                    result = engine.observation.configure(data.get('enabled'), data.get('proactive'))
                elif self.path == '/api/phone/activity':
                    engine.activity(self.read_json().get('phase'))
                    result = {'ok': True}
                elif self.path == '/api/live/start':
                    data = self.read_json(120000)
                    if engine.args.dialogue_mode != 'live':
                        raise ValueError('노을 전용 실행기로 서버를 시작해 주세요.')
                    result = engine.live.start(data.get('sdp', ''), data.get('mock', False))
                elif self.path == '/api/live/heartbeat':
                    result = engine.live.heartbeat(self.read_json(40000))
                elif self.path == '/api/live/emotion':
                    result = engine.live.emotion(self.read_json(6000))
                elif self.path == '/api/live/stop':
                    result = engine.live.stop(self.read_json().get('session_id'))
                elif self.path == "/api/realtime/start":
                    data = self.read_json(120000)
                    result = engine.realtime.start(data.get('sdp', ''), data.get('mock', False))
                elif self.path == "/api/realtime/heartbeat":
                    result = engine.realtime.heartbeat(self.read_json(40000))
                elif self.path == '/api/realtime/notice':
                    data = self.read_json()
                    with engine.lock:
                        a = engine.realtime.require(data.get('session_id'))
                        result = {'notice': engine.observation.take_notice(a)}
                elif self.path == '/api/realtime/emotion':
                    result = engine.realtime.emotion(self.read_json(6000))
                elif self.path == "/api/realtime/stop":
                    result = engine.realtime.stop(self.read_json().get('session_id'))
                elif self.path == "/api/admin/realtime/stop":
                    self.read_json()
                    result = engine.voice_session().stop(force=True)
                elif self.path == "/api/realtime/frames":
                    data = self.read_json()
                    with engine.lock:
                        a = engine.realtime.require(data.get('session_id'))
                        manual = data.get('manual', True)
                        if type(manual) is not bool or type(data.get('force', False)) is not bool:
                            raise ValueError('프레임 전송 옵션을 확인하세요.')
                        frames = engine.frames.select() if manual and engine.scene_mode == 'frames' else []
                        automatic = not frames and engine.observation.enabled
                        if automatic:
                            frames = engine.observation.frames()
                        version = ('auto:' + str(engine.observation.generation) + ':' + str(engine.observation.scene)
                                   if automatic else 'manual:' + str(engine.frames.version))
                        now = time.monotonic()
                        if not frames:
                            result = {'version': version, 'frames': []}
                        elif not automatic and version == a.get('visual_version'):
                            result = {'unchanged': True}
                        elif automatic and (now - a.get('visual_sent_at', float('-inf')) < (1 if data.get('force') else 5)
                                or (version == a.get('visual_version') and not data.get('force')
                                    and now - a.get('visual_sent_at', 0) < 30)):
                            result = {'unchanged': True}
                        elif a.get('visual_count', 0) + len(frames) > 240:
                            result = {'version': version, 'frames': [], 'limited': True}
                        else:
                            a.update(visual_sent_at=now, visual_version=version, visual_count=a.get('visual_count', 0) + len(frames))
                            result = {'version': version + ':' + str(a['visual_count']), 'automatic': automatic,
                                      'observation_generation': engine.observation.generation,
                                      'frames': [f.public(compact=True) for f in frames]}
                elif self.path == "/api/admin/frames":
                    source = self.headers.get('X-BMO-Source', 'prepared')
                    frame_generation = int(self.headers.get('X-BMO-Frame-Generation', '-1'))
                    captured_at = float(self.headers['X-BMO-Captured-At']) if 'X-BMO-Captured-At' in self.headers else None
                    data = self.read_body(20 * 1024 * 1024)
                    with engine.lock:
                        if frame_generation != engine.frames.generation:
                            raise ValueError('이전 프레임 공급 요청입니다. 사진 묶음이나 웹캠을 다시 시작하세요.')
                        changed = engine.frames.add(data, source, unquote(self.headers.get('X-BMO-Label', '')), captured_at)
                        if self.headers.get('X-BMO-Activate') == '1':
                            engine.scene_mode = 'frames'
                    result = {'ok': True, 'changed': changed, 'generation': engine.frames.generation}
                elif self.path == "/api/admin/frames/clear":
                    self.read_json()
                    with engine.lock:
                        engine.frames.clear()
                        if engine.scene_mode == 'frames':
                            engine.scene_mode = 'off'
                    result = {'ok': True, 'generation': engine.frames.generation}
                elif self.path == "/api/voice":
                    audio = self.read_body(MAX_AUDIO)
                    result = engine.turn(audio=audio, mime=self.headers.get("Content-Type", ""),
                                         use_camera=self.headers.get("X-BMO-Camera") == "1", origin="phone")
                    result.pop("audio", None)
                elif self.path == "/api/chat":
                    data = self.read_json()
                    if type(data.get("camera", False)) is not bool:
                        raise ValueError("camera 값은 boolean이어야 합니다.")
                    result = engine.turn(question=data.get("question"), use_camera=data.get("camera", False), origin="pc")
                    result.pop("audio", None)
                elif self.path == "/api/admin/capture":
                    self.read_json()
                    return self.send(200, engine.capture_preview(), 'image/jpeg')
                elif self.path == "/api/admin/image":
                    if self.headers.get("Content-Type", "").split(";", 1)[0].lower() not in ("image/jpeg", "image/png"):
                        raise ValueError("JPG 또는 PNG 이미지만 업로드하세요.")
                    engine.set_image(self.read_body(20 * 1024 * 1024))
                    result = {"ok": True}
                elif self.path == "/api/admin/image/clear":
                    self.read_json()
                    engine.clear_image()
                    result = {"ok": True}
                elif self.path == "/api/admin/scene":
                    data = self.read_json()
                    engine.set_scene_mode(data.get("mode"))
                    result = {"ok": True}
                elif self.path in ("/api/cancel", "/api/reset"):
                    self.read_json()
                    if self.path == '/api/reset' and engine.voice_busy():
                        raise ValueError('실시간 대화를 종료한 뒤 기록을 지워주세요.')
                    engine.cancel(clear=self.path == "/api/reset", origin="phone" if self.path == "/api/cancel" else None)
                    result = {"ok": True}
                else:
                    return self.send(404, {"error": "없는 경로입니다."})
                return self.send(200, result)
            except (ValueError, TypeError, UnicodeError) as exc:
                return self.send(400, {"error": str(exc)[:250]})
            except RuntimeError as exc:
                return self.send(502, {"error": str(exc)[:250]})
            except Exception:
                return self.send(500, {"error": "처리 중 오류가 발생했습니다. 카메라 설정과 서버 상태를 확인해주세요."})
    return Handler


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="BMO 눌러 말하기 비서")
    p.add_argument("--provider", choices=["mock", "claude", "openai"], default="mock")
    p.add_argument("--model", default="")
    p.add_argument("--source", choices=["demo", "image", "pi", "ssh-pi"], default="demo", help="demo는 카메라 없음")
    p.add_argument("--image")
    p.add_argument("--camera-index", type=int, default=0)
    p.add_argument('--scene-mode', choices=['off', 'camera'], default='off')
    p.add_argument('--auto-observe', action=argparse.BooleanOptionalAction, default=None,
                   help='주변 자동 관찰·변화 요약·먼저 말하기; Pi 카메라의 기본값은 켜짐')
    p.add_argument('--pi-host', default='192.168.1.50')
    p.add_argument('--pi-user', default='pi-user')
    p.add_argument('--pi-key', default=str(Path.home() / '.ssh' / 'bmo_pi_ed25519'))
    p.add_argument('--pi-project', default='/home/pi-user/bmo-project')
    p.add_argument('--pi-port', type=int, default=8765)
    p.add_argument("--stt-model", default="gpt-4o-mini-transcribe")
    p.add_argument("--tts-model", default="gpt-4o-mini-tts")
    p.add_argument("--voice", default="coral")
    p.add_argument("--realtime-model", default="gpt-realtime-2.1")
    p.add_argument('--dialogue-mode', choices=['realtime', 'live'], default='realtime')
    p.add_argument("--min-turn-seconds", type=float, default=2)
    p.add_argument("--max-calls", type=int, default=180)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--tls-cert")
    p.add_argument("--tls-key")
    p.add_argument("--auto-connect", action="store_true", help="개인 네트워크에서 연결 코드 없이 바로 접속")
    p.add_argument("--allowed-host", action="append", default=[], help="아이폰에서 접속할 IP:포트 또는 도메인:포트")
    a = p.parse_args(argv)
    a.model = a.model or os.environ.get("ANTHROPIC_MODEL" if a.provider == "claude" else "OPENAI_MODEL", "")
    if a.auto_observe is None:
        a.auto_observe = a.source == 'pi' and a.provider in ('openai', 'mock')
    a.allowed_host = [host.lower() for host in a.allowed_host]
    if bool(a.tls_cert) != bool(a.tls_key):
        p.error("--tls-cert와 --tls-key를 함께 지정하세요.")
    if a.host not in ("127.0.0.1", "localhost") and (not a.tls_cert or not a.allowed_host):
        p.error("외부 기기 접속에는 TLS 인증서와 --allowed-host가 필요합니다.")
    if a.source == "image" and (not a.image or not Path(a.image).is_file()):
        p.error("--image에 존재하는 사진 경로를 지정하세요.")
    if a.scene_mode == 'camera' and a.source == 'demo':
        p.error('카메라 장면 모드에는 이미지 또는 카메라 소스가 필요합니다.')
    if a.auto_observe and (a.source not in ('pi', 'image') or a.provider not in ('openai', 'mock')):
        p.error('--auto-observe에는 pi/image 소스와 openai/mock 공급자가 필요합니다.')
    if not 0 <= a.min_turn_seconds <= 60 or a.max_calls < 1 or a.camera_index < 0 or not 1 <= a.port <= 65535:
        p.error("요청 간격, 호출 한도, 포트 또는 카메라 번호를 확인하세요.")
    return a


class BmoServer(ThreadingHTTPServer):
    def server_bind(self):
        # Windows SO_REUSEADDR can route requests to an older server on the same port.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(engine):
    args = engine.args
    server = BmoServer((args.host, args.port), handler_for(engine))
    try:
        if args.tls_cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(args.tls_cert, args.tls_key)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
        return server
    except Exception:
        server.server_close()
        raise


def main():
    args = parse_args()
    try:
        engine = Engine(args)
        server = create_server(engine)
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
    print(f"BMO: {'https' if args.tls_cert else 'http'}://{args.host}:{args.port} | {args.provider}", flush=True)
    if args.tls_cert and not args.auto_connect:
        print(f"Device pairing code: {engine.pair_code}", flush=True)
    try:
        engine.observation.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.close()
        server.server_close()


if __name__ == "__main__":
    main()
