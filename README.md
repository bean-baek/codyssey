# AI 생성 플랫폼 관심도 트렌드 분석 (a2-1)

미션 **"AI 데이터 분석, 데이터 기반 트렌드 분석"** 결과물입니다. 미션 원문 요약은 [docs/mission.md](docs/mission.md)에 있습니다.

AI 이미지·영상 생성 플랫폼 8종(Midjourney, Stable Diffusion, DALL-E, Flux / Sora, Runway, Kling, Veo)을 다룹니다.
각 플랫폼의 **영어 위키백과 일별 조회수**(2022-01-01 ~ 2026-11-19, 8,707개 데이터 포인트)로 관심이 어디로 움직이는지 분석했습니다.

👉 **분석 리포트: [REPORT.md](REPORT.md)**

| 결과물 | 위치 |
| --- | --- |
| 분석 리포트 (질문 5개, 인사이트 4개 + 보너스 2개, 한계점, AI 사용 로그) | [REPORT.md](REPORT.md) |
| 시각화 7장 | [figures/](figures/) |
| 수집 스크립트 | [src/collect.py](src/collect.py) |
| 정제·분석 스크립트 | [src/analyze.py](src/analyze.py), [src/analysis.py](src/analysis.py) |
| 테스트 | [tests/test_analysis.py](tests/test_analysis.py) |
| 원본 데이터 / 정제 데이터 | [data/raw/pageviews.csv](data/raw/pageviews.csv), [data/processed/daily_wide.csv](data/processed/daily_wide.csv) |
| 리포트 수치의 출처 | [results/stats.json](results/stats.json) |
| 보너스: 웹 대시보드 | [dashboard/](dashboard/) |

## 실행 방법

Python 3.10 이상이 필요합니다(3.12.4에서 검증).

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python src/collect.py --end 20261119   # 1) 데이터 수집 → data/raw/pageviews.csv
python src/analyze.py                  # 2) 정제·분석 → figures/*.png, results/stats.json, dashboard/data.json
python -m pytest -q                    # 3) 테스트 (8개)
```

- `collect.py`는 API 키가 필요 없습니다. `--end`를 빼면 어제 날짜까지 받습니다. 그러면 리포트의 숫자와 달라집니다.
- 저장소에 수집된 CSV가 이미 들어 있으므로 1)을 건너뛰고 2)부터 실행해도 됩니다.

## 대시보드 (보너스)

```bash
python src/analyze.py                  # dashboard/data.json 생성 (이미 있으면 생략)
python -m http.server 8765 -d dashboard
# 브라우저에서 http://localhost:8765
```

- 기간(직접 입력 / 90일·1년·2년·전체), 플랫폼 켜고 끄기, 이동평균(없음·7일·28일), 세로축(로그·선형·이미지/영상 비중)을 바꿀 수 있습니다.
- 아래 표에는 선택한 기간의 하루 평균, 최댓값, 첫 30일 → 마지막 30일 변화, 스파이크 일수가 함께 바뀌어 나옵니다.
- 다크 모드 버튼(🌓)이 있고, 모바일 폭에서도 볼 수 있습니다.
- `index.html`을 파일로 바로 열면(`file://`) 브라우저가 `data.json` 읽기를 막습니다. 꼭 위처럼 서버로 열어 주세요.
- 스크린샷과 조작 시나리오는 [REPORT.md 부록](REPORT.md#부록-보너스--대시보드)에 있습니다.

## 프로젝트 구조

```
.
├── REPORT.md                 분석 리포트
├── docs/mission.md           미션 요구사항 요약
├── src/
│   ├── collect.py            Wikimedia Pageviews API → data/raw/pageviews.csv
│   ├── analysis.py           정제·이상치·요일지수·변화율 순수 함수 (테스트 대상)
│   └── analyze.py            정제 → 분석 → 그래프 7장 + stats.json + 대시보드 데이터
├── tests/test_analysis.py    결측·이상치 처리 규칙 테스트
├── data/raw/                 API 원본 (long 형식)
├── data/processed/           정제 후 (날짜 × 플랫폼)
├── figures/                  리포트용 그래프
├── results/stats.json        리포트의 모든 수치
├── dashboard/                보너스 대시보드 (index.html + data.json)
└── screenshots/              대시보드 화면
```

## 데이터 출처와 라이선스

- **출처:** [Wikimedia Analytics API — Pageviews](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/), 영어 위키백과, `agent=user`(자동화 트래픽 제외)
- **라이선스:** Wikimedia 조회수 데이터는 [CC0](https://creativecommons.org/publicdomain/zero/1.0/)로 공개됩니다. 위키백과 **문서 본문**은 CC BY-SA지만, 이 프로젝트는 본문을 쓰지 않고 조회수만 씁니다.
- **이용 시 주의:** Wikimedia API 정책에 따라 요청에 프로젝트를 식별할 수 있는 `User-Agent`를 붙였습니다. 요청 사이에는 0.3초 간격을 뒀습니다.
- 조회수는 "관심"의 대리 지표일 뿐, 실제 사용자 수나 품질이 아닙니다. 자세한 한계는 [REPORT.md 5장](REPORT.md#5-한계점)에 있습니다.

## 다음 미션

`a2-2` 브랜치에서 **AI Agent 개발 미션**(FastAPI + Firestore + GPT, Render/Vercel 배포)을 진행합니다.
이 분석의 요약 지표(기간, 개수, 평균·최대·최소, 최근 추세)가 그 미션의 `/api/data/summary`로 이어질 예정입니다.
