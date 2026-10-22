**최신 사진 수정 · 파이 적용 완료:** “사진 찍어줘/다시 찍어줘”라고 하면 요청 후 새로 촬영한 한 장만 분석합니다. 촬영 실패 시 이전 사진으로 답하지 않습니다. `versions/BMO-fresh-photo-noeul-2026-10-22.zip`과 [BMO-FINAL.md](BMO-FINAL.md)를 우선합니다. 이전 버전 ZIP은 보존했습니다.

**2026-10-22 최종 통합 · 파이 적용 완료:** GPT-Live-1/노을, 가까운 목소리 필터, 현재 장면 분석, 대화 중 프로액티브를 통합했다. 사용/복원은 [BMO-FINAL.md](BMO-FINAL.md)를 우선한다. 아래의 미배포·아이폰·예전 IP 안내는 과거 기록이다.

# 2026-10-21 · 별도 노을 버전과 네트워크 안내

GPT-Live-1 + 노을은 `start-live-noeul.ps1` / `start-pi-live-noeul.sh`로 실행한다. 기존 실행기는 Realtime을 유지한다. 설치와 제한은 [BMO-LIVE.md](BMO-LIVE.md), PC 없이 파이에서 동작하는 구조는 [BMO-NETWORK.md](BMO-NETWORK.md)를 따른다. 새 버전은 PC에 준비했고 파이에는 아직 배포하지 않았다. 아래의 예전 접속 주소보다 현재 실행기의 출력과 위 두 안내를 우선한다.

# BMO 음성 비서 — 아이폰 얼굴 + PC 관리자

**최신 감정 표정:** BMO 답변을 12개 감정 단어 중 하나로 분류하고, 연결된 여러 후보 중 한 장을 답변 동안 유지합니다. Rosto 1~25번 중 15번을 제외한 24장을 사용합니다. 듣기·생각 중·대기 전환은 우선하며 자세한 후보·실시간 추가 호출·검증은 [BMO-EMOTIONS.md](BMO-EMOTIONS.md)를 따릅니다. 현재 버전은 `BMO-emotion-faces-2026-10-15.zip`입니다.

**최신 음량 설정:** LCD 하단 **설정**을 열면 마이크·스피커 음량을 각각 0~100%로 조절할 수 있습니다. 슬라이더 또는 −/+ 버튼을 사용하며 두 대화 방식 모두에 적용됩니다. 현재 버전은 `BMO-audio-controls-2026-10-15.zip`입니다.

**2026-10-15 현재 실행 버전:** 사용자 요청으로 실시간 대화를 다시 복원했습니다. Pi 5의 MPI5008 LCD 하단 중앙에 **눌러서 말하기 / 실시간 대화 시작**을 나란히 표시합니다. 같은 실시간 버튼으로 종료하며 생각하는 표정과 `생각 중 …`를 유지합니다. 기존 모델은 `gpt-realtime-2.1`입니다. 버전 구분은 [BMO-VERSIONS.md](BMO-VERSIONS.md), 장치 상태는 [BMO-HARDWARE.md](BMO-HARDWARE.md)를 우선하세요. 호출어 기능은 보류했습니다.

2026-10-15 장치 방향 변경: **라즈베리파이 5 + MPI5008 LCD + USB 마이크·스피커**에서 기존 웹앱을 실행하는 구성을 준비합니다. 로컬 AI 모델로 전환하지 않고 현재 클라우드 연결을 유지합니다. LCD와 음성 부품은 아직 연결·검증 전입니다. 앞으로의 장치 구성은 [BMO-HARDWARE.md](BMO-HARDWARE.md)를 먼저 확인하세요. 아래 휴대폰·아이패드 설명은 기존 시험 구성입니다.

2026-10-14: Windows 실행기는 기본으로 **연결 코드 없이 자동 접속**합니다. 같은 네트워크에서 HTTPS 주소를 열면 바로 연결되며 PC 관리자 제한과 요청 보호는 유지됩니다. 연결 코드를 다시 요구하려면 실행기에 `-RequirePairing`을 붙입니다. 현재 접속 주소와 테스트 상태는 `BMO-REALTIME.md`를 확인하세요.

