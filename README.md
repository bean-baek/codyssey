# AI 관심도 비서 (a2-2)

미션 **"AI Agent 개발 — 내 데이터를 아는 AI 비서"** 결과물입니다. 미션 요약은 [docs/mission-a2-2.md](docs/mission-a2-2.md)에 있습니다.

## 무엇을 해결하나

일반 ChatGPT에게 "요즘 AI 영상 도구 관심이 어때?"라고 물으면 일반론만 돌아옵니다.
이 서비스는 직전 미션(a2-1)에서 모은 **AI 이미지·영상 생성 플랫폼 8종(Midjourney, Stable Diffusion, DALL-E, Flux, Sora, Runway, Kling, Veo)의 영어 위키백과 일별 조회수 합계**를 Firestore에 저장합니다.
그 요약(기간·개수·평균·최대·최소·최근 추세)을 GPT의 시스템 프롬프트에 넣어, **내 데이터를 근거로** 답하게 합니다.

- 데이터: 2025-11-20 ~ 2026-11-19, **365개** 일별 값 `(date, value, memo)`. memo에는 그날 급증한 플랫폼(a2-1의 이상치 규칙)이 들어 있습니다.
- 데이터는 화면에서 추가·수정·삭제할 수 있고, 바꾸는 즉시 요약과 AI 답변에 반영됩니다.

## 배포 URL

| 구분 | 주소 |
| --- | --- |
| 프론트엔드 (Vercel) | _배포 후 기입_ |
| 백엔드 API (Render) | _배포 후 기입_ |
| Swagger UI | _백엔드 주소_ + `/docs` |

> **첫 접속 안내:** Render 무료 티어는 15분간 요청이 없으면 잠듭니다. 첫 요청은 최대 1분 정도 걸립니다.
> 화면은 시작할 때 `/api/health`로 서버를 먼저 깨웁니다. 2.5초 넘게 걸리면 "서버를 깨우는 중" 안내를 띄우고, 요청 제한 시간을 90초로 늘려 둡니다.

## 기술 스택

| 영역 | 사용 |
| --- | --- |
| 백엔드 | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| DB | Firebase Firestore (`firebase-admin`) |
| AI | OpenAI Chat Completions + Function Calling (`openai`) |
| 프론트엔드 | HTML / CSS / JavaScript(ES Modules), 프레임워크·차트 라이브러리 없음 (그래프는 SVG 직접 그림) |
| 배포 | Render(백엔드), Vercel(프론트) |
| 보너스 | MCP Server(`mcp`), 통계 API, 그래프, CSV/JSON 내보내기, 다크 모드 |

## 화면

| 채팅 (요약 + 질문·답변) | 데이터 관리 (수정) | 대화 기록 (불러오기) |
| --- | --- | --- |
| _배포 후 `screenshots/a2-2_chat.png`_ | _`screenshots/a2-2_data.png`_ | _`screenshots/a2-2_history.png`_ |

## 로컬 실행

Python 3.10 이상, Node 18 이상(프론트 설정 파일 생성용)이 필요합니다.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 1) 백엔드
cd backend
cp .env.example .env          # 키를 채운다. 비워 두면 메모리 저장소 + 데모 모드로 뜬다
python -m scripts.seed        # (Firestore를 쓸 때 1회) seed 365일을 data 컬렉션에 적재
uvicorn main:app --reload     # http://localhost:8000/docs
python -m pytest -q           # 테스트 25개 (Firestore·OpenAI 없이 실행)

