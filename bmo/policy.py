"""Deterministic temporal policy; no identity tracking or medical diagnosis."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Observation:
    summary: str
    person: bool
    posture: str
    activity: str
    confidence: float

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict) or set(data) != {"summary", "person", "posture", "activity", "confidence"}:
            raise ValueError("분석 결과 필드가 올바르지 않습니다.")
        if type(data["person"]) is not bool:
            raise ValueError("person은 boolean이어야 합니다.")
        if not isinstance(data["summary"], str) or not 1 <= len(data["summary"]) <= 600:
            raise ValueError("장면 설명이 올바르지 않습니다.")
        if data["posture"] not in ("upright", "slouched", "unknown"):
            raise ValueError("자세 값이 올바르지 않습니다.")
        if data["activity"] not in ("sitting", "standing", "moving", "unknown"):
            raise ValueError("활동 값이 올바르지 않습니다.")
        c = data["confidence"]
        if type(c) not in (int, float) or not math.isfinite(c) or not 0 <= c <= 1:
            raise ValueError("확신도 값이 올바르지 않습니다.")
        return cls(**data)

    def dict(self):
        return asdict(self)


class Policy:
    def __init__(self, posture_seconds=60, sitting_seconds=1800, cooldown=300, max_gap=180):
        self.posture_seconds = posture_seconds
        self.sitting_seconds = sitting_seconds
        self.cooldown = cooldown
        self.max_gap = max_gap
        self.last_alert = -float("inf")
        self.reset()

    def reset(self):
        self.slouch_since = self.sitting_since = self.last_seen = None
        self.slouch_count = 0

    def evaluate(self, obs, now):
        if self.last_seen is not None and now - self.last_seen > self.max_gap:
            self.reset()
        if not obs.person or obs.confidence < 0.75:
            self.reset()
            return None
        self.last_seen = now
        if obs.posture == "slouched":
            if self.slouch_since is None:
                self.slouch_since = now
            self.slouch_count += 1
        else:
            self.slouch_since = None
            self.slouch_count = 0
        if obs.activity == "sitting":
            if self.sitting_since is None:
                self.sitting_since = now
        else:
            self.sitting_since = None
        if now - self.last_alert < self.cooldown:
            return None
        event = None
        if self.slouch_count >= 3 and now - self.slouch_since >= self.posture_seconds:
            event = {"kind": "posture", "message": "몸이 앞으로 기울어진 모습이 몇 번 보였어요. 편하게 자세를 바꿔볼까요?"}
        elif self.sitting_since is not None and now - self.sitting_since >= self.sitting_seconds:
            event = {"kind": "break", "message": "최근 관찰에서 계속 앉아 있는 모습이 보였어요. 잠깐 쉬어갈까요?"}
        if event:
            self.last_alert = now
        return event
