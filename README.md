# 결 — 초고를 다시 쓰지 않는 퇴고 도구

완성한 초고에서 **고칠 지점만 문장 단위로 짚어 주는** 한국어 퇴고 웹 서비스입니다.
AI가 글을 대신 써 주지 않습니다.

**배포 URL**: (배포 후 여기에 기입)

---

## 이 서비스가 하는 일

```
원고 붙여넣기
   → 문장 단위로 분해 (브라우저)
   → Claude가 고칠 문장의 "번호"와 대안·사유를 반환 (POST /api/revise)
   → 서버가 번호로 원문을 채워 돌려줌
   → 사용자가 제안을 하나씩 골라 반영
```

핵심은 **모델에게 원문을 돌려받지 않는다**는 점입니다.
모델은 `index`만 답하고 원문은 서버가 `sentences[index]`에서 채웁니다.
없는 문장을 지어낼 경로가 구조적으로 막혀 있습니다.

### 화면 구성

| 섹션 | 내용 | AI |
| --- | --- | --- |
| 홈 | 서비스 소개와 세 가지 원칙 | — |
| 퇴고 | 원고 입력 → 문장별 제안 카드 + 편집 방침 패널 | `POST /api/revise` |
| 도우미 | 유의어 · 그 단어 뭐였지 · 인상 · 분류 | `POST /api/assist` |
| 설계 | 3층 구조, 환각 차단 방식, 오류 처리 기준 | — |

---

## 기술 스택

| 층 | 사용 기술 |
| --- | --- |
| 프론트엔드 | 순수 HTML / CSS / JavaScript (ES 모듈). 프레임워크·빌드 도구 없음 |
| 백엔드 | Vercel Serverless Functions (Python) — `api/revise.py`, `api/assist.py` |
| AI | Anthropic Claude — 퇴고는 Sonnet, 도우미는 Haiku |
| 배포 | Vercel (GitHub 연동, `a1-3` 브랜치) |

**두 엔드포인트를 나눈 이유**는 속도입니다. 퇴고는 문맥 판단과 사유 서술이 필요해
느려도 되지만 도우미는 빨라야 합니다. 모델·토큰 상한·타임아웃을 다르게 잡고
경로를 분리해, 잦은 호출이 비싼 경로로 새지 않게 했습니다.

```
index.html              4개 섹션
css/style.css
js/
  core/ai.js            모든 AI 호출의 단일 창구 (타임아웃·재시도·연타 방지·오류 문구)
  core/sentences.js     문장 분해 (offset 포함)
  core/nav.js           해시 라우팅
  core/store.js         편집 방침 보관
  ui/editor.js          퇴고 화면
  ui/assist.js          도우미 화면
  ui/persona.js         편집 방침 패널
  app.js
api/
  revise.py             POST /api/revise
  assist.py             POST /api/assist
AGENTS.md               엔진 설계 문서 (프롬프트·스키마·검증 규칙의 근거)
docs/기획서.md
tests/sentences.test.mjs
```

프론트에서 `fetch`를 직접 쓰는 곳은 `js/core/ai.js` 하나뿐입니다.
화면 모듈은 `revise()` / `assist()`만 부르므로, 화면이 늘어도 실패 처리 코드는 늘지 않습니다.

---

## 환경 변수 설정

이 서비스는 **`ANTHROPIC_API_KEY` 하나**만 필요합니다.

### 키 발급

[console.anthropic.com](https://console.anthropic.com/settings/keys) → **Create Key**

### 로컬

```bash
cp .env.example .env
```

`.env`를 열어 값을 채웁니다.

```
ANTHROPIC_API_KEY=발급받은_키
```

`.env`는 `.gitignore` 맨 위에 등록되어 있어 커밋되지 않습니다.

### Vercel

프로젝트 → **Settings → Environment Variables** →
Name `ANTHROPIC_API_KEY`, Value에 키를 붙여 넣고 Production·Preview·Development 모두 체크합니다.
**추가한 뒤에는 재배포해야 적용됩니다.**

키가 없으면 API가 호출 전에 500 `UPSTREAM_ERROR`를 돌려주고,
화면에는 "잠시 후 다시 시도해 주세요"가 뜹니다.

---

## ⚠️ 키 유출 주의

API 키는 비밀번호와 같습니다. **과금이 걸려 있어 유출되면 요금이 청구됩니다.**

**하지 말아야 할 것**

- 코드에 키를 직접 적기 — `api_key = "sk-ant-..."` 같은 줄을 만들지 않습니다.
- `.env`를 커밋하기 — `.gitignore`로 막아 두었지만 습관이 더 중요합니다.
- README·기획서·**스크린샷**에 키가 보이게 두기 — 터미널 캡처 전에 키가 찍혀 있지 않은지 확인하세요.
- 키를 채팅·메신저·이메일로 보내기.

**이미 커밋했다면** 되돌리는 것만으로는 부족합니다. Git 기록에 남아 있으므로
**콘솔에서 그 키를 폐기하고 새로 발급받는 것이 유일한 해결책**입니다.

**공개 URL이므로 콘솔에서 월 사용 한도(spend limit)를 반드시 설정하세요.**
누구나 접속해 호출할 수 있고, 이것이 마지막 안전장치입니다.

---

## 실행 방법

### 1. 의존성

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 로컬 실행

AI 기능까지 확인하려면 `api/`를 함께 띄우는 `vercel dev`를 씁니다.

```bash
npx vercel dev
```

화면만 볼 때는 정적 서버로도 되지만 `/api/*`가 동작하지 않습니다.

```bash
python3 -m http.server 8899
```

### 3. 테스트

```bash
node tests/sentences.test.mjs
```

문장 분해와 제안 반영 로직을 검사합니다. 브라우저 없이 실행됩니다.

---

## 배포 방법

1. GitHub에 푸시합니다 (이 프로젝트는 `a1-3` 브랜치).
2. [vercel.com](https://vercel.com) → **Add New → Project** → 저장소를 선택합니다.
3. **Settings → Git → Production Branch**를 `a1-3`으로 지정합니다.
4. **Settings → Environment Variables**에 `ANTHROPIC_API_KEY`를 등록합니다.
5. 재배포 후 배포 URL에서 네비게이션·반응형·AI 기능을 확인합니다.

빌드 설정은 건드릴 것이 없습니다. 정적 파일은 루트에서 그대로 서빙되고,
`api/*.py`는 `requirements.txt`를 보고 Python 함수로 자동 인식됩니다.

`vercel.json`은 함수 실행 시간만 늘려 둡니다. 퇴고는 서버 타임아웃이 25초인데
플랫폼 기본 한도가 그보다 짧으면 모델이 답하기 전에 잘리기 때문입니다.

---

## 알아두면 좋은 것

**모델 ID는 갱신됩니다.** 코드에서는 `MODEL_REVISE` / `MODEL_ASSIST` 상수
한 곳에서만 참조하므로 그 줄만 고치면 됩니다.

**Sonnet 계열은 `temperature`를 받지 않습니다.** 보내면 400입니다.
그래서 퇴고는 `output_config.effort`로 출력 흔들림을 조절하고,
도우미의 Haiku는 `temperature`를 그대로 씁니다. 두 엔드포인트의 설정 항목이
다른 것은 실수가 아니라 모델 세대 차이입니다. 자세한 내용은 `AGENTS.md` 1장에 있습니다.