2026-10-12: 기존 음성·얼굴 화면에 이미지 입력을 지원하는 **GPT-Realtime-2.1 실시간 대화**와 **사진 묶음·PC 웹캠 프레임**을 추가했습니다. 현재 사용 방법과 검증 범위는 [BMO-REALTIME.md](BMO-REALTIME.md)를 먼저 확인하세요. GPT-Live 1 + 이미지 분석 백엔드는 아직 구현하지 않았습니다.

아이폰 또는 아이패드는 BMO 얼굴과 음성 입출력, PC는 문장 입력과 사진 관리 역할을 합니다. 두 화면은 **같은 BMO 서버**에 접속해 대화 기록과 장면 설정을 공유합니다. PC에서 보낸 문장의 답변도 `/phone`에 표시되고, 음성 생성이 성공하면 그 화면을 연 기기의 스피커에서 재생됩니다. PC 관리자 화면은 음성을 재생하지 않습니다. 동시 요청은 순서대로 처리합니다.

## BMO 장치에서 소리 듣기

1. BMO에 넣을 아이패드 Chrome 또는 아이폰에서 같은 서버의 `/phone`을 엽니다. 실제 기기 연결에는 아래 HTTPS 설정이 필요합니다.
2. **BMO 소리 켜기**를 한 번 누릅니다. 이미 답변이 있으면 최근 답변을 재생하고, 아직 없으면 짧은 확인음을 냅니다. 이 버튼은 마이크 권한이나 새 AI 호출을 사용하지 않습니다.
3. PC의 `/admin`에서 질문하면 새 답변을 BMO 화면에서 재생합니다. 자동 재생이 막히면 **BMO 소리 켜기** 또는 **↻**를 눌러 들을 수 있습니다.

얼굴 화면을 나중에 열거나 새로고침해도 최근 답변을 **↻**로 다시 들을 수 있습니다. PC의 `/phone`도 열어 두면 PC에서 소리가 날 수 있으므로, 실제 아이패드로 옮긴 뒤에는 PC 얼굴 미리보기 탭을 닫고 `/admin`만 열어 두세요. 화면을 잠그거나 브라우저를 닫으면 재생이 계속된다고 보장하지 않습니다.

아이폰은 **가로 방향으로 BMO 본체의 화면 자리에 넣는 구성**입니다. `/phone`은 첨부한 얼굴 이미지를 화면 전체에 보여 줍니다. 평소에는 미소와 짧은 눈 깜빡임, 녹음 중에는 듣는 표정, 처리 중에는 생각하는 표정으로 바뀝니다. 음성 답변 중에는 입을 열고 닫으며, 브라우저가 허용하면 실제 재생 음량에 맞춥니다. 이미지 30장은 모두 `bmo/web/faces/`에 포함했고, 강한 감정 표정은 일반 대화 중 임의로 등장하지 않게 했습니다. 이 이미지들은 연속 동영상 프레임이 아니라 서로 다른 표정이므로, 표정 사이를 짧게 전환하는 방식입니다.

기본은 눌러 말하기이며, 얼굴 화면의 **실시간 대화**에서 연속 음성 연결을 시작할 수 있습니다. 먼저 말하기는 자동으로 켜지지 않습니다. 기존 질문은 선택한 사진 한 장 또는 최근 프레임 묶음을 사용하고, 실시간 모드는 사용자가 켠 프레임 전송 선택을 따릅니다.

## API 키를 한 번만 설정

프로젝트의 **`bmo/private_config.py`** 파일을 열어 `OPENAI_API_KEY`의 따옴표 사이에 본인 키 값만 넣고 저장하세요.

```python
OPENAI_API_KEY = "여기에 본인 OpenAI API 키 값"
ANTHROPIC_API_KEY = ""
```

