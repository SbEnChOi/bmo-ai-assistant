# BMO 장치 구성 — MPI5008과 기존 웹앱

최신 추가: LCD의 **설정**에 실제 파이 기본 마이크·스피커 음량 조절기를 추가했다. 0~100% 슬라이더와 5% 단위 버튼을 제공한다. 장치 인식·실제 변경을 확인했으며 마이크 시험은 39→44→39%, 스피커는 시험 직전의 50→45→50%로 복원했다. 커널에 USB 연결 해제 흔적은 없고 전원 상태 `get_throttled=0x0`이었다. 사용자는 첫 몇 마디만 출력되는 현상을 다시 시험할 예정이다. 최근 접속은 유선 192.168.1.50, 파이에서 확인한 현재 Wi-Fi 주소는 192.168.1.120이다. 아래 11.135.148.117은 이전 네트워크 기록이다.

2026-10-15 사용자 확정 방향. 휴대폰을 본체에 넣는 구성을 라즈베리파이 5와 5인치 MPI5008로 변경한다. 기존 BMO 웹앱과 클라우드 AI 연결을 유지하며, 원본 영상의 로컬 모델 실행 방식으로 전환하지 않는다.

최신 UI는 **눌러서 말하기 + 실시간 대화 + 생각하는 표정 + 생각 중 …**다. 사용자 요청으로 기존 실시간 기능을 다시 복원하고 시작·종료 버튼을 눌러서 말하기 옆 하단 중앙으로 옮겼다. 버튼 높이 50px, 하단 여백 28px이며 실제 800×480 LCD 화면을 확인했다. 호출어 기능은 보류했으며 버전은 `BMO-VERSIONS.md`를 따른다.

음성 장치 최신 기록: USB Jieli UACDemoV1.0 스피커를 기본 출력으로 선택한 뒤 실제 한국어 합성 음성을 재생했고 사용자는 작게 들린다고 확인했다. 요청에 따라 출력 100%를 적용했다. AB13X USB Audio 캡처 장치도 인식됐고 앱의 실제 음성 인식·답변 음성 생성은 성공했다. 이후 USB가 잠시 분리됐다가 사용자가 재연결했고, 두 장치 인식·기본 출력/입력·음소거 해제와 스피커 100%를 다시 확인했다. 마이크 음량은 기존 39%를 유지했다. 이번 실시간 UI 복원에서는 마이크 녹음·유료 실시간 호출을 하지 않았다. 아래 USB 미연결 설명은 초기 설치 당시 기록이다.

## 현재 상태

- 사용자가 확인한 디스플레이: **5inchDisplay MPI5008**.
- LCD의 HDMI·USB 전원·26핀 GPIO 연결을 사용자가 완료했다. 파이의 실제 출력은 **HDMI-1, 800×480, 60Hz**, 데스크톱은 X11/LXDE다.
- 사용자가 알려준 USB 마이크 모델: **JBC-055**. 파이에서 인식·녹음은 아직 검증하지 않았고 공식 Linux 호환 자료도 확인하지 못했다.
- 스피커는 아직 선택하지 않았다. 추천 후보는 아래에 기록하되 구매·확정한 것으로 간주하지 않는다.
- 최신 웹앱을 기존 API 설정 보존·소스 백업 후 파이에 반영했다. 파이에서 Python 테스트 **66개 통과**, 로컬 BMO 서버와 실제 LCD Chromium 전체 화면을 확인했다. 화면과 서버 자동 실행을 설정했으나 설정 후 재부팅 시험은 아직 하지 않았다.
- 재부팅 후 Wi-Fi 프로필은 `dlink`, 주소는 **11.135.148.117/19**다. 이 주소로 새 SSH 연결과 PC 관리자 터널 접속에 성공했고 외부 경로 wlan0·OpenAI 주소 DNS/TLS 연결도 확인했다. 유선 `192.168.1.50`은 유지했다. 실제 랜선 분리 시험은 아직 하지 않았다.

## 2026-10-15 터치 해결과 LCD 화면 실행

처음에는 X11과 `/proc/bus/input/devices`에 터치 장치가 없고 GPIO 7~11의 SPI0도 꺼져 있었다. 사용자가 설정 적용·재부팅을 마친 뒤 **ADS7846 Touchscreen, /dev/input/event5, spi0.1**을 커널과 X11에서 확인했다. 사용자가 실제 터치가 잘 인식된다고 확인했다. `nospi10`, HDMI 800×480/60Hz와 `imx219,cam0` 카메라는 보존됐고 IMX219 센서 목록도 정상이다.

