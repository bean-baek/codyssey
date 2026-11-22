"""요청·응답 모델(Pydantic).

요청 모델은 "잘못된 값이 DB까지 가지 않게" 막는 첫 관문이다.
- 날짜는 문자열이 아니라 date 로 받아 2026-13-40 같은 값을 422로 거른다.
- 조회수(value)는 음수·NaN·무한대를 거른다.
- 문자열은 길이 상한을 둬서 Firestore 문서(1MB)·GPT 토큰이 폭주하지 않게 한다.
- extra="forbid" 로 오타 난 필드(valeu 등)를 조용히 무시하지 않고 에러로 알린다.
"""
from __future__ import annotations

import math
from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_VALUE = 1e9
MEMO_MAX = 200
MESSAGE_MAX = 1000
TITLE_MAX = 60
MESSAGES_PER_CONVERSATION_MAX = 100


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- data ----------

class DataCreate(_Strict):
    date: Date = Field(description="날짜(YYYY-MM-DD)", examples=["2026-11-20"])
    value: float = Field(ge=0, le=MAX_VALUE, description="그날의 값(AI 생성 플랫폼 8종 위키백과 조회수 합계)",
                         examples=[3120])
    memo: str = Field(default="", max_length=MEMO_MAX, description="메모(선택)", examples=["Sora 신모델 발표"])

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("value 는 유한한 숫자여야 합니다")
        return v


class DataUpdate(_Strict):
    """부분 수정. 보낸 필드만 바뀐다. 최소 1개는 보내야 한다."""
    date: Date | None = None
    value: float | None = Field(default=None, ge=0, le=MAX_VALUE)
    memo: str | None = Field(default=None, max_length=MEMO_MAX)

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("value 는 유한한 숫자여야 합니다")
        return v

    def changes(self) -> dict:
        return self.model_dump(exclude_unset=True, exclude_none=True)


class DataRecord(BaseModel):
    id: str
    date: Date
    value: float
    memo: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DataList(BaseModel):
    count: int
    items: list[DataRecord]


# ---------- summary / statistics ----------

class Extreme(BaseModel):
    value: float
    date: Date


class Metrics(BaseModel):
    total: float
    average: float
    median: float
    max: Extreme
    min: Extreme
    std: float = Field(description="일별 값의 표준편차")


class Trend(BaseModel):
    direction: Literal["상승", "하락", "유지", "데이터 부족"]
    change_pct: float | None = Field(description="최근 30일 평균 ÷ 직전 30일 평균 − 1 (%)")
    recent_avg: float | None
    previous_avg: float | None
    label: str = Field(description="사람이 읽는 한 줄 요약", examples=["하락 (최근 30일 평균 -12.3%)"])


class MonthlyPoint(BaseModel):
    month: str
    average: float
    total: float
    days: int


class Summary(BaseModel):
    period: str = Field(examples=["2025-11-20 ~ 2026-11-19"])
    start: Date | None
    end: Date | None
    count: int
    metrics: Metrics | None
    trend: Trend
    latest: DataRecord | None
    monthly: list[MonthlyPoint] = Field(description="최근 6개월 월평균")
    unit: str = "회/일 (영어 위키백과 조회수, 8개 플랫폼 합계)"


class WeekdayPoint(BaseModel):
    weekday: str
    average: float


class SeriesPoint(BaseModel):
    date: Date
    value: float
    ma7: float | None


class Statistics(BaseModel):
    """보너스: 요약보다 자세한 지표 + 그래프용 시계열."""
    count: int
    volatility_pct: float | None = Field(description="일간 변화율의 표준편차(%) — 들쭉날쭉한 정도")
    weekday: list[WeekdayPoint]
    monthly: list[MonthlyPoint]
    top_days: list[DataRecord]
    series: list[SeriesPoint]


# ---------- conversations ----------

class Message(_Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime | None = None
    tools: list[str] = Field(default_factory=list, description="이 답변을 만들 때 호출한 도구 이름")


class ConversationCreate(_Strict):
    title: str = Field(default="", max_length=TITLE_MAX)
    messages: list[Message] = Field(min_length=1, max_length=MESSAGES_PER_CONVERSATION_MAX)


class ConversationMeta(BaseModel):
    """목록용. messages 는 포함하지 않는다(방식 A: 전체 메시지는 GET /api/conversations/{id})."""
    id: str
    title: str
    message_count: int
    preview: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Conversation(ConversationMeta):
    messages: list[Message]


class ConversationList(BaseModel):
    count: int
    items: list[ConversationMeta]


# ---------- chat ----------

class ChatRequest(_Strict):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX, examples=["최근 관심도 추세가 어때?"])
    conversation_id: str | None = Field(default=None, max_length=64,
                                        description="이어서 대화할 때. 비우면 새 대화를 만든다")


class ToolCallLog(BaseModel):
    name: str
    arguments: dict
    reason: str = Field(description="모델이 이 도구를 부른 근거(인자 요약)")


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolCallLog]
    summary_period: str
    model: str
