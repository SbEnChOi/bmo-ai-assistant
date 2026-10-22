# GPT-Live-1 / 노을 설계 — 2026-10-21

사용자는 기존 Realtime을 보존하고 GPT-Live-1 + Noeul을 별도 버전으로 만드는 앞선 제안을 승인했다. 이 문서는 그 범위를 구체화한다. 파이는 현재 연결하지 않는다.

- 기존 실행기의 기본은 Realtime / coral을 유지한다. 새 PC·Pi 실행기는 `--dialogue-mode live`로 시작한다. 음성 모델은 `gpt-live-1`, 목소리는 `noeul`로 고정한다. 눌러서 말하기와 대기 중 먼저 말하기는 기존 TTS/coral을 유지하며 UI에 구분해 안내한다.
- 브라우저 오디오는 WebRTC, 서버는 JSON `POST /v1/live/sessions`를 사용한다. 키는 서버에만 있다. 신뢰된 서버 sideband가 자막·클라이언트 위임·맥락 전달과 종료를 소유한다. 브라우저는 중복으로 분석을 실행하지 않는다.
- `session.delegation.created`의 ID를 보존하고 현재 자막과 최근 이력으로 기존 Conversation 백엔드를 호출한다. 사진·프레임은 백엔드로만 전달하고 결과는 480 UTF-8 byte 이하의 `session.commentary.append`로 Live에 전달한다. 사진이 없거나 오래되면 현재 시각을 주장하지 않는다.
- 관찰 요약은 `session.thinking.append`로 조용히 갱신한다. 일시정지·기록 지우기·새 질문/정정·종료 후 도착한 사진 분석은 폐기한다. 동시 위임은 최신 요청만 유효하고, 세션당 최대 24회·전체 API 예산을 적용한다.
- 기존 얼굴·생각 중 점·음량을 유지한다. Live의 양방향 자막을 독립 표시하고 실제 출력 레벨로 말하는 표정을 표시한다. 감정 분류는 기존 한 발화 한 포즈 정책을 유지한다.
- 실시간 연결은 양쪽 모드 통틀어 하나만 허용한다. 연결된 동안 눌러서 말하기/대기 안내는 차단한다. 최대 5분, heartbeat 30초 유실·화면 이탈·사용자 종료 시 닫는다. 종료 확인 실패는 재시도와 경고를 유지하고 새 유료 세션 생성을 막는다.
- 분당 $0.05는 세션 시간 기준 추정치이며 분석 비용은 별도다. 초기화 과금과 최종 사용량 미확인을 구분한다. 모의 연결은 마이크·외부 API·과금이 전혀 없다.
- 검증: 합성 사진, 가짜 Live 서버/sideband, 브라우저 WebRTC 대역으로 연결·자막·위임·감정·경합·종료·기존 회귀를 검사한다. 실제 노을 음색·계정 접근·파이 성능은 실물 연결 후 확인한다.

공식 규격: https://developers.openai.com/api/docs/guides/voice-webrtc, https://developers.openai.com/api/docs/guides/live-delegation, https://developers.openai.com/api/docs/guides/live-conversations, https://developers.openai.com/api/docs/guides/voice-server-controls?api=live