`tools/configure_pi_display.py`를 PC와 파이 프로젝트에 추가했다. 설치된 공식 ADS7846 오버레이에 SPI0, CS1(GPIO7), IRQ(GPIO25)와 제조사 기본 터치 범위를 지정한다. 기본 실행은 변경분만 표시하며, `--apply`일 때만 부팅 설정을 백업하고 저장한다. 다른 터치 오버레이·명시적 SPI 비활성화·편집된 관리 블록이 있으면 자동 적용하지 않는다. 제조사의 전체 LCD5-show 스크립트는 실행하지 않았다.

설정·백업 테스트 5개와 기존 카메라 설정 테스트 5개를 통과했고, 파이의 실제 설정으로도 미리보기를 확인한 뒤 사용자가 아래 명령으로 적용했다. **현재는 재실행할 필요가 없다.**

```bash
cd /home/pi-user/bmo-project
sudo python3 tools/configure_pi_display.py --apply && sudo reboot
```

백업은 `/boot/firmware/config.txt.bmo-display-backup-날짜`다. 정량적인 모서리 좌표·감도 보정 시험은 아직 하지 않았으며 위치가 어긋날 때만 추가 보정한다. GPIO를 다시 꽂아야 한다면 전원을 완전히 끈 뒤 작업한다.

