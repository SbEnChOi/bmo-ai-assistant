**2026-10-22 최종 적용:** bmo.service 기본은 start-pi-live-noeul.sh --auto-camera --observe --pc-port 8775. 사용자 서비스 enabled와 실제 LCD 새 노을 화면을 확인했다. 재부팅 자체는 이번에 수행하지 않았다. 소스/서비스 백업 /home/pi-user/bmo-backups/final-20261022-093924, 사용·복원 BMO-FINAL.md 우선.

# 2026-10-21 현재 구조와 별도 Live 버전

파이에서 웹 서버와 LCD Chromium을 함께 실행하며 PC의 8775는 파이 관리용 SSH 터널이다. PC 없이 동작하려면 파이 자체 인터넷 연결이 필요하다. [BMO-NETWORK.md](BMO-NETWORK.md)를 우선한다. 새 GPT-Live-1 + 노을과 자동 관찰 PC 소스는 아직 파이 미배포이며 [BMO-LIVE.md](BMO-LIVE.md)의 수동 시험 뒤 부팅 서비스 전환을 결정한다. 기존 유선·Wi-Fi 주소는 2026-10-21에 응답하지 않아 사용자가 추후 현재 IP를 알려주기로 했다. API 실패 원인은 아직 미확정이다.

# BMO 라즈베리 파이 설치 기록 — 2026-10-07

최신 추가: 설정 패널의 마이크·스피커 음량 조절 기능을 파이에 적용했다. 기본 PipeWire 장치를 `wpctl`로 제어하며 관리자 권한이나 녹음이 필요 없다. 유선 192.168.1.50 경로와 PC 8775 터널을 다시 열었다. 파이 현재 Wi-Fi IP는 192.168.1.120이며 이전 11.135.148.117은 응답하지 않는다. 아래 네트워크 절은 과거 기록이다. 설정 적용 전 소스 백업: `/home/pi-user/.local/share/bmo/backups/audio-settings-20261015T115456379093Z`.

**2026-10-15 현재 UI:** 사용자 요청으로 기존 실시간 기능을 복원했다. `/phone` 하단 중앙의 눌러서 말하기 옆에 50px 높이의 실시간 시작·종료 버튼이 있으며, 생각 중 점·표정을 유지한다. LCD·터치·카메라·무선 설정은 그대로다. 복원 전 파이 소스 백업: `/home/pi-user/.local/share/bmo/backups/realtime-restore-ui-20261015T113534360872Z`. 버전 파일은 `BMO-VERSIONS.md`를 따른다. USB 오디오 재연결 후 Jieli 스피커 기본 출력 100%·AB13X 기본 마이크 39%·음소거 해제를 확인했다.

## 2026-10-15 LCD 터치·BMO 화면 완료 · 최신 상태

MPI5008은 800×480/60Hz로 출력된다. 사용자가 아래 터치 설정을 적용·재부팅한 뒤 **ADS7846 Touchscreen, /dev/input/event5, spi0.1**이 커널과 X11에 인식됐고, 사용자가 실제 터치 동작을 확인했다. 아래 명령은 적용 기록이며 다시 실행할 필요가 없다.

```bash
cd /home/pi-user/bmo-project
sudo python3 tools/configure_pi_display.py --apply && sudo reboot
```

기존 카메라 `imx219,cam0`과 HDMI 설정을 보존했으며 IMX219 센서 목록도 정상이다. 자세한 근거·검증은 `BMO-HARDWARE.md`를 따른다. 최신 BMO 소스를 기존 API 설정 변경 없이 백업·반영했고 파이 Python 테스트 **66개가 통과**했다. 소스 백업은 `/home/pi-user/.local/share/bmo/backups/20261015T010442873586Z`다.

파이의 `bmo.service`를 **시작하고 자동 실행도 활성화**했다. `~/.config/autostart/bmo-kiosk.desktop`과 프로젝트의 `start-pi-kiosk.sh`가 로그인 시 Chromium 전체 화면을 연다. LCD의 실제 `/phone` 화면·한국어 표시를 캡처로 확인했고, 첫 실행 키링·번역 안내창도 정리했다. 새 자동 실행 설정 후 재부팅 검증은 남아 있다. 종료는 키보드 Alt+F4, 다시 시작은 파이 데스크톱 터미널에서 `bash /home/pi-user/bmo-project/start-pi-kiosk.sh`다. USB 마이크·스피커가 아직 인식되지 않아 실제 음성 입출력 시험은 하지 않았다.