# 2) 프론트엔드 (새 터미널)
cd frontend
API_BASE_URL=http://localhost:8000 node build.mjs   # public/config.js 생성
python3 -m http.server 5500 -d public               # http://localhost:5500
```

- 키 없이 띄우면 **데모 모드**입니다. 서버를 켤 때마다 seed 365일이 메모리에 올라가고, 채팅은 GPT 대신 주입된 요약을 그대로 보여 줍니다. 화면 오른쪽 위에 "데모 모드: GPT 키 없음"이 표시됩니다.
- 프론트 주소가 5500/3000 포트가 아니면 백엔드 `.env`의 `ALLOWED_ORIGINS`에 추가해야 CORS에 막히지 않습니다.

## 환경 변수

**백엔드 (Render / `backend/.env`)**

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `OPENAI_API_KEY` | ✔ | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✔ | 서비스 계정 키 JSON **내용 전체**(한 줄). 로컬에서는 대신 `FIREBASE_SERVICE_ACCOUNT_PATH`(키 파일 경로)도 가능 |
| `ALLOWED_ORIGINS` | ✔ | CORS 허용 프론트 주소, 쉼표 구분. 예: `https://ai-interest.vercel.app` |
| `OPENAI_MODEL` | | 기본 `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | | 답변 1회 최대 토큰(과금 상한), 기본 600 |
| `CHAT_RATE_PER_MINUTE` / `CHAT_DAILY_LIMIT` | | IP당 분당 채팅 수 / 서버 전체 하루 채팅 수, 기본 10 / 300 |
| `OPENAI_BASE_URL` | | 프록시를 쓸 때만 |

**프론트엔드 (Vercel)**

| 이름 | 설명 |
| --- | --- |
| `API_BASE_URL` | 백엔드 주소. 예: `https://ai-interest-api.onrender.com`. 빌드 때 `build.mjs`가 `public/config.js`로 만든다 |

## 배포 방법

**백엔드 — Render**
1. Render 대시보드에서 **New → Blueprint**를 누르고 이 저장소(`a2-2` 브랜치)를 고릅니다. 루트의 [render.yaml](render.yaml)이 `rootDir: backend`, 빌드·시작 명령, 헬스체크를 지정합니다.
2. 비밀 값 3개(`OPENAI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ALLOWED_ORIGINS`)를 대시보드에서 입력합니다.
3. `https://<서비스>.onrender.com/docs`에서 Swagger를 확인합니다.

**프론트엔드 — Vercel**
1. **Add New → Project**에서 같은 저장소를 고르고 **Root Directory = `frontend`**로 지정합니다. 빌드 설정은 [frontend/vercel.json](frontend/vercel.json)에 있습니다.
2. Environment Variables에 `API_BASE_URL`을 넣고 배포합니다.
3. 받은 Vercel 주소를 Render의 `ALLOWED_ORIGINS`에 넣습니다.

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/data` | 데이터 추가 `{date, value, memo}`. 같은 날짜가 있으면 409 |
| GET | `/api/data` | 목록. `start`, `end`, `order`(asc/desc), `limit` |
| PUT | `/api/data/{id}` | 부분 수정(보낸 필드만) |
| DELETE | `/api/data/{id}` | 삭제 |
| GET | `/api/data/summary` | **요약(프롬프트 주입용)**: 기간, 개수, 합계·평균·중앙값·최대·최소·표준편차, 최근 추세, 최근 6개월 월평균 |
| GET | `/api/data/statistics` | 보너스: 요일별·월별 평균, 변동성, 상위 5일, 7일 이동평균 시계열 |
| GET | `/api/data/export?format=csv\|json` | 보너스: 내보내기 |
| POST | `/api/conversations` | 대화 저장 `{title?, messages:[{role, content}]}` |
| GET | `/api/conversations` | 대화 목록. **messages는 포함하지 않음**(제목·개수·미리보기만) |
| GET | `/api/conversations/{id}` | 특정 대화 불러오기(전체 messages) — 방식 (A) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | `{message, conversation_id?}` → 요약 주입 GPT 답변, 자동 저장 |
| GET | `/api/health` | 상태(저장소 종류, 모델). 콜드스타트 깨우기용 |

요약 응답 예시 (seed 데이터 기준):

```json
{
  "period": "2025-11-20 ~ 2026-11-19",
  "count": 365,
  "metrics": { "total": 1426110, "average": 3907.2, "median": 3674, "std": 1971.1,
               "max": { "value": 31476, "date": "2026-03-25" },
               "min": { "value": 2125,  "date": "2026-08-15" } },
  "trend": { "direction": "유지", "change_pct": -2.0, "label": "유지 (최근 30일 평균 -2.0%, 직전 30일 대비)" },
  "monthly": [ { "month": "2026-06", "average": 3553.0 }, "…" ]
}
```

## 설계 설명

### 프로젝트 구조 — 라우터 / 서비스 / 저장소 분리

```
backend/
├── main.py                 앱 생성, CORS, 예외 처리, 라우터 등록
├── app/
│   ├── config.py           환경 변수 → Settings (키는 여기서만 읽음)
│   ├── schemas.py          Pydantic 요청·응답 모델
│   ├── db.py               Repository 인터페이스 + Firestore / 메모리 구현
│   ├── deps.py             라우터가 쓰는 공용 객체, 요청 제한
│   ├── routers/            data.py · conversations.py · chat.py  — HTTP만 담당
│   └── services/           summary.py · chat.py · tools.py · llm.py — 로직
├── scripts/                build_seed.py(a2-1 → seed CSV) · seed.py(→ Firestore)
├── seed/ai_interest_daily.csv
├── mcp_server.py           보너스: MCP 서버
└── tests/test_api.py
frontend/
├── build.mjs, vercel.json
└── public/  index.html · styles.css · js/{app,api,chart}.js
```

- **라우터**는 "어떤 URL이 어떤 입력을 받아 어떤 상태 코드를 돌려주나"만 압니다. 404·409 판단도 여기서 합니다.
- **서비스**는 HTTP를 모릅니다. 요약 계산, 채팅 흐름, 도구 실행을 맡습니다. 그래서 MCP 서버나 테스트에서도 같은 로직을 그대로 씁니다.
- **저장소(Repository)** 인터페이스를 둔 이유: 라우터·서비스는 Firestore를 직접 부르지 않습니다. 같은 인터페이스의 메모리 구현을 넣으면 키 없이 로컬 실행과 테스트를 할 수 있습니다. 테스트 25개가 Firestore·OpenAI 없이 돕니다.

### Pydantic 입력 검증

잘못된 값은 DB에 닿기 전에 422로 막습니다(`app/schemas.py`).
- `date`는 문자열이 아니라 `date` 타입으로 받습니다. `2026-13-40`은 들어오지 못합니다.
- `value`는 0 이상, 10억 이하, 유한한 수만 받습니다(NaN·무한대 차단).
- `memo`는 200자, 채팅 메시지는 1,000자까지입니다. Firestore 문서(1MB)와 GPT 토큰이 폭주하지 않게 하려는 상한입니다.
- `extra="forbid"`로 오타 필드(`valeu`)를 조용히 무시하지 않고 에러로 알립니다.
- PUT은 보낸 필드만 바꾸고(`exclude_unset`), 아무것도 없으면 422입니다.
- 형식 검증 외의 업무 규칙도 둡니다. 시계열은 하루 1개 값이 전제이므로 같은 날짜를 또 추가하면 409입니다.

### Firestore 컬렉션 구조

```
data/{autoId}           { date: "2026-03-25", value: 31476, memo: "Sora 급증", created_at, updated_at }
conversations/{autoId}  { title, message_count, preview, created_at, updated_at,
                          messages: [ { role: "user"|"assistant", content, created_at, tools: [...] } ] }
