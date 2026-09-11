# 국내 여행 추천 리포트 생성기 (travel_planner)

날짜 하나를 넣으면 **LLM + 지도 API**를 이어 붙여 국내 여행 리포트를 만들어 주는 CLI 프로그램입니다.

```
날짜 입력 → ① Gemini에게 추천 도시·날씨·행사를 JSON으로 요청
         → ② 그 도시로 Kakao Local에서 맛집 검색
         → ③ 둘을 합쳐 Gemini에게 Markdown 리포트 작성 요청
         → results/ 에 원본 JSON + 리포트 저장
```

핵심은 **LLM의 출력을 JSON으로 구조화해서 다음 단계(장소 검색)의 입력으로 넘기는 흐름**입니다.

---

## 프로그램 개요

| 항목 | 내용 |
| --- | --- |
| LLM API | Google Gemini (`generateContent`) |
| 지도/장소 API | Kakao Local 키워드 검색 |
| HTTP 클라이언트 | `requests` (벤더 SDK 없이 REST 직접 호출) |
| 결과물 | `results/<날짜>_raw.json`, `results/<날짜>_travel_plan.md` |

SDK 대신 `requests`를 쓴 이유는 요청이 어떻게 만들어지는지 코드에 그대로 드러나기 때문입니다.
두 API가 서로 다른 메서드를 쓰는 것도 비교해서 볼 수 있습니다.

| | Gemini | Kakao Local |
| --- | --- | --- |
| 메서드 | **POST** | **GET** |
| 보낼 내용 | 요청 **본문(body)** 에 JSON | 주소 뒤 **쿼리스트링** 에 조건 |
| 인증 헤더 | `x-goog-api-key: <키>` | `Authorization: KakaoAK <키>` |
| 왜 이 메서드인가 | 프롬프트가 길고 구조가 있어 URL에 담기 어렵다 | "무엇을 달라"는 단순 조회다 |

---

## 실행 방법

### 1. 가상환경 만들고 패키지 설치

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> macOS에서 Homebrew 파이썬을 쓰면 전역 `pip install`이 막혀 있습니다(PEP 668).
> 위처럼 가상환경을 만들어야 설치됩니다.

### 2. API 키 설정 (아래 "API 키 설정 방법" 참고)

### 3. 실행

```bash
python travel_planner.py --date "2026-03-15"
```

출력 예시:

```
[1/3] 1차 추천 생성 중(LLM)...
      - recommended_city: "제주"
[2/3] 맛집 검색 중(지도/장소 API)...
      - 제주: 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
      - 리포트 생성 완료

완료! results/2026-03-15_travel_plan.md 를 확인하세요.
      원본 데이터는 results/2026-03-15_raw.json 에 있습니다.
```

### 옵션

| 옵션 | 설명 |
| --- | --- |
| `--date "YYYY-MM-DD"` | **필수.** 여행 날짜. `-date` 로 써도 됩니다. |
| `--cities {1,2,3}` | 추천받을 도시 수 (보너스, 기본 1) |
| `--places N` | 도시당 검색할 맛집 수 (기본 5) |
| `--refresh` | 캐시를 무시하고 API를 다시 호출 |
| `--list-models` | 쓸 수 있는 Gemini 모델 목록만 출력하고 종료 |
| `--check-keys` | 두 키가 실제로 동작하는지 점검하고 종료 |

날짜 형식이 틀리면 사용법을 출력하고 종료합니다.

```bash
$ python travel_planner.py --date "2026-13-99"
usage: travel_planner.py [-h] -date YYYY-MM-DD [--cities {1,2,3}] ...
travel_planner.py: error: argument -date/--date: 날짜 형식이 올바르지 않습니다: '2026-13-99' (예: 2026-03-15)
```

---

## API 키 설정 방법

### 키 발급받기

