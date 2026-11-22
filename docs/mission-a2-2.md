# 미션: AI Agent 개발 — 내 데이터를 아는 AI 비서

> 원문: Notion 미션 페이지. 브랜치 `a2-2`에서 수행한다. 직전 미션(트렌드 분석)은 `a2-1` → [mission.md](mission.md)

## 최종 결과물 (4가지 기능)
1. 데이터 기반 AI 채팅: 자연어 질문 → 저장된 데이터 요약을 반영한 답변 + 로딩 표시
2. 데이터 관리(CRUD): (date, value, memo) 추가/수정/삭제 → 목록 갱신·저장 결과 확인
3. 대화 기록 저장·불러오기: 저장, 목록, 특정 대화 메시지 재표시
4. 배포·문서화: 프론트/백엔드 URL, Swagger UI, README(실행·환경변수)

## 기능 요구 사항
1. Python 3.10+, venv, fastapi·uvicorn·firebase-admin·openai·python-dotenv
2. 시계열 100개 이상, 요약(기간·개수·평균/최대/최소·최근 추세)
3. FastAPI + CORS, `/docs`
4. Firestore, 서비스 계정 키는 환경 변수. 컬렉션 `data`, `conversations`
5. `POST/GET /api/data`, `PUT/DELETE /api/data/{id}`, `GET /api/data/summary`
6. `POST/GET /api/conversations`, `DELETE /api/conversations/{id}` + (A) `GET /api/conversations/{id}` 또는 (B) 목록에 messages 포함 여부 명시
7. `POST /api/chat`: 요약 조회 → 시스템 프롬프트 삽입 → GPT 호출 → conversations 자동 저장
8. Render 배포, `/docs` 확인, 콜드스타트 안내
9. 바닐라 HTML/CSS/JS: 채팅(입력·표시·로딩), 데이터 관리(추가·목록·수정/삭제 1개 이상), 대화 기록(목록·불러오기), 요약 표시
10. Vercel 배포(API 주소는 환경 변수), README(소개·스택·URL·로컬 실행·환경 변수), 스크린샷 3장(요약+채팅, 데이터 관리, 대화 불러오기)

## 보너스
- Function Calling + MCP Server 또는 GPT Actions, README에 호출 근거와 흐름
- 통계 지표 추가, 프론트 그래프, CSV/JSON 내보내기, 다크 모드

## 제약
- 백엔드 Render, 프론트 Vercel 고정
- 키는 환경 변수(OPENAI_API_KEY, FIREBASE_SERVICE_ACCOUNT_JSON, API_BASE_URL, ALLOWED_ORIGINS), 입력 검증·예외 처리
- 과금 주의: 요청 횟수·max_tokens 제한