이 파일은 Git에서 제외됩니다. 배포 ZIP에는 실제 파일 대신 **키가 비어 있는 템플릿만** 들어갑니다. 브라우저에 전송되지 않으며 서버에서만 읽습니다. 파일을 공유하거나 채팅에 키를 붙여 넣지 마세요. 파일에 키 값이 있으면 환경 변수보다 우선하고, 파일이 비어 있으면 환경 변수를 사용합니다. 키를 바꾼 뒤에는 서버를 다시 시작해야 합니다. `start-assistant.ps1`과 `start-pi.sh`는 이제 키 입력을 묻지 않습니다. Claude를 쓸 때만 `ANTHROPIC_API_KEY`도 설정합니다.

## Windows에서 실행

프로젝트 폴더(`start-assistant.ps1`이 있는 곳)에서 PowerShell을 열고:

```powershell
.\start-assistant.ps1
```

`py` 명령이 없으면 스크립트가 이 PC에 포함된 Python을 찾아 사용합니다. 이미 사용 중인 포트는 건너뛰고 접속 주소를 출력합니다. 실행을 끝내려면 PowerShell에서 `Ctrl+C`를 누르세요. 얼굴 화면 파일 변경은 브라우저를 새로고침하면 반영됩니다. Python 코드나 서버 설정을 변경했을 때는 서버를 다시 시작합니다.

- **PC 관리자:** 출력된 주소에 `/admin`을 붙여 엽니다. 예: `http://127.0.0.1:8766/admin`
- **아이폰 화면 미리보기:** 같은 PC에서 주소에 `/phone`을 붙여 엽니다. 예: `http://127.0.0.1:8766/phone`. 창을 가로로 넓게 보면 실제 장착 비율에 가깝습니다.
- **아이폰 실제 사용:** 아이폰 Safari에서 Pi 또는 PC의 신뢰된 HTTPS 주소로 접속합니다. 아이폰에서 기본 `/` 주소를 열면 얼굴 화면이 나옵니다. `127.0.0.1`은 각 기기 자신의 주소라서 PC의 `127.0.0.1`을 아이폰에서 열 수는 없습니다.

아이폰을 가로로 돌려 `/phone`을 열고 Safari의 **홈 화면에 추가**를 사용하면 얼굴 화면을 더 크게 볼 수 있습니다. 녹음 버튼은 화면 하단에 겹쳐 있으며 한 번 눌러 시작하고 다시 눌러 전송합니다. 가로 회전이 고정되어 있으면 아이폰의 회전 잠금을 해제하세요.

PC에서 문장을 입력하면 아이폰 화면도 같은 서버의 새 답변을 표시합니다. 아이폰에서 **눌러서 말하기**를 한 번 누르면 녹음 시작, 다시 누르면 전송합니다. 최대 45초입니다. × 버튼은 아이폰의 녹음·재생을 멈춥니다. PC의 **대화 지우기**는 두 화면의 공유 대화 기록을 지웁니다.

PC의 **입력 이미지**에서 네 가지 모드를 고릅니다. **사용 안 함**은 사진을 보내지 않습니다. **파이 카메라 / 시작 사진**은 질문마다 새 사진을 촬영하거나 시작할 때 지정한 파일을 읽습니다. **PC에서 올린 사진**은 PC가 올린 사진을 서버 메모리에 보관해 질문에 첨부합니다. **여러 프레임**은 사진 묶음 또는 PC 웹캠에서 시간 순서로 최대 4장을 선택합니다. 사진은 텍스트 대화 기록에 저장하지 않으며, 프레임은 제거하거나 서버를 종료하면 사라집니다. 실시간 세션의 시각 입력은 현재 **여러 프레임** 모드를 사용합니다.

라즈베리 파이 카메라가 아직 없다면 Windows에서 사진 파일로 이미지 흐름을 시험할 수 있습니다.

```powershell
.\start-assistant.ps1 -ImagePath 'C:\사진\책상.jpg'
```

이 경우 PC 관리자에서 **파이 카메라 / 시작 사진**을 선택하면 파일을 질문에 사용합니다. `-ImagePath`에는 존재하는 JPG 또는 PNG 파일을 넣으세요. Pillow가 없는 일반 Python 환경에서는 `python -m pip install -r requirements.txt`로 설치합니다.