이번 재부팅 이후 무선 프로필은 `dlink`, Wi-Fi 주소는 **11.135.148.117/19**, 게이트웨이는 `11.135.128.1`이다. 기존 `192.168.1.50`은 현재 주소가 아니다. 새 무선 SSH에서 기존 파이의 호스트 키를 검증했고 외부 경로 wlan0, OpenAI 주소 DNS와 TLS1.3 접속을 확인했다. 랜선 분리 시험은 아직 하지 않았다. PC 관리자는 무선 SSH 터널을 통해 **http://127.0.0.1:8775/admin**으로 접속한다. 현재 터널은 열려 있으며 PC 재시작 등으로 종료되면 다음으로 다시 연다.

```powershell
./connect-pi.ps1 -PiHost 11.135.148.117
```

`connect-pi.ps1`은 유선과 같은 파이 호스트 키를 확인하도록 `HostKeyAlias=192.168.1.50`을 기본 사용한다. DHCP 주소는 바뀔 수 있어 재접속 전 확인한다. 로컬 LCD와 파이 서버는 PC 터널 없이 동작한다. 아래 네트워크 및 서비스 기록은 과거 상태다.

## 2026-10-15 무선 연결 완료

현재 파이는 **G109_IoT_2.4G**에 연결됐으며 Wi-Fi 주소는 **192.168.1.50**이다. DHCP 주소이므로 바뀔 수 있다. NetworkManager 프로필 `bmo-wifi`에 자동 연결을 켰으며 Wi-Fi 경로 우선순위는 50이다. 기존 유선 `192.168.1.50`과 `pi-static` 설정은 유지했다.

PC의 Wi-Fi 주소 `172.16.63.226`에서 파이의 무선 주소로 새 SSH 접속을 열어 기존 호스트 키와 일치하는지 검증했다. 외부 경로가 `wlan0`을 사용하며 DNS와 인증서 검증을 포함한 외부 HTTPS TLS 연결에 성공했다. 파이 시계도 현재 날짜로 동기화됐다. 실제 랜선 분리 및 재부팅 후 재연결은 아직 시험하지 않았다. BMO 서비스는 확인 당시 `inactive`였으며 이 네트워크 설정 작업에서 시작하지 않았다.

PC PowerShell에서 무선 SSH 접속:

```powershell
ssh -i "$env:USERPROFILE\.ssh\bmo_pi_ed25519" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.1.50 pi-user@192.168.1.50
```

`HostKeyAlias`는 기존 유선 접속에서 등록한 동일 파이의 호스트 키를 검증하기 위한 옵션이다. 비밀번호는 이 문서나 설정 도구에 저장하지 않았다. 무선 접속 확인 결과는 `output/pi-wifi-result.json`에 저장했다. 아래 기록은 과거 유선 구성과 당시 인터넷 상태를 설명한다.

접속 대상은 `pi-user@192.168.1.50`입니다. 유선 PC 주소는 `192.168.137.1`이고, BMO 프로젝트는 파이의 `/home/pi-user/bmo-project`에 설치했습니다. Raspberry Pi 5, aarch64, Debian 13, Python 3.13.5 환경입니다.

## PC에서 파이 BMO 열기

이 프로젝트 폴더에서 PowerShell을 열어 실행합니다.

```powershell
.\connect-pi.ps1
```

창을 열어 둔 상태에서 PC 관리자는 `http://127.0.0.1:8775/admin`, 얼굴 미리보기는 `http://127.0.0.1:8775/phone`으로 접속합니다. 이 주소의 서버는 파이에서 실행됩니다. 기존 PC 서버와 포트가 다릅니다. 실제 아이폰의 음성 입력에는 README의 HTTPS 설정이 별도로 필요합니다.

## 파이에서 실행 제어

```bash
systemctl --user start bmo.service
systemctl --user restart bmo.service
systemctl --user status bmo.service --no-pager
journalctl --user -u bmo.service -n 40 --no-pager
```

서비스는 사용자 권한으로 실행합니다. 2026-10-15 LCD 설정에서 자동 실행을 활성화했으며 수동 시작은 `systemctl --user start bmo.service`입니다. 서비스는 `start-pi.sh --auto-camera --pc-port 8775`를 실행해 카메라가 인식되면 카메라 모드, 그렇지 않으면 음성 전용 모드로 시작합니다. 실제 질문에 카메라 사진을 넣으려면 PC 관리자에서 **파이 카메라 / 시작 사진**을 선택합니다.

