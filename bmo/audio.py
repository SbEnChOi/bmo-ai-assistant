"""Bounded in-memory audio exchange. API credentials never reach the browser."""
import json
import secrets
import urllib.error
import urllib.request
from .config import api_key

MAX_AUDIO = 8 * 1024 * 1024
AUDIO_TYPES = {"audio/webm": "webm", "video/webm": "webm", "audio/mp4": "mp4",
               "video/mp4": "mp4", "audio/ogg": "ogg", "audio/wav": "wav", "audio/mpeg": "mp3"}


def validate_api_key(key, name="API"):
    """HTTP authorization headers require a printable, single-line secret."""
    if not isinstance(key, str) or not key or len(key) > 4096 or any(not 33 <= ord(char) <= 126 for char in key):
        raise ValueError(f"{name} API 키 형식이 올바르지 않습니다. 키 값만 다시 입력하세요(한글, 공백, 줄바꿈 제외). 키는 화면에 표시하지 않습니다.")
    return key


def validate_audio(data, mime):
    mime = mime.split(";", 1)[0].strip().lower()
    if mime not in AUDIO_TYPES:
        raise ValueError("지원되지 않는 녹음 형식입니다. Safari 또는 Chrome을 사용하세요.")
    if not 100 <= len(data) <= MAX_AUDIO:
        raise ValueError("녹음이 비어 있거나 8 MB를 초과했습니다.")
    return mime


def rate_limit_message(exc):
    """Use only a known error code; never show the remote error body."""
    code = None
    try:
        error = json.loads(exc.read(4096)).get("error", {})
        if isinstance(error, dict):
            code = error.get("code") or error.get("type")
    except (ValueError, TypeError, AttributeError, OSError):
        pass
    if not isinstance(code, str):
        code = None
    messages = {
        "credit_balance_exhausted": "API 선불 크레딧이 소진되었습니다. OpenAI Platform의 Billing을 확인하세요.",
        "organization_spend_limit_exceeded": "조직의 API 지출 한도에 도달했습니다. OpenAI Platform의 Limits를 확인하세요.",
        "project_spend_limit_exceeded": "프로젝트의 API 지출 한도에 도달했습니다. OpenAI Platform의 프로젝트 설정을 확인하세요.",
        "organization_usage_limit_exceeded": "조직의 API 사용 한도에 도달했습니다. OpenAI Platform의 Limits를 확인하세요.",
        "rate_limit_exceeded": "요청 속도 제한에 걸렸습니다. 잠시 기다렸다가 다시 시도하세요.",
        "slow_down": "요청이 너무 빠르게 증가했습니다. 잠시 기다렸다가 다시 시도하세요.",
        "rate_limit_error": "요청 속도 제한에 걸렸습니다. 잠시 기다렸다가 다시 시도하세요.",
        "insufficient_quota": "API 크레딧 또는 사용·지출 한도를 확인하세요. OpenAI Platform의 Billing과 Limits를 확인하세요.",
    }
    return messages.get(code, "요청 속도 또는 API 크레딧·사용 한도를 확인하세요. OpenAI Platform의 Billing과 Limits를 확인하세요.")


def api_request(url, key, body, content_type="application/json", headers=None, binary=False, response_headers=False, timeout=45):
    validate_api_key(key)
    request_headers = {"Authorization": f"Bearer {key}", "Content-Type": content_type}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(12 * 1024 * 1024 + 1)
            received_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            message = rate_limit_message(exc)
        else:
            message = {400: "요청 형식 또는 모델 설정을 확인하세요.", 401: "API 키를 확인하세요.",
                       403: "API 접근 권한을 확인하세요.", 404: "모델 ID를 확인하세요."}.get(exc.code, "서비스 오류입니다. 잠시 후 다시 시도하세요.")
        raise RuntimeError(f"API HTTP {exc.code}: {message}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("API 연결 실패 또는 시간 초과입니다.") from None
    if len(data) > 12 * 1024 * 1024:
        raise RuntimeError("API 응답 크기 제한을 초과했습니다.")
    result = data if binary else json.loads(data)
    return (result, received_headers) if response_headers else result


class OpenAISpeech:
    def __init__(self, stt_model="gpt-4o-mini-transcribe", tts_model="gpt-4o-mini-tts", voice="coral"):
        self.key = api_key("OPENAI_API_KEY")
        if not self.key:
            raise ValueError("OPENAI_API_KEY를 bmo/private_config.py 또는 환경 변수에 설정하세요.")
        validate_api_key(self.key, "OpenAI")
        self.stt_model, self.tts_model, self.voice = stt_model, tts_model, voice

    def transcribe(self, audio, mime):
        mime = validate_audio(audio, mime)
        boundary = "bmo_" + secrets.token_hex(16)
        parts = []
        for name, value in (("model", self.stt_model), ("language", "ko"), ("response_format", "json")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.{AUDIO_TYPES[mime]}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),
                      audio, f'\r\n--{boundary}--\r\n'.encode()])
        result = api_request("https://api.openai.com/v1/audio/transcriptions", self.key, b"".join(parts), f"multipart/form-data; boundary={boundary}")
        text = result.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("말소리를 인식하지 못했어요. 다시 말씀해주세요.")
        if len(text) > 3000:
            raise ValueError("인식한 문장이 너무 깁니다. 짧게 나누어 말씀해주세요.")
        return text.strip()

    def synthesize(self, text):
        body = {"model": self.tts_model, "voice": self.voice, "input": text, "response_format": "mp3"}
        audio = api_request("https://api.openai.com/v1/audio/speech", self.key, json.dumps(body).encode(), binary=True)
        if not audio:
            raise RuntimeError("합성 음성이 비어 있습니다.")
        return audio
