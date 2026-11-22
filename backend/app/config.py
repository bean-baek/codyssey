"""환경 변수 → 설정 객체.

키·주소는 전부 환경 변수에서만 읽는다(코드에 하드코딩 금지).
로컬에서는 backend/.env 를 python-dotenv 로 읽고, Render 에서는 대시보드의 Environment 값을 쓴다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _split(value: str) -> list[str]:
    return [v.strip().rstrip("/") for v in value.split(",") if v.strip()]


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = ""          # 프록시를 쓸 때만. 비우면 공식 엔드포인트
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 600       # 답변 1회 최대 토큰(과금 상한)

    # Firestore
    firebase_service_account_json: str = ""   # JSON 문자열 그대로
    firebase_service_account_path: str = ""   # 또는 키 파일 경로(로컬용)

    # CORS / 운영
    allowed_origins: list[str] = field(default_factory=list)
    chat_rate_per_minute: int = 10     # IP 당 분당 채팅 요청 수
    chat_daily_limit: int = 300        # 서버 전체 하루 채팅 요청 수(과금 상한)

    @property
    def use_firestore(self) -> bool:
        return bool(self.firebase_service_account_json or self.firebase_service_account_path)

    @property
    def use_openai(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    origins = _split(os.getenv("ALLOWED_ORIGINS", ""))
    if not origins:
        # 로컬 개발 기본값: 프론트를 python -m http.server 5500 등으로 띄우는 경우
        origins = ["http://localhost:5500", "http://127.0.0.1:5500",
                   "http://localhost:3000", "http://127.0.0.1:3000"]
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_model=os.getenv("OPENAI_MODEL", "") or "gpt-4o-mini",
        openai_max_tokens=_int("OPENAI_MAX_TOKENS", 600),
        firebase_service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        firebase_service_account_path=os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", ""),
        allowed_origins=origins,
        chat_rate_per_minute=_int("CHAT_RATE_PER_MINUTE", 10),
        chat_daily_limit=_int("CHAT_DAILY_LIMIT", 300),
    )
