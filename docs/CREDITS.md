# 사진 출처와 참고 자료

## 작성 근거

개인 보고서는 개발자 최승빈의 설명, 기존 수행평가 보고서의 최종 수정본, BMO 구현 소스, 버전 목록 및 검증 기록을 함께 참고했다. 제작 동기와 인두기를 이용한 공간 확보 경험은 개발자가 직접 제공한 설명을 반영했다. 따로 말하지 않은 감정이나 경험을 새로 만들어 넣지 않았다.

AI 도구는 코드 작성·수정, 오류 분석, 설정 지원, 자동 검사와 문서 편집에 활용했다. 개발자의 역할은 목표와 우선순위 결정, 기구 설계·출력·도색·조립·배선·가공, 실제 장치 확인과 피드백이다.

## 사진과 코드 이미지

`assets/photos/`는 제공된 보고서의 그림 15개에서 추출한 공개 문서용 사본이다. 원본 보고서는 수정하지 않았다. 일부는 원본 Word의 표시 영역을 따라 자르고, 긴 변을 최대 1600픽셀로 축소했으며 EXIF 없이 저장했다. `bmo-front-back.jpg`는 제공된 완성본 전·후면 사진 두 장만 나란히 배치한 이미지다.

사진의 의미는 다음과 같이 구분한다.

- `initial-front`, `initial-side`, `initial-layout`: 초기 설계 구상. 이동부는 최종 구현 범위에 포함되지 않는다.
- `reference-bmo`: 원본 보고서의 외형 참고 이미지. 직접 제작한 완성본 사진으로 사용하지 않았다. 기존 문서에는 Aguilar Workshop 케이스 참고가 기록되어 있으나 이 이미지의 개별 원출처는 확정하지 않았다.
- `fusion-design`, `slicer`, `printing`, `painting`, `assembly`: 제공된 설계·제작·조립 기록.
- `early-phone-ui`, `lcd-test`: 당시 웹 화면과 LCD 시험 기록. 최신 노을 화면을 보여 주는 자료와 구분한다.
- `original-face-sheet`, `original-code-capture`: 기존 보고서의 표정 목록·코드 캡처를 보존한 자료. 현재 동작 설명은 새로 만든 24장 후보 목록과 실제 소스 발췌를 기준으로 한다.
- `bmo-front`, `bmo-back`: 제공된 최종 시제품 전·후면 사진.

인두 가공 순간을 별도로 촬영한 사진은 없으므로, 조립 사진을 해당 작업의 촬영 증거로 설명하지 않았다.

새 코드 이미지는 설치된 **CodeSnap 1.3.4의 webview 렌더러와 PNG 내보내기 기능**을 이용해 만들었다. 격리된 브라우저에서 VS Code API 저장 연결을 대체하고 실제 소스를 HTML로 전달했다. 원본 줄 번호와 소스 파일 SHA-256은 [code-sources.json](code-sources.json)에 기록했다. 최소 공통 들여쓰기는 표시를 위해 제거했으며, 복사 가능한 발췌 파일은 원래 들여쓰기를 보존했다. 발췌는 함수 전체가 아닐 수 있다.

CodeSnap: [프로젝트 저장소](https://github.com/kufii/CodeSnap), adpyke, MIT. 이 문서 패키지에 확장 프로그램 코드를 재배포한 것은 아니다. 표정 이미지와 참고 케이스 등 외부 자료의 라이선스를 프로젝트 전체에 임의로 적용하지 않았다. 원형 BMO 캐릭터와 외부 에셋을 본 프로젝트의 독자 창작물로 주장하지 않는다.

## 외부 참고 자료

- [프로젝트 원형 영상](https://www.youtube.com/watch?v=l5ggH-YhuAw) — 제작 계기로 개발자가 제시한 영상. 외형과 개인 AI 비서 방향을 참고했으며, 이 프로젝트는 브라우저·외부 API 방식으로 개발했다.
- [Raspberry Pi 카메라 문서](https://www.raspberrypi.com/documentation/computers/camera_software.html) — 카메라 소프트웨어 확인 자료.
- [Picamera2 설명서](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) — 6.4.1의 촬영 요청 시점과 flush 동작 참고.
- [LCDWiki MPI5008](https://www.lcdwiki.com/5inch_HDMI_Display) — 화면 규격 및 HDMI·USB 전원·GPIO 터치 설명.
- [GPT-Live 1 모델](https://developers.openai.com/api/docs/models/gpt-live-1) — 음성 모델 설명.
- [GPT-Live 세션과 음성](https://developers.openai.com/api/docs/guides/live-conversations) — Noeul 설정 확인.
- [GPT-Live 위임과 이미지 분석](https://developers.openai.com/api/docs/guides/live-delegation) — 별도 백엔드 분석과 결과 전달 구조.

외부 기술 문서는 2026년 10월 22일 확인한 내용을 기준으로 작성했다. 모델 이용 조건과 API는 달라질 수 있으므로 재현할 때 해당 공식 문서를 확인한다.
