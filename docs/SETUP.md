# BMO 설치와 네트워크

2026년 10월 22일 소스 기준 안내다. Raspberry Pi 5의 데스크톱 환경, MPI5008, IMX219, USB 마이크·스피커 구성을 기준으로 한다. 화면·터치 설정은 배선과 OS 환경에 따라 달라질 수 있다.

## 최초 준비

BMO 소스가 있는 폴더에서 다음과 같이 가상 환경을 만든다. Picamera2는 Raspberry Pi OS의 시스템 패키지를 사용하므로 카메라 환경은 `--system-site-packages`로 생성한다.

```bash
sudo apt update
sudo apt install python3-venv python3-picamera2 python3-pil rpicam-apps chromium
python3 -m venv --system-site-packages .venv-camera
.venv-camera/bin/python -m pip install -r requirements-live.txt
```

음성 전용 실행의 기본 환경은 `.venv`이므로 카메라 미연결 시에도 실행할 계획이라면 함께 준비한다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-live.txt
```

API 키는 서버에서 읽는다. 공개 코드에는 실제 키를 넣지 않는다. 별도의 로컬 설정 파일이 없다면 터미널에서 아래와 같이 입력할 수 있다. 이 환경 변수는 해당 터미널의 실행에 적용되며, 서비스 자동 실행 설정에 자동으로 저장되지는 않는다.

```bash
read -rs -p 'OpenAI API key: ' OPENAI_API_KEY
echo
export OPENAI_API_KEY
```

자동 실행 서비스에서 사용할 경우 `tools/pi_install.py --help`와 기존 설치 문서를 확인해 서비스의 실행 환경 또는 비공개 서버 설정을 별도로 준비한다. Live 모델 이용 권한과 API 사용 가능 상태가 필요하다. 이 문서는 계정별 권한이나 실제 청구 금액을 보장하지 않는다.

## 카메라와 LCD

카메라 연결은 파이 전원을 끈 상태에서 확인한다. 이 프로젝트의 최종 카메라는 IMX219이며 CAM/DISP 0을 사용했다. 다음 명령은 먼저 변경 예정 내용을 보여 준다.

```bash
python3 tools/configure_pi_camera.py --port 0 --sensor imx219
python3 tools/configure_pi_display.py
```

본인 장치와 맞는 것을 확인한 뒤 `sudo`와 `--apply`를 사용하면 기존 설정을 백업하고 적용한다. 변경 후 재부팅이 필요하다. 다른 센서나 포트를 사용하면 해당 값을 바꾼다.

```bash
sudo python3 tools/configure_pi_camera.py --port 0 --sensor imx219 --apply
sudo python3 tools/configure_pi_display.py --apply
sudo reboot
```

부팅 후 `rpicam-hello --list-cameras`로 인식을 확인한다. MPI5008의 HDMI 화면 출력과 GPIO 터치 입력은 별개다. 기존 LCD 드라이버 설치 명령을 무조건 실행하기보다 현재 카메라·화면 설정을 보존하는 프로젝트 도구를 기준으로 확인한다. [제품 연결 설명](https://www.lcdwiki.com/5inch_HDMI_Display)

## 수동 실행과 종료

```bash
bash start-pi-live-noeul.sh --auto-camera --observe --pc-port 8775
```

파이 Chromium에서 `http://127.0.0.1:8765/phone`을 연다. 브라우저에 마이크 권한을 허용하고 노을 대화를 시작한다. 카메라가 감지되지 않으면 실행기는 음성만으로 시작하며, 요청 사진 기능은 사용할 수 없다. `--model`은 별도 답변·이미지 분석 모델 설정이며 Live 음성 모델 이름을 바꾸는 옵션이 아니다.

이미 자동 실행 서비스가 있다면 다음으로 상태를 확인하고 기존 서비스를 중지한 뒤 수동 실행한다. 중복 서버의 포트 충돌을 피한다.

```bash
systemctl --user status bmo.service
systemctl --user stop bmo.service
# 수동 실행 후 Ctrl+C로 종료
systemctl --user start bmo.service
```

데스크톱의 전체 화면은 `Alt+F4`로 닫을 수 있다. `bash start-pi-kiosk.sh`는 설치된 `bmo.service`를 시작한 뒤 LCD 브라우저를 연다. 새 파이에 이 스크립트만 복사한다고 서비스가 설치되지는 않는다.

## PC에서 관리자 화면 보기

파이에 인터넷이 있으면 서버와 화면은 파이 자체에서 실행된다. PC는 필수가 아니다. PC에서 관리할 때는 파이의 현재 주소와 SSH 계정으로 터널을 연다. 아래 꺾쇠 괄호 부분은 실제 값으로 바꾼다.

```bash
ssh -N -L 8775:127.0.0.1:8765 <pi-user>@<pi-ip>
```

PC 브라우저에서 `http://127.0.0.1:8775/admin`을 연다. 다른 PC나 태블릿의 `127.0.0.1`은 각각 그 기기 자신이다. 직접 LAN 접속을 사용하려면 서버 호스트 허용·HTTPS·브라우저 마이크 권한을 별도로 구성해야 하며, 로컬 터널 주소만 전달해서는 다른 기기에서 접속되지 않는다.

파이 IP가 바뀌면 SSH 목적지를 바꾼다. AI API 연결 실패는 파이의 인터넷·DNS·API 인증·이용 상태·WebRTC 통신 등을 따로 확인한다. PC와 파이의 유선 연결 성공만으로 파이의 인터넷 연결까지 입증되지는 않는다.