| 키 | 발급처 | 경로 |
| --- | --- | --- |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Get API key → Create API key |
| `KAKAO_REST_API_KEY` | [카카오 개발자센터](https://developers.kakao.com) | 내 애플리케이션 → 앱 키 → **REST API 키** |

키가 제대로 들어갔는지는 아래 명령으로 바로 확인할 수 있습니다.

```bash
python travel_planner.py --check-keys
```

```
[Kakao] REST API 키 점검
   형태: 32자, 앞 4자 'a1b2…'
   ✓ 정상 (테스트 검색 1건)

[Gemini] API 키 점검
   형태: 39자, 앞 4자 'AIza…'
   ✓ 키 정상 (목록에 모델 40개)
   ✓ 모델 'gemini-3.6-flash' 로 생성 성공

모두 정상입니다. 이제 --date 로 실행하세요.
```

키 값 자체는 출력하지 않고 길이와 앞 4자만 보여 줍니다.

**자주 막히는 지점**

| 증상 | 원인 |
| --- | --- |
| Kakao 401 | `REST API 키`가 아닌 다른 키를 넣었거나 값이 잘림 |
| Kakao 401 | `KakaoAK ` 접두어까지 같이 복사함 — 키 값만 넣어야 합니다 |
| Kakao 403 | 앱 설정 → 플랫폼 에 Web 플랫폼 추가 필요 |
| Gemini 400 | 키가 유효하지 않음 (Gemini는 401이 아니라 400으로 답합니다) |
| Gemini 404 | 모델이 단종됨 — 응답 메시지가 대체 모델 이름을 알려 줍니다 |
| Gemini 503 | 일시적 혼잡 — 5초 뒤 자동으로 1회 재시도합니다 |

> **모델 목록에 있다고 다 쓸 수 있는 건 아닙니다.**
> 단종된 모델은 `--list-models` 에는 계속 보이지만 실제 생성 요청에서 404가 납니다.
> 그래서 `--check-keys` 는 목록만 보지 않고 실제로 한 번 생성해 봅니다.

### 방법 1 — `.env` 파일 (권장)

```bash
cp .env.example .env
```

그 다음 `.env` 를 열어 값을 채웁니다.

```
GEMINI_API_KEY=발급받은_키
KAKAO_REST_API_KEY=발급받은_키
GEMINI_MODEL=            # 비워 두면 gemini-3.6-flash
```

`.env` 는 `.gitignore` 맨 위에 등록되어 있어 **커밋되지 않습니다.**

### 방법 2 — 환경변수 (현재 터미널 세션에만 적용)

macOS / Linux:

```bash
export GEMINI_API_KEY="YOUR_KEY"
export KAKAO_REST_API_KEY="YOUR_KEY"
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
$env:KAKAO_REST_API_KEY="YOUR_KEY"
```

### 키가 없으면

프로그램이 **API를 호출하기 전에 즉시 종료**하고 설정 방법을 안내합니다. (종료 코드 1)

```
[설정 오류] 다음 API 키가 설정되어 있지 않습니다: GEMINI_API_KEY, KAKAO_REST_API_KEY

설정 방법 (둘 중 하나)
  1) .env 파일 사용 (권장)
  ...
```

---

## ⚠️ 키 유출 주의 사항

API 키는 **비밀번호와 같습니다.** 아래는 반드시 지켜 주세요.

**하지 말아야 할 것**

- 코드에 키를 직접 적기 — `KEY = "AIza..."` 같은 줄을 만들지 마세요.
- README, 보고서, 스크린샷에 키를 붙여 넣기 — 화면 캡처 전에 터미널에 키가 찍혀 있지 않은지 확인하세요.
- `.env` 를 커밋하기 — 이 저장소는 `.gitignore` 로 막아 두었지만, 습관이 더 중요합니다.
- 키가 담긴 파일을 메신저나 이메일로 보내기.

**왜 중요한가**

1. **공유 사고 방지** — 저장소를 공개하거나 협업자를 추가하는 순간 키도 같이 넘어갑니다.
2. **교체가 쉬워짐** — 키가 새면 발급처에서 폐기하고 새로 발급받으면 되고, `.env` 값만 바꾸면 코드는 손댈 필요가 없습니다.
3. **과금/쿼터 사고 예방** — 유출된 키로 남이 호출하면 내 쿼터가 소진되고, 유료 서비스면 요금이 청구됩니다.

**이미 커밋했다면** — 커밋을 되돌리는 것만으로는 부족합니다. Git 기록에 남아 있으므로
**발급처에서 그 키를 폐기하고 새로 발급받는 것이 유일한 해결책**입니다.

---

## 결과물 확인 방법

실행하면 `results/` 폴더에 파일 두 개가 생깁니다.

```
results/
├── 2026-03-15_raw.json          원본 데이터
└── 2026-03-15_travel_plan.md    최종 리포트
```

### `_raw.json` — 원본 데이터

```json
{
  "date": "2026-03-15",
  "generated_at": "2026-03-15T14:02:11",
  "recommendation": {
    "recommended_city": "제주",
    "weather": "3월 중순 평균 15°C 내외, 바람이 있으나 비교적 온화함",
    "events": ["유채꽃 관련 지역 행사"],
    "reason": "3월 중순은 제주가 봄꽃을 즐기기 좋은 시기입니다. ..."
  },
  "places_by_city": {
    "제주": [
      {
        "name": "○○식당",
        "address": "제주시 ...",
        "category": "음식점 > 한식",
        "url": "http://place.map.kakao.com/...",
        "phone": "064-...",
        "x": 126.52,
        "y": 33.50
      }
    ]
  },
  "errors": []
}
```

- `recommendation` — 1차 추천 JSON을 파싱한 결과
- `places_by_city` — 도시별 맛집 목록 (0건일 수 있음)
- `errors` — 처리 중 발생한 오류 요약 (없으면 빈 배열)

### `_travel_plan.md` — 최종 리포트

```
# 2026-03-15 국내 여행 추천 리포트
## 추천 지역
## 추천 이유
## 날씨 요약
## 행사·축제
## 맛집 추천
## 1일 일정 제안
## 오류 요약(errors)
```

터미널에서 바로 보려면:

```bash
cat results/2026-03-15_travel_plan.md
```

---

## 에러 처리 정책

미션 요구에 맞춰 상황별로 다르게 대응합니다.

| 상황 | 동작 | `errors` 에 남는 type |
| --- | --- | --- |
| API 키 미설정 | **즉시 종료** + 설정 방법 안내 | (호출 전이라 없음) |
| 장소 API 인증 실패 (401/403) | 맛집 = 데이터 없음, **리포트는 계속 생성** | `AUTH_ERROR` |
| 장소 API 쿼터 초과 (429) | 위와 같음 | `QUOTA_ERROR` |
| 장소 API 네트워크 오류 | 위와 같음 | `NETWORK_ERROR` |
| 검색 결과 0건 | 위와 같음 | `EMPTY_RESULT` |
| LLM JSON 파싱/검증 실패 | 형식만 강조한 프롬프트로 **1회만** 재요청 | `PARSE_ERROR` / `SCHEMA_ERROR` |
| 재요청도 실패 | 추천 없이는 진행 불가하므로 종료 | 위와 같음 |
| 리포트 생성 실패 | 수집한 자료로 **대체 리포트**를 직접 작성 | `GENERATION_ERROR` |
| LLM 서버 혼잡 (503) | 5초 뒤 **1회** 자동 재시도 | (성공하면 남지 않음) |

무한 재시도는 하지 않습니다. LLM 재요청은 **최대 1회**로 못 박혀 있습니다.

---

## 코드 구조

| 구간 | 함수 |
| --- | --- |
| CLI | `parse_args()`, `valid_date()` |
| 키 관리 | `load_keys()` |
| LLM (POST) | `call_gemini()`, `list_models()`, `extract_json()` |
| 1차 추천 | `build_recommend_prompt()`, `validate_recommendation()`, `get_recommendation()` |
| 장소 (GET) | `search_restaurants()`, `normalize_place()`, `to_float()` |
| 리포트 | `build_report_prompt()`, `generate_report()`, `fallback_report()`, `append_errors_section()` |
| 저장/캐시 | `result_paths()`, `load_cache()`, `save_results()` |
| 흐름 | `pick_cities()`, `main()` |

---

## 개발 환경

- Python 3.12.4 (3.10 이상 필요)
- requests 2.34
- python-dotenv 1.x
- Gemini 모델: `gemini-3.6-flash` (기본값, `.env`의 `GEMINI_MODEL`로 변경 가능)

타임아웃은 호출 성격에 따라 다르게 잡았습니다.
장소 검색·모델 목록은 30초, 리포트 생성은 120초입니다.
도시 3개짜리 리포트는 30초로는 모자라 실제로 타임아웃이 났습니다.
