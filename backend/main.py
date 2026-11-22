"""FastAPI 앱 진입점.  로컬:  cd backend && uvicorn main:app --reload

구성
  main.py            앱 생성, CORS, 예외 처리, 라우터 등록
  app/config.py      환경 변수 → Settings
  app/schemas.py     Pydantic 요청·응답 모델(입력 검증)
  app/db.py          저장소(Firestore / 메모리) — 컬렉션 구조는 여기 주석 참고
  app/services/      비즈니스 로직: 요약 계산, 채팅 흐름, GPT 도구, LLM 클라이언트
  app/routers/       HTTP 경로만 담당(검증된 입력 → 서비스 호출 → 응답)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, load_settings
from app.db import Repository, make_repository
from app.deps import RateLimiter
from app.routers import chat, conversations, data
from app.seed import load_seed_rows
from app.services.chat import ChatService
from app.services.llm import LLMError, make_llm
from app.services.summary import SummaryService

log = logging.getLogger("uvicorn.error")


def create_app(settings: Settings | None = None, repository: Repository | None = None, llm=None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(
        title="AI 관심도 비서 API",
        version="1.0.0",
        description="AI 이미지·영상 생성 플랫폼 8종의 위키백과 조회수(관심도) 데이터를 관리하고, "
                    "그 요약을 GPT 시스템 프롬프트에 주입해 대화하는 API.",
    )
    repo = repository or make_repository(settings)
    if repository is None and repo.backend == "memory":
        # 키 없이 띄운 로컬 데모: 서버를 켤 때마다 seed 365일을 메모리에 채운다(끄면 사라짐)
        repo.create_data_bulk(load_seed_rows())
    summaries = SummaryService(repo)
    model = llm or make_llm(settings)
    app.state.settings = settings
    app.state.repo = repo
    app.state.summaries = summaries
    app.state.chat = ChatService(repo, summaries, model)
    app.state.limiter = RateLimiter(settings.chat_rate_per_minute, settings.chat_daily_limit)

    @app.exception_handler(LLMError)
    async def _llm_error(_: Request, exc: LLMError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.middleware("http")
    async def _unexpected(request: Request, call_next):
        # CORS 미들웨어 안쪽에서 잡아야 500 응답에도 CORS 헤더가 붙어 브라우저가 에러 내용을 읽을 수 있다
        try:
            return await call_next(request)
        except Exception:
            log.exception("처리하지 못한 오류: %s %s", request.method, request.url.path)
            return JSONResponse({"detail": "서버 내부 오류가 발생했습니다"}, status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.include_router(data.router)
    app.include_router(conversations.router)
    app.include_router(chat.router)

    @app.get("/", tags=["health"], summary="서버 상태")
    @app.get("/api/health", tags=["health"], summary="서버 상태(콜드스타트 깨우기용)")
    def health():
        return {"status": "ok", "storage": repo.backend, "model": getattr(model, "model", "unknown"),
                "docs": "/docs"}

    log.info("저장소=%s, 모델=%s, CORS=%s", repo.backend, getattr(model, "model", "?"), settings.allowed_origins)
    return app


app = create_app()