```
- `date`를 `YYYY-MM-DD` 문자열로 저장했습니다. 사전순이 곧 날짜순이라 범위 조회(`>=`, `<=`)와 정렬이 별도 인덱스 없이 됩니다.
- 메시지는 대화 문서 안 배열로 넣었습니다. 대화 하나를 불러올 때 읽기 1회로 끝납니다. 대신 문서가 커지지 않게 최근 100개까지만 둡니다.
- 대화 목록 조회는 `select()`로 messages를 빼고 읽습니다. 목록 응답이 가볍습니다.
- **읽기 절약:** 요약은 채팅마다 쓰이므로, 데이터 365건을 메모리에 캐시하고 추가·수정·삭제 때만 버립니다. 캐시가 없으면 채팅 1번에 Firestore 읽기 365회가 듭니다.

### 컨텍스트 주입 — `POST /api/chat`의 흐름

```
사용자 질문
   │
   ▼
① SummaryService.summary()   ← /api/data/summary 와 같은 계산(캐시)
   │
   ▼
② 시스템 프롬프트에 삽입
   "당신은 데이터 분석 비서입니다 … [사용자 데이터 요약]
    - 데이터 기간: 2025-11-20 ~ 2026-11-19
    - 총 레코드: 365개 …  - 최근 트렌드: 유지 (최근 30일 평균 -2.0%) …"
   + 이 대화의 최근 메시지 12개 + 새 질문
   │
   ▼
③ GPT 호출 (tools 포함) ──필요하면──▶ 도구 실행 → 결과를 붙여 다시 호출 (최대 3번)
   │
   ▼