API 설정은 PC에서 암호화된 SSH로 파이의 `bmo/private_config.py`에 옮겼고 파일 권한은 `600`입니다. ZIP에는 실제 키를 넣지 않습니다. 가상 환경 `.venv`는 설치된 Pillow와 Picamera2를 사용하고, `.venv-camera`는 같은 환경을 가리킵니다.

## 검증

재부팅 후 파이에서 Python 테스트 36개가 통과했고 Pillow·Picamera2 가져오기, OpenAI 설정 형식, 관리자·얼굴·이미지 경로의 HTTP 응답을 확인했습니다. PC에서 SSH 터널 포트의 접속 검사를 포함한 Python 테스트 36개와 음성 입력 상태·공유 응답·표정 애니메이션 JavaScript 테스트 12개가 통과했습니다. PC의 8775 포트를 통한 관리자·얼굴·자산 접속도 확인했습니다. 유료 API 요청은 보내지 않았습니다.

## 카메라 모델과 연결 설정

처음에는 사용자가 알려준 Rev 1.3(OV5647) 기준으로 설정했으나, 2026-10-08에 첨부한 실제 카메라 사진에는 **Camera V2** 표기가 보였습니다. **CAM/DISP 0**에 맞춰 `camera_auto_detect=0`, `dtoverlay=imx219,cam0`을 적용하고 재부팅한 뒤 **IMX219 센서 인식과 BMO 코드의 촬영에 성공했습니다.** 아래는 적용한 명령이며 다시 실행할 필요는 없습니다.

```bash
cd /home/pi-user/bmo-project
sudo python3 tools/configure_pi_camera.py --port 0 --sensor imx219 --apply && sudo reboot
```