근거: [제조사 기본 터치 설정](https://github.com/goodtft/LCD-show/blob/master/LCD5-show), [현재 계열 커널의 공식 ADS7846 오버레이](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/overlays/ads7846-overlay.dts).

파이 서버는 `http://127.0.0.1:8765`, LCD 화면은 `/phone`을 사용한다. `bmo.service` 사용자 서비스를 활성화했고 `~/.config/autostart/bmo-kiosk.desktop`이 `start-pi-kiosk.sh`를 실행하도록 설정했다. 별도 BMO Chromium 프로필(`~/.local/share/bmo/chromium`)에서 키링·번역 초기 창을 정리했고, 한국어 Noto Sans CJK KR 글꼴과 라이선스를 사용자 폴더에 설치했다. BMO 프로필의 비밀번호 저장은 끄고 키링 없는 저장소 옵션을 사용하므로 개인 웹사이트 로그인에는 이 전용 프로필을 사용하지 않는다. 일반 브라우저 프로필은 변경하지 않았다. 실제 화면 기록은 PC `test-results/bmo-lcd-kiosk.png`다.

PC 관리자는 **http://127.0.0.1:8775/admin**이며 무선 SSH 터널을 열어 두었다. 창이 닫히거나 PC 재시작으로 터널이 종료되면 `./connect-pi.ps1 -PiHost 11.135.148.117`로 다시 연다. DHCP 주소가 달라지면 먼저 `hostname -I`로 확인한다. LCD의 로컬 BMO 서버와 화면은 PC 터널과 독립적이다. USB 음성 장치가 인식되지 않아 실제 녹음·재생·실시간 대화는 이번 설치에서 시험하지 않았으며, 자동 시험으로 유료 AI를 호출하지 않았다.

글꼴 근거: [공식 Noto CJK 배포](https://github.com/notofonts/noto-cjk), [SIL Open Font License](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE). 키링 옵션 근거: [Chromium Linux password storage](https://chromium.googlesource.com/chromium/src/+/134.0.6998.35/docs/linux/password_storage.md).

## 구성

| 역할 | 사용할 장치·소프트웨어 |
| --- | --- |
| 화면과 얼굴 | MPI5008에서 기존 `/phone` 웹 화면 표시 |
| 웹 화면 실행 | 라즈베리파이 5의 Chromium, 최종적으로 전체 화면 자동 실행 |
| 사용자 음성 입력 | USB 마이크 JBC-055, 파이 인식·녹음 확인 필요 |
| BMO 음성 출력 | 파이에 연결한 USB 디지털 오디오 스피커 |
| 주변 이미지 | 기존 Camera V2.1 / IMX219, CAM/DISP 0 |
| AI 연결 | 기존 BMO 서버·클라우드 API 유지 |
| 초기 관리자 | PC의 기존 `/admin` 유지 |

파이의 브라우저가 이전 휴대폰 브라우저의 역할을 맡는다. 얼굴·대화·음성 재생·실시간 연결 코드는 재사용한다. 원작자의 Ollama·Whisper.cpp·Piper 설치는 이 방향의 필수 작업이 아니다. 기존 얼굴 이미지와 카메라 설정도 보존한다.

현재는 서버와 Chromium을 파이에서 함께 실행한다. 로컬 `127.0.0.1` 화면은 브라우저의 마이크 사용이 가능한 루프백 출처이며 PC의 HTTPS 인증서에 의존하지 않는다. WebRTC 오디오는 브라우저에서 외부 서비스로 연결하므로 파이 자체의 인터넷 접속이 필요하다. 파이에서 웹 서버를 실행하는 것은 로컬 AI 모델을 돌리는 것과 다른 개념이다. 이전 PC 서버는 별도 시험 구성으로 남아 있다.

## MPI5008에서 확인한 사항

- 5인치, **800×480**, HDMI 영상 입력, 저항막 터치.
- USB 단자는 공식 하드웨어 설명상 **5V 전원 입력**이다. 터치 신호는 26핀 GPIO 연결을 사용하므로 USB 터치 화면으로 가정하지 않는다.
- Pi 5 영상 연결에는 Pi 쪽 micro-HDMI와 LCD 쪽 HDMI에 맞는 케이블이 필요하다. 영상 출력과 GPIO 터치 설정은 나누어 확인한다.
- 공식 사양에서 스피커·마이크 내장 기능은 확인되지 않아, 음성 입출력은 별도 USB 장치로 구성한다.
- 기판 외곽 크기 약 **121.11×77.93mm**. 원본 케이스에 장착할 때 화면 대각선 크기 외에 기판·나사 위치·커넥터와 케이블 공간도 확인한다.

근거: [MPI5008 제품 문서](https://www.lcdwiki.com/5inch_HDMI_Display), [제품 매뉴얼](https://www.lcdwiki.com/res/MPI5008/5inch_HDMI_Display_User_Manual%28EN%29.pdf).

## 음성 부품 선택 기준

추천 후보는 [Adafruit Mini External USB Stereo Speaker, 제품 3369](https://www.adafruit.com/product/3369)다. 제조사 안내상 USB만으로 전원·오디오를 전달하고 Raspberry Pi에 사용할 수 있다. 외곽 크기는 84×43×32mm이며 케이블 공간까지 본체에 들어가는지 확인한다. 실제 보유 파이에서의 동작·대화 음질과 JBC-055와 함께 사용할 때의 에코는 아직 검증하지 않았다. 국내 판매처 예시는 [아이씨뱅큐](https://www.icbanq.com/P013153584), [로봇사이언스몰](https://robotscience.kr/goods/view?no=10476)이며 가격·재고는 주문 시 확인한다.

- USB 마이크는 Linux/Raspberry Pi OS에서 녹음 장치로 인식되는 제품을 선택한다.
- 스피커는 **USB로 전원과 오디오를 함께 받는 제품**인지 확인한다. USB 전원 + 3.5mm 오디오 입력 제품은 별도 USB 오디오 어댑터가 필요할 수 있다. Pi 5에는 3.5mm 아날로그 오디오 출력이 없다.
- 마이크·스피커 통합형 USB 스피커폰도 대안이다. 본체 내부 크기와 Linux 지원, 에코 제거 지원을 확인한다.
- 연결 후 운영체제의 기본 입력·출력 장치와 Chromium 마이크 권한·재생을 확인한다. USB 장치를 연결했다고 기존 웹앱에서 실제 녹음·재생까지 검증된 것은 아니다.

근거: [라즈베리파이 공식 오디오 안내](https://pip-assets.raspberrypi.com/categories/1259-audio-camera-and-display/documents/RP-008124-WP-1-Choosing%20an%20Audio%20option.pdf). 원작자의 [be-more-agent 저장소](https://github.com/brenpoly/be-more-agent)에도 USB 마이크·스피커가 요구 장치로 적혀 있다. 영상 자체의 재생은 이 환경에서 확인하지 못했으며 원작자의 공개 저장소를 참고했다.

## 다음 순서

1. USB 마이크·스피커를 연결하고 장치 인식·자체 녹음·재생 확인.
2. LCD의 소리 켜기·마이크 권한 확인 후 기존 대화와 실시간 음성 시험.
3. 랜선 분리와 재부팅 후 무선 재접속·화면 자동 실행 시험.
4. 케이스 장착·배선 공간과 필요한 경우 터치 좌표 보정.
5. 파이 카메라 연속 프레임 연결 진행. 파이의 연속 프레임 공급 기능은 아직 미구현이다.

브라우저 자동 실행 근거: [라즈베리파이 키오스크 안내](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/).