④ 질문 + 답변(+ 호출한 도구 이름)을 conversations 에 자동 저장
   │
   ▼
{ conversation_id, reply, tool_calls[{name, arguments, reason}], summary_period, model }
```

GPT는 학습 데이터만으로는 이 데이터를 모릅니다. 그래서 매 요청의 **시스템 프롬프트에 요약 텍스트를 넣어** 모델이 그 숫자를 "읽고" 답하게 합니다. 모델을 다시 학습시키지 않고, 데이터가 바뀌면 다음 요청부터 바로 반영됩니다. 요약은 365개 원본보다 훨씬 짧아 토큰(=비용)도 적게 듭니다. 원본이 필요한 질문만 도구로 따로 가져옵니다.

### 배포 환경의 CORS · 환경 변수 · 키 관리

- **CORS:** 프론트(Vercel)와 백엔드(Render)는 도메인이 다릅니다. 그래서 브라우저는 백엔드가 허락한 출처의 요청 응답만 읽게 해 줍니다. `ALLOWED_ORIGINS`에 적은 주소만 허용하고 `*`는 쓰지 않습니다. 아무 사이트에서나 내 API를 호출해 GPT 비용을 쓰지 못하게 하려는 것입니다. 테스트로 허용·차단을 확인합니다.
- **환경 변수:** API 키, 서비스 계정 키, 허용 도메인, 프론트가 부를 API 주소는 환경(로컬/배포)마다 다르고, 일부는 비밀입니다. 코드에는 이름만 있고 값은 Render·Vercel 대시보드나 로컬 `.env`에 있습니다. `.env`와 키 파일 패턴은 `.gitignore`에 등록돼 커밋되지 않습니다.
- **키는 백엔드에만:** OpenAI·Firebase 키는 브라우저로 내려가지 않습니다. 프론트가 아는 값은 공개돼도 되는 `API_BASE_URL` 하나입니다.
- **과금 보호:** 답변 최대 토큰(`OPENAI_MAX_TOKENS=600`), 이전 대화는 최근 12개만 전송, IP당 분당 10회, 서버 전체 하루 300회 제한을 둡니다.
- **오류 처리:** GPT 인증 실패·한도 초과·시간 초과는 각각 502/429/504와 한국어 안내로 돌려줍니다. 예상 못 한 오류도 CORS 헤더가 붙은 500 JSON으로 돌려줘서 브라우저가 내용을 읽을 수 있게 했습니다. 실패한 채팅은 저장하지 않습니다.

## 보너스 1 — Function Calling + MCP Server

### 도구와 호출 근거

요약은 항상 시스템 프롬프트에 들어 있습니다. 도구는 **요약만으로 답할 수 없을 때만** 부르도록 description에 적었습니다. 모든 도구는 `reason` 인자를 받아 모델이 "왜 부르는지"를 스스로 적게 합니다. 그 값은 응답의 `tool_calls`와 화면의 도구 칩에 그대로 보입니다.

| 도구 | 언제 부르나 (description 기준) | 예시 질문 |
| --- | --- | --- |
| `get_data_summary` | 요약 원본 JSON이 필요하거나 최신 여부를 확인할 때 | "지금 데이터 몇 개야? 정확히" |
| `get_statistics` | 요일·월별·변동성·상위 일자처럼 요약에 없는 지표 | "무슨 요일에 가장 많이 찾아봐?" |
| `query_data(start, end)` | 기간이 정해진 질문(최대 62일) | "2026년 3월 하순 일별 값을 보여줘" |
| `list_conversations` | "지난번에", "전에 물어본" | "지난번에 내가 뭘 물어봤지?" |
| `get_conversation(id)` | 목록에서 찾은 대화의 내용 | (위 질문의 다음 단계) |

### 호출 흐름

```
[웹 채팅]  사용자 ─▶ POST /api/chat ─▶ ChatService ─▶ GPT ─(tool_calls)─▶ ToolRunner ─▶ SummaryService / Repository
                                                       ◀──── 도구 결과(JSON) ────┘
                                         GPT 최종 답변 ─▶ conversations 저장 ─▶ 화면(답변 + 도구 칩)

