"""라우터가 쓰는 공용 객체(앱 수명 동안 1개씩) 꺼내기 + 간단한 요청 제한."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import HTTPException, Request

from .db import Repository
from .services.chat import ChatService
from .services.summary import SummaryService


def repo(request: Request) -> Repository:
    return request.app.state.repo


def summaries(request: Request) -> SummaryService:
    return request.app.state.summaries


def chat_service(request: Request) -> ChatService:
    return request.app.state.chat


class RateLimiter:
    """IP 당 분당 N회 + 서버 전체 하루 M회. GPT 과금 폭주를 막는 최소 장치(인스턴스 1개 기준)."""

    def __init__(self, per_minute: int, per_day: int) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self._hits: dict[str, deque] = defaultdict(deque)
        self._day = date.today()
        self._day_count = 0
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        t = time.monotonic()
        with self._lock:
            if date.today() != self._day:
                self._day, self._day_count = date.today(), 0
            if self._day_count >= self.per_day:
                raise HTTPException(429, "오늘 사용 가능한 채팅 횟수를 모두 썼습니다. 내일 다시 시도하세요")
            q = self._hits[key]
            while q and t - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                raise HTTPException(429, "요청이 너무 잦습니다. 1분 뒤 다시 시도하세요")
            q.append(t)
            self._day_count += 1


def client_ip(request: Request) -> str:
    # Render 는 프록시 뒤에 있으므로 X-Forwarded-For 의 첫 값이 실제 클라이언트
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")