스크립트는 Pi 5와 기존 카메라 설정을 확인하고 `/boot/firmware/config.txt.bmo-backup-날짜`에 백업한 뒤 `camera_auto_detect=0`, `dtoverlay=imx219,cam0`을 적용합니다. 실제 적용 전 미리보기는 `python3 tools/configure_pi_camera.py --port 0 --sensor imx219`입니다. 다른 부팅 설정은 유지합니다. 단일 OV5647/IMX219의 센서 및 0↔1 포트 전환을 지원하며 다른 센서나 복수 카메라 설정은 자동 변경하지 않습니다. Rev 1.3으로 되돌릴 경우에는 명시적으로 `--sensor ov5647`을 사용합니다. 근거: [Raspberry Pi 공식 카메라 설정](https://www.raspberrypi.com/documentation/computers/camera_software.html#configuration).

재부팅 후 다음으로 확인합니다.

```bash
rpicam-hello --list-cameras
systemctl --user start bmo.service
```

OV5647 설정에서는 1번 및 0번 포트 모두 센서 목록이 비어 있고 오류 -121이 발생했습니다. IMX219로 변경한 뒤에는 `rpicam-hello --list-cameras`에 `0 : imx219 [3280x2464 10-bit RGGB]`가 나타납니다. 현재 V2 카메라 인식 문제는 실제 센서에 맞는 드라이버로 해결됐습니다. `bmo.camera.Camera('pi')`로 1280×960 JPEG 촬영·카메라 해제에 성공했고, 검증용 사진을 `/home/pi-user/bmo-project/test-results/bmo-camera-test.jpg`에 저장해 PC로 전송했습니다. 센서 설정 테스트 5개는 PC와 파이 모두 통과했습니다.

사용자가 촬영 방향을 바꾼 뒤 두 번째 사진 `test-results/bmo-camera-scene.jpg`(1280×960, 49,204바이트)를 촬영했습니다. 이를 SSH로 PC에 받은 뒤 PC BMO 앱(8766)의 사진 업로드 API와 `camera=true` 대화 요청으로 OpenAI에 첨부했습니다. AI는 회색 니트 옷/팔로 보이는 부분, 흰 배경, 검은 물체 및 파란 물체를 설명했고 음성 합성도 성공했습니다. 사물 분류와 조명 추정은 모델의 해석이며 정확한 정답으로 확정하지 않습니다. 사진이 기울고 다소 흐릿해 고정·촬영 방향·초점은 추가 조정이 필요합니다. 이 검증은 **파이 촬영 → PC 전송 → PC의 API 요청**이며 파이에서 직접 API에 접속하는 인터넷 문제는 아직 해결되지 않았습니다. 검증 과정에서 PC API 요청 4회(대화 2회·음성 2회)를 추가로 사용했으며 마지막 요청에 사진을 첨부했습니다.

이번 백업 경로는 `/boot/firmware/config.txt.bmo-backup-20260917T143454040414Z`입니다. 파일명 날짜는 당시 파이 시스템 시계이며 실제 작업 날짜와 다릅니다. 파이 시스템 시계도 인터넷 복구 후 확인해야 합니다.

## 유선 인터넷 상태

파이는 PC(`192.168.137.1`)에 접속되지만, 확인 당시 `api.openai.com` DNS 조회가 시간 초과되었습니다. 기본 경로와 DNS는 모두 PC를 가리킵니다. 외부 IP ping도 응답하지 않았으나 이것만으로 인터넷 단절을 확정할 수는 없습니다. Windows 인터넷 공유와 DNS 전달 상태를 점검한 뒤 실제 API 통신을 확인해야 합니다.

## 2026-10-08 PC 실제 대화 테스트

파이의 Python 테스트 36개와 PC의 음성·표정 JavaScript 테스트 12개가 통과했습니다. 파이 서버를 재시작하고 PC SSH 터널의 관리자·얼굴 화면 HTTP 200을 확인했습니다.

파이 인터넷과 카메라를 기다리는 동안 PC에 별도 OpenAI 서버를 실행했습니다. 관리자 `http://127.0.0.1:8766/admin`, 얼굴 화면 `http://127.0.0.1:8766/phone`을 같은 서버로 사용합니다. 파이 서버(8775)와 PC 테스트 서버(8766)의 대화 이력은 별개입니다.

PC 서버에 짧은 한국어 연결 테스트 질문 한 건을 보내 실제 답변과 음성 합성 성공을 확인했습니다(API 요청 2회). 얼굴 화면용 공유 상태에도 같은 답변이 있고, MP3 응답은 HTTP 200 / audio/mpeg / 79,488바이트였습니다. 실제 마이크 녹음·스피커 재생·아이폰 화면은 이번 자동 확인에 포함하지 않았습니다. 테스트 서버를 다시 실행하려면 PC PowerShell에서 `./start-assistant.ps1 -Port 8766`을 사용하세요.

## BMO 화면 기기의 음성 출력

2026-10-08에 PC와 파이의 `/phone`에 **BMO 소리 켜기**와 최근 답변 다시 듣기를 반영했습니다. PC 관리자에서 질문한 답변 음성은 `/phone`을 연 기기에서 재생합니다. 사용자가 원하는 BMO 화면은 아이패드 Chrome이며 현재는 PC에서 미리보기로 시험 중입니다. 아이패드는 PC 관리자와 같은 BMO 서버의 신뢰된 HTTPS 주소로 연결해야 합니다. PC 미리보기 주소 `127.0.0.1`은 실제 아이패드 접속 주소로 쓸 수 없습니다. 연결 후 아이패드에서 소리 켜기를 한 번 누르고 PC의 `/phone` 탭을 닫으면 PC는 관리자 역할만 합니다.

PC JavaScript 테스트 16개와 데스크톱 Chrome의 기존 답변 음성 재생 상태를 확인했습니다. 실제 아이패드의 연결·스피커·마이크 검증은 남아 있습니다. 이번 UI 검증에서는 새 유료 API를 호출하지 않았습니다.

## 2026-10-08 아이패드 Wi-Fi 연결용 PC 서버

같은 Wi-Fi 기기용 HTTPS 서버를 PC의 **8768** 포트에 별도로 시작했습니다. PC 관리자는 `https://127.0.0.1:8768/admin`, 아이패드 Chrome 얼굴 화면은 `https://172.16.33.173:8768/phone`입니다. 인증서 설치 안내는 아이패드 Safari에서 `http://172.16.33.173:8767/`으로 엽니다. 이 주소는 PC의 당시 Wi-Fi 주소이며 바뀌면 갱신합니다. 기존 PC HTTP 8766과 파이 HTTP/SSH 터널 8775는 각각 별도 서버입니다.

현재는 파이 인터넷 문제를 해결한 구성이 아니라, 인터넷이 동작하는 PC에서 OpenAI·음성을 제공하는 구성입니다. 아이패드용 HTTPS·연결 코드·Windows 로컬 서브넷 접속 허용을 확인했고 사용자가 기기 연결 성공을 알렸습니다. 실제 아이패드의 음성 입출력 확인은 이어서 진행합니다. 인증서·개인 키는 파이 또는 ZIP에 자동 복사하지 않았습니다. 자세한 실행·인증서 설치 안내는 README의 PC 서버 연결 절을 사용합니다.
