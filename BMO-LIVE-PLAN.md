# BMO Live Noeul Implementation Plan

> **For agentic workers:** Execute inline with executing-plans, followed by an independent code review. Preserve the existing ZIPs; this shared project has an unborn Git branch and unrelated untracked projects, so do not stage or commit the workspace.

**Goal:** 기존 Realtime을 보존하면서 GPT-Live-1 + 노을 대화 실행기를 제공한다.

**Architecture:** Live는 기존 세션 관리자에서 임대·소유권·감정 분류를 재사용한다. 서버 sideband만 자막 이력과 위임을 처리하고, 브라우저 WebRTC는 오디오·표시·사용자 제어를 담당한다.

**Tech Stack:** Python stdlib HTTP + websocket-client (Live 전용 선택 의존성), 기존 HTML/CSS/JS, unittest + Node test + Playwright CLI.

## Global constraints
- `gpt-live-1`, `noeul`, 최대 300초, heartbeat 30초, 위임 최대 24회, 키는 서버 전용.
- 원본 Realtime·TTS 기본값·표정 후보 1~25 중 15 제외·음량·카메라/터치 부팅 설정 보존.
- 실제 기기와 유료 세션에는 접속하지 않는다. 종료는 서버가 확인하며 미확인 시 경고·재시도한다.

## Tasks

- [x] 1. `tests/test_live.py`에 모의 JSON handshake, 목소리/키 분리, 두 음성 모드 배타성, 지연 취소, 종료 실패 재시도 검사를 추가한다. `python -m unittest tests.test_live -v`로 새 인터페이스 부재 실패를 확인한다.
- [x] 2. `bmo/live.py`의 `Live(engine)`와 `bmo/live_transport.py`의 `LiveSideband(session_id, key, on_event, on_error)`를 구현한다. `start(sdp, mock)`는 기존 local session_id와 SDP만 브라우저로 반환하고, `stop`은 확인된 종료까지 비용 연결을 관리한다. `bmo/realtime.py`는 공유 소유권/remote-create hook만 추출한다.
- [x] 3. Live의 서버 이벤트 처리에서 원본 자막 조각/시각을 보존하고 `session.delegation.created`에서 `Conversation.reply(question, history, jpeg, frames, observation)`를 호출한다. 최신 위임/설정 세대 확인 후 결과를 Live로 보내고, 실패는 사실에 맞는 짧은 실패 설명으로 전달한다. stale·중복·동시·예산·사진 출처를 테스트한다.
- [x] 4. `bmo/app.py`에 dialogue mode, 통합 음성 상태, Live의 인증·토큰 보호 API를 연결하고 화면 meta로 JS를 선택한다. `/api/live/start`, `/heartbeat`, `/emotion`, `/stop`과 관리자 강제 종료를 검사한다. `/api/realtime/*`는 기존 기능을 유지한다.
- [x] 5. `bmo/web/live.js`에서 ICE 완료→JSON handshake→session.started 순서를 구현한다. 자막은 정확한 delta를 두 화자별로 합치고, 재생 레벨·분석 상태·기존 감정 모듈을 연결한다. 모의 연결, 늦은 마이크/handshake, 실패/숨김 종료, 최종 사용량, 음소거를 `tests/test_live_ui.cjs`로 검사한다.
- [x] 6. `start-live-noeul.ps1`, `start-pi-live-noeul.sh`, `requirements-live.txt`를 추가한다. 기존 실행기는 Realtime, 새 실행기는 Live로 시작한다. LCD 중앙 버튼·설정·비용 안내를 800×480 브라우저에서 확인한다.
- [x] 7. 전체 Python/JS 회귀 테스트와 시작 스크립트 문법을 확인한다. requesting-code-review 스킬에 따라 독립 검토를 요청하고 중요한 지적을 수정한 후 관련 검사를 다시 수행한다.
- [x] 8. `BMO-LIVE.md`, 버전/인수인계/검증 문서를 갱신하고 키 없는 `versions/BMO-live-noeul-2026-10-21.zip`을 만든다. 원본 ZIP 해시 보존, 새 ZIP 무결성·빈 키 템플릿·필수 파일을 확인한다. 파이 미배포·실제 음성 미검증을 명시한다.

## Verification commands
```powershell
python -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_live_ui.cjs tests/test_realtime_ui.cjs tests/test_voice_ui.cjs tests/test_face_ui.cjs tests/test_audio_controls_ui.cjs tests/test_observation_ui.cjs
```

## Execution record
- 2026-10-21: Python 123 / JavaScript 53 passed; PowerShell and Bash syntax passed. Independent review findings reproduced and repaired. LCD-size mock UI inspected. New ZIP verification recorded in versions/manifest.json.
- Raspberry Pi and actual paid Noeul conversation remain intentionally untested; network diagnosis awaits current IP and error from the user.