[MCP 채널] Claude Desktop/Code ─▶ mcp_server.py(stdio) ─▶ 같은 REST API(/api/data/summary, /api/data …)
```

- 도구가 잘못된 인자(예: `start="어제"`)로 불리면 예외를 내지 않고 `{"error": …}`를 모델에게 돌려줍니다. 모델이 스스로 고치게 하려는 것입니다.
- 도구 루프는 최대 3번입니다. 그 뒤에는 도구 없이 호출해 답을 강제합니다. 둘 다 테스트로 확인했습니다.

### MCP Server

[backend/mcp_server.py](backend/mcp_server.py)는 같은 도구(`get_data_summary`, `get_statistics`, `query_data`, `list_conversations`, `get_conversation`)와 `ask_assistant`(= `/api/chat`)를 MCP로 노출합니다.

```bash
# Claude Code에 등록
claude mcp add ai-interest -e API_BASE_URL=https://<render-app>.onrender.com -- \
  "$PWD/.venv/bin/python" "$PWD/backend/mcp_server.py"
```

검증: MCP 클라이언트(stdio)로 접속해 도구 6개가 목록에 뜨는지 확인했습니다. 이어서 `get_data_summary`가 `count: 365`를, `query_data("2026-03-24","2026-03-26")`가 3건(Sora 급증 메모 포함)을 돌려주는지 확인했습니다.

## 보너스 2 — 인사이트·UX

- **추가 지표:** `/api/data/statistics`가 변동성(일간 변화율 표준편차), 요일별·월별 평균, 상위 5일, 7일 이동평균을 줍니다. 요약에도 중앙값·표준편차·월평균을 더했습니다.
- **그래프:** 화면 상단에 최근 365일 일별 값(로그 축), 7일 평균, 급증 메모가 있는 날을 그립니다. 마우스나 손가락을 대면 그날 값과 메모가 보입니다. 스파이크 하나(3만 회)가 축을 독점하지 않게 로그 축을 썼습니다.
- **내보내기:** 데이터 관리의 CSV / JSON 버튼. CSV에는 BOM을 넣어 엑셀에서 한글 메모가 깨지지 않습니다.
- **다크 모드:** 오른쪽 위 버튼. 선택은 브라우저에 기억되고, 처음에는 OS 설정을 따릅니다.

## 데이터 출처와 라이선스

- [Wikimedia Analytics API — Pageviews](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/), 영어 위키백과, `agent=user`. 조회수 데이터는 [CC0](https://creativecommons.org/publicdomain/zero/1.0/)입니다.
- seed는 `python backend/scripts/build_seed.py`로 a2-1의 `data/processed/daily_wide.csv`에서 다시 만들 수 있습니다.
- 조회수는 관심의 대리 지표일 뿐 실제 사용자 수가 아닙니다.

## 이전 미션 (a2-1) — 트렌드 분석

같은 데이터의 분석 리포트는 [REPORT.md](REPORT.md)에 있습니다(질문 5개, 인사이트 4개, STL 분해·베이스라인 예측, AI 사용 로그).

```bash
pip install -r requirements.txt
python src/collect.py --end 20261119   # 수집 (생략 가능, CSV 포함)
python src/analyze.py                  # 그래프 7장 + results/stats.json + dashboard/data.json
python -m pytest -q                    # a2-1 테스트 8개
python -m http.server 8765 -d dashboard
```

## AI 사용 로그

Claude Code(Claude Opus 5.5)와 함께 만들었습니다.

| 작업 | 사용 내용 | 검증 방법 |
| --- | --- | --- |
| 구조 설계 | 라우터/서비스/저장소 분리, Firestore 컬렉션 구조 제안 | 메모리 저장소로 바꿔 끼워도 라우터 코드가 바뀌지 않는지 테스트로 확인 |
| 백엔드 코드 | FastAPI 라우터, Pydantic 모델, 채팅·도구 루프 작성 | 테스트 25개(검증 422, 중복 409, 캐시 무효화, 도구 왕복, 루프 상한, CORS 허용·차단, 실패 시 미저장) |
| seed 데이터 | a2-1 정제 데이터 → 365일 합계 + 급증 메모 | 최대값 31,476(2026-03-25)이 a2-1 그래프의 Sora 스파이크 날짜와 일치하는지 확인 |
| 프론트엔드 | 바닐라 JS 화면, SVG 그래프 | 브라우저(1440px, 390px, 다크 모드)에서 채팅·추가·수정·삭제·대화 불러오기를 직접 조작 |
| MCP | MCP 서버 작성 | MCP 클라이언트로 접속해 도구 목록과 실제 응답 확인 |
