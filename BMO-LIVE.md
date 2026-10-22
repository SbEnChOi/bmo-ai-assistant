**2026-10-22 업데이트:** 본 문서의 별도 Live 구현을 최종 통합하여 파이에 적용했다. 실제 Live/Noeul 합성 입력의 음성 응답과 카메라 분석 위임도 확인했다. 현재 실행·제한·복원은 BMO-FINAL.md와 VALIDATION.md를 우선한다. 아래 10월21일 미배포 설명은 과거 상태다.

# GPT-Live-1 + 노을 별도 버전 — 2026-10-21

PC 준비 소스와 보관 ZIP: `versions/BMO-live-noeul-2026-10-21.zip`. **파이 미배포, 실제 노을 음성·계정 접근·마이크 대화 미검증.** 기존 Realtime 실행기와 이전 ZIP을 보존했다. 네트워크 구조는 `BMO-NETWORK.md`를 따른다.

## 무엇이 달라지는가

- 새 실행기에서 `gpt-live-1` / `noeul`을 사용한다. 기존 `start-assistant.ps1`, `start-pi.sh` 기본은 Realtime이다.
- 중앙의 **노을과 대화 시작** 버튼으로 연결하고 같은 자리에서 종료한다. 눌러서 말하기는 유지하며 두 방식의 동시 실행을 막는다.
- 설정의 마이크 끄기·말 멈추기·모의 연결, 기존 스피커/마이크 음량, 24장 표정 후보(15번 제외), 생각 중 점을 유지한다.
- Live는 양방향 음성이 겹칠 수 있어 자막을 두 화자로 나눠 표시한다. 자막 조각 자체를 재생 시작으로 간주하지 않고 출력 오디오 레벨로 말하기 표정을 정한다. 자막은 근사 시간에 기반한 발화 묶음이며 정확한 문장 종료 이벤트는 아니다.
- **눌러서 말하기와 대기 중 먼저 말하기는 기존 TTS/coral**이다. 노을은 새 Live 실시간 세션에 적용된다.

## PC에서 실행

Python 3.10 이상과 기존 서버 API 키 설정이 필요하다. 키를 새 ZIP 템플릿으로 덮어쓰지 않는다. 현재 작업 PC에는 `.venv-live`와 websocket-client 1.9.2를 준비했다. 다른 PC의 신규 설치 예:

```powershell
python -m venv .venv-live
./.venv-live/Scripts/python.exe -m pip install -r requirements-live.txt
./start-live-noeul.ps1
```

기본 주소는 `http://127.0.0.1:8780/phone`, 관리자는 `/admin`이다. 해당 포트를 사용 중이면 실행기에 표시되는 주소를 따른다. 모델·카메라·LAN 인자는 기존 실행기와 동일하게 지정한다. 다른 Python은 `-PythonPath`로 지정한다. 시작만으로 유료 Live 세션을 만들지 않으며, 화면의 시작 버튼을 눌렀을 때 마이크와 연결을 연다. 모의 연결은 마이크·외부 API·과금이 없다.

기존 Realtime 비교: `./start-assistant.ps1`로 별도 서버를 실행한다. 두 서버를 동시에 열었을 때 대화 기록은 별개이며 같은 마이크를 동시에 시작하지 않는다.

## 파이에 적용할 때

이번에는 파이에 복사하거나 부팅 서비스를 변경하지 않았다. 실제 연결 복구 후 기존 설정·키·가상 환경을 보존하여 설치하고, 기존 서비스를 정지한 상태에서 시험한다.

```bash
cd /home/pi-user/bmo-project
# 카메라를 쓰는 기존 가상 환경에 Live 추가 의존성 설치
.venv-camera/bin/python -m pip install -r requirements-live.txt
systemctl --user stop bmo.service
bash start-pi-live-noeul.sh --auto-camera --observe --pc-port 8775
```

카메라가 없으면 `.venv/bin/python` 환경에도 Live 의존성이 필요하다. 파이 브라우저에서 `http://127.0.0.1:8765/phone`을 연다. 기존 kiosk 실행기는 기존 서비스를 다시 시작할 수 있으므로 수동 시험 중에는 파이 브라우저 주소만 연다. 기존 Realtime으로 복귀하려면 시험 프로세스를 Ctrl+C로 끝내고 `systemctl --user start bmo.service`를 실행한다. Live 부팅 자동 실행은 실물 검증 후 서비스 ExecStart를 새 실행기로 변경한다.

## 카메라와 백엔드

Live는 이미지를 직접 받지 않는다. 서버의 신뢰된 sideband가 `session.delegation.created`를 받고 기존 Conversation의 사진 분석을 호출한다. 준비한 사진/웹캠은 설정에서 허용한 경우, 자동 관찰은 사용자가 켠 경우, 카메라 장면 모드는 해당 소스를 선택한 경우 사용한다. 최신 관찰 프레임은 최대 3장이다. 결과는 480 UTF-8 byte 이내의 텍스트로 Live에 전달한다. 긴 답변은 이 단계에서 축약될 수 있다.

관찰 기록은 최신 순으로 조용히 전달하고, 과거 업로드는 촬영 시각 미확인 자료로 표시한다. 서버가 자막·위임을 처리하므로 브라우저가 중복으로 분석을 요청하지 않는다. 한 세션 최대 24번의 분석, 기존 전체 API 예산, 최신 요청 우선·설정 변경·새 질문·종료 후 늦은 결과 폐기를 적용한다. 백엔드의 실행 중 HTTP 호출 자체를 취소하는 것은 아니며, 무효화된 결과를 음성으로 보내지 않는다.

## 비용과 종료

공식 확인 기준 Live는 세션 시간 분당 **$0.05**이며 침묵·마이크 음소거·분석 대기도 포함된다. 초기 WebRTC 연결에는 최소 15초 초기화 과금이 있고 이후 세션 시간에 반영된다. 사진 분석·감정 분류·기존 TTS 등 백엔드 비용은 별도다. UI 금액은 수신한 누적 seconds를 사용한 추정치이며 청구서가 아니다.

최대 5분, heartbeat 30초 유실, 화면 이탈, 사용자가 종료할 때 세션을 닫는다. 마이크·로컬 재생은 즉시 멈추고 제어 연결은 종료 확인까지 유지한다. 확인 실패는 경고와 재시도를 유지하고 새 세션을 차단한다. 서버 강제 종료·정전·인터넷 완전 단절에서는 최종 사용량을 확인하지 못할 수 있다. 모의 시험으로 실제 네트워크에서의 음성 품질과 과금을 입증하지 않는다.

## 확인한 범위

오프라인 HTTP·가짜 sideband·WebRTC 대역 테스트와 800×480 브라우저 모의 화면을 검사했다. 실제 API 권한/노을 음색/양방향 끼어들기/파이 성능·Wi-Fi 연결은 사용자가 기기를 연결한 뒤 확인해야 한다. 실패하면 API 키 값을 공개하지 말고 화면 오류 코드와 서버 로그로 인증·사용량·네트워크·오디오 장치를 구분한다.

공식 근거: [Live](https://developers.openai.com/api/docs/guides/live), [WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc?voice-api=live), [위임](https://developers.openai.com/api/docs/guides/live-delegation), [노을·자막·종료](https://developers.openai.com/api/docs/guides/live-conversations), [비용](https://developers.openai.com/api/docs/guides/voice-latency-cost?api=live).