## Raspberry Pi 5에 옮기기

이 PC에서 전용 SSH 키를 등록한 파이에 접속할 때는 프로젝트 폴더의 PowerShell에서 `./connect-pi.ps1`을 실행합니다. 기본 접속 대상은 `pi-user@192.168.1.50`이고, PC의 `http://127.0.0.1:8775/admin`을 파이의 서버로 연결합니다. 이 창을 열어 둔 상태로 사용하세요. 파이 IP가 바뀌면 `./connect-pi.ps1 -PiHost 새IP`로 실행합니다. 이 HTTP 터널은 PC 관리자와 얼굴 미리보기용이며, 실제 아이폰 마이크에는 아래 HTTPS 설정이 필요합니다.

원격 설치 후 프로젝트 경로는 `/home/pi-user/bmo-project`이고, 실행 서비스는 `bmo.service`입니다. 파이 터미널에서 `systemctl --user start bmo.service`, `systemctl --user stop bmo.service`, `systemctl --user restart bmo.service`로 제어하고, `journalctl --user -u bmo.service -n 40 --no-pager`로 로그를 확인합니다. 서비스는 시작할 때 카메라 인식을 확인해 카메라 모드 또는 음성 전용 모드를 선택합니다. 처음 설치 시 서비스를 시작하며, 부팅 자동 실행은 별도로 설정합니다.

Pi에는 Raspberry Pi OS 64비트와 Python 3.10 이상을 사용합니다. 프로젝트 폴더를 Pi로 복사하세요. ZIP 파일에는 실제 API 키가 들어 있지 않으므로, Pi의 `bmo/private_config.py`에도 본인이 키를 직접 입력하거나 환경 변수를 설정해야 합니다.

```powershell
scp -r 'C:\프로젝트\bmo-project' 사용자명@파이IP:~/bmo-project
ssh 사용자명@파이IP
```

Pi에서 음성만 실행할 때:

```bash
cd ~/bmo-project
python3 -m venv .venv
bash start-pi.sh
```

