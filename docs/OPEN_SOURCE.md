# 오픈소스 검토

2026-10-26에 아래 GitHub 프로젝트 페이지의 HTTP 200 응답을 확인했습니다.
GitHub API는 환경 프록시에서 403으로 차단되어 최근 커밋 날짜/유지보수 주기를 확인하지 못했습니다.

| 프로젝트 | 용도와 선택 |
|---|---|
| https://github.com/opencv/opencv | 영상 처리, 채택. Apache-2.0 |
| https://github.com/BoboTiG/python-mss | 캡처, 채택. MIT |
| https://github.com/learncodebygaming/pydirectinput | 입력 참고 후보. MIT. 구현은 Windows SendInput 직접 사용 |
| https://github.com/ultralytics/ultralytics | YOLO 후보. AGPL-3.0/상용 라이선스 고려 필요. 게임 전용 가중치가 없어 미채택 |
| https://github.com/Farama-Foundation/Gymnasium | 시뮬레이션/RL 후보. MIT. 실제 게임 상태/보상 제공 환경이 없어 미채택 |
| https://github.com/RapidAI/RapidOCR | ONNX 기반 메뉴 OCR, 채택. Apache-2.0. 번들 모델의 한국어 인식은 보장하지 않음 |

라이브러리 설치물에는 각 라이선스가 포함됩니다. 재배포 시 라이브러리/모델별 고지 의무를 확인해야 합니다.
쿠키런 전용 공개 이미지나 학습 모델을 확보하지 않았고, 게임 에셋을 배포하거나 학습에 사용하지 않았습니다.