카메라 케이블이 도착하면 **Pi 전원을 완전히 끈 상태**에서 연결합니다. Pi 5에는 22핀 미니 커넥터용 케이블이 필요하며 CAM/DISP0 또는 CAM/DISP1을 사용할 수 있습니다. [Raspberry Pi 카메라 연결 안내](https://www.raspberrypi.com/documentation/accessories/camera.html)

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-pil python3-venv rpicam-apps
rpicam-hello --list-cameras
rpicam-still -n -o camera-test.jpg
python3 -m venv --system-site-packages .venv-camera
bash start-pi.sh --camera
```

먼저 `rpicam-*` 명령으로 장치 인식과 촬영을 확인하세요. [Raspberry Pi 카메라 소프트웨어 안내](https://www.raspberrypi.com/documentation/computers/camera_software.html) 카메라가 두 대라면 `--camera-index 1`을 추가할 수 있습니다. 카메라가 없어도 음성만 쓰려면 `--camera`를 빼면 됩니다.

## 아이패드·아이폰을 같은 Wi-Fi에서 연결

### PC 서버에 연결하기

PC와 아이패드를 같은 Wi-Fi에 연결하고, PC의 `ipconfig`에서 **Wi-Fi IPv4 주소**를 확인합니다. 기본 `127.0.0.1` 주소는 PC 내부에서만 동작합니다. 이 PC에서 현재 실행 중인 공유 서버는 **8768**, 인증서 설치 안내는 **8767** 포트를 사용합니다. 관리자와 BMO 화면은 모두 같은 8768 서버를 사용해야 합니다. 기존 8766 서버의 대화와는 별개입니다.

```powershell
.\start-assistant.ps1 -LanIP 172.16.33.173 -Port 8768 -SetupPort 8767
```

위 IP는 설정 당시 주소입니다. 주소가 바뀌면 실제 PC 주소로 바꿉니다. 실행기는 `certs/`에 BMO 전용 CA와 서버 인증서를 만들고 개인 키 폴더를 현재 사용자만 접근하도록 제한합니다. PC 관리자도 경고 없이 접속할 수 있도록 **현재 Windows 사용자**의 신뢰된 루트 저장소에 이 CA를 등록합니다. 일반 Python에서 필요한 라이브러리가 없으면 먼저 `python -m pip install -r requirements-lan.txt`로 설치합니다. CA·개인 키·생성 인증서는 Git과 배포 ZIP에서 제외합니다.

Windows 방화벽에서 다른 기기 접속이 막히면 실행기가 출력한 방화벽 설정 명령을 **관리자 PowerShell**에서 한 번 실행합니다. 이 PC에 적용한 명령은 다음과 같습니다.

```powershell
.\tools\allow-bmo-lan.ps1 -LanIP 172.16.33.173 -Port 8768 -SetupPort 8767
```

이 규칙은 지정한 PC 주소의 두 TCP 포트와 해당 Python 실행 파일만 로컬 서브넷에 허용합니다. 실행 중인 BMO LAN 서버를 확인해 실제 Python 경로를 찾으므로 서버를 먼저 시작합니다. 필요하면 실행기에 출력된 `-PythonPath`로 직접 지정할 수 있습니다. 방화벽을 끄거나 인터넷 공유기 포트를 공개하지 않습니다. 규칙 제거는 관리자 PowerShell에서 `Remove-NetFirewallRule -Name BMO-LAN-Access`로 할 수 있습니다.

1. 아이패드 **Safari**에서 `http://172.16.33.173:8767/`을 열고 **BMO 인증서 받기**를 누릅니다.
2. **설정 → 일반 → VPN 및 기기 관리**에서 **BMO Local Development CA** 프로파일을 설치합니다.
3. **설정 → 일반 → 정보 → 인증서 신뢰 설정**에서 해당 CA의 전체 신뢰를 켭니다. [Apple 안내](https://support.apple.com/en-us/102390)
4. 아이패드 **Chrome**에서 현재 PC 주소의 `/phone`을 열면 자동 연결됩니다. **BMO 소리 켜기**를 누릅니다.
5. PC는 `https://127.0.0.1:8768/admin`을 열면 자동 연결됩니다. PC의 이전 `/phone` 미리보기 탭은 닫습니다.

인증서 설치는 처음 한 번입니다. 기본 자동 연결에서는 연결 코드를 입력하지 않습니다. `-RequirePairing`으로 실행한 경우에만 서버를 재시작할 때 바뀌는 연결 코드를 사용합니다. Wi-Fi 주소가 변경돼도 기존 CA를 유지하므로 새 주소로 실행하면 서버 인증서만 갱신합니다. 설치 안내 HTTP 서버는 공개 인증서와 안내 화면만 제공하며 대화·음성·API 키·개인 키를 제공하지 않습니다. BMO API는 HTTPS와 Host·Origin·요청 토큰 검사를 유지합니다. 같은 Wi-Fi라도 공유기의 기기 간 통신 차단이 켜져 있으면 접속되지 않을 수 있습니다.

### 다른 네트워크에서 연결하기

PC와 아이패드를 Tailscale 같은 전용 VPN으로 같은 개인 네트워크에 연결한 뒤 해당 주소·인증서를 앱에 설정하거나, 접근 권한이 있는 사용자에게만 열리는 HTTPS 중계 기능을 사용합니다. [Tailscale 개인 네트워크 HTTPS 안내](https://tailscale.com/docs/features/tailscale-serve) 현재는 같은 Wi-Fi 연결만 설정했으며 외부 네트워크용 VPN·중계는 아직 구성하지 않았습니다. 중계를 추가할 때는 실제 기기를 로컬 관리자로 잘못 인식하지 않도록 관리자 접근 정책도 함께 점검해야 합니다.

### 파이 서버에 직접 연결하기

아이폰 Safari 마이크를 사용하려면 신뢰된 HTTPS 주소가 필요합니다. 이 앱은 인증서 없이 외부 접속을 허용하지 않습니다. 개발용으로 [mkcert](https://github.com/FiloSottile/mkcert)를 사용해 실제 Pi IP가 포함된 인증서를 만들 수 있습니다. 아래 IP는 예시이며 실제 주소로 바꿔야 합니다.

```powershell
New-Item -ItemType Directory -Force certs
mkcert -install
mkcert -cert-file certs/bmo.pem -key-file certs/bmo-key.pem 192.168.0.50 localhost 127.0.0.1
mkcert -CAROOT
```

`mkcert -install`은 만든 CA를 개발 PC의 신뢰 저장소에 추가합니다. `-CAROOT`가 가리키는 폴더에서 **rootCA.pem만** 아이폰에 설치하고, 아이폰 설정의 **일반 → 정보 → 인증서 신뢰 설정**에서 이 CA를 신뢰하도록 설정하세요. `rootCA-key.pem`은 절대 전달하지 않습니다. [Apple의 인증서 신뢰 안내](https://support.apple.com/102390)

서버 인증서와 키를 Pi의 프로젝트 `certs` 폴더로 복사한 뒤:

```powershell
scp -r certs 사용자명@파이IP:~/bmo-project/
```

```bash
cd ~/bmo-project
chmod 600 certs/bmo-key.pem
bash start-pi.sh --camera --lan 192.168.0.50
```

아이폰 Safari에서 `https://192.168.0.50:8765/`를 열고 Pi 터미널에 출력된 **Device pairing code**를 입력합니다. 이 코드는 API 키와 다릅니다. PC 관리자는 같은 Pi에 SSH 터널을 연 뒤 `https://127.0.0.1:8765/admin`으로 접속하세요. 이때 PC의 8765 포트가 비어 있어야 하며, Pi가 HTTPS로 실행 중이므로 PC 쪽도 `https`를 사용합니다.

```powershell
ssh -N -L 8765:127.0.0.1:8765 사용자명@파이IP
```

PC 관리자 API는 서버에서 로컬 접속에만 열립니다. SSH 터널을 쓰면 Pi는 PC를 로컬 연결로 인식합니다. Pi의 API 키와 사진은 아이폰에 저장되지 않습니다. 이 서버는 같은 Wi-Fi의 개인용 프로토타입입니다. 공유기 포트를 인터넷에 공개하지 마세요.

## 동작과 제한

음성 질문 한 번은 보통 음성 인식·대화·음성 합성 API 호출 3회, PC의 글 질문은 대화·음성 합성 호출 2회입니다. 최근 6회의 질문/답변을 대화 맥락으로 사용하고, 표시용 기록은 최근 24개 메시지입니다. 음성·사진은 디스크에 저장하지 않습니다. 업로드 사진과 최근 8개 답변 음성은 서버 메모리에 남고 서버 종료 시 사라집니다.

PC와 아이폰이 같은 순간 요청하면 서버가 순서대로 처리합니다. 아이폰의 취소는 그 아이폰 요청에만 적용하고, PC의 대기 중 문장은 유지합니다. 브라우저가 PC에서 시작한 답변 음성의 자동 재생을 막으면 **BMO 소리 켜기** 또는 **↻** 버튼으로 재생할 수 있습니다. Raspberry Pi 5의 Camera V2 / IMX219 촬영과 PC에서의 사진 분석·음성 생성은 확인했습니다. 실제 아이패드 Chrome과 아이폰 Safari의 마이크·스피커는 기기에서 확인해야 합니다.

테스트: `python -m unittest discover -s tests -v`와 `node --test tests/test_voice_ui.cjs tests/test_face_ui.cjs`. 자세한 검증 범위는 `VALIDATION.md`에 기록했습니다. Windows의 `tools/package-bmo.ps1`은 코드·얼굴·테스트를 ZIP으로 묶고 API 키는 빈 템플릿으로 넣습니다. Pi에 실제 키를 옮길 때는 이 ZIP과 별도로 암호화된 SSH 연결을 사용합니다.

