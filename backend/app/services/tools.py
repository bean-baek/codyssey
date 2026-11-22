"""GPT 가 필요할 때 부르는 내부 도구(Function Calling).

요약은 이미 시스템 프롬프트에 들어 있다. 도구는 요약만으로 답할 수 없는 질문
(특정 기간의 일별 값, 요일별 패턴, 지난 대화 내용)에만 쓰도록 description 에 적었다.
모든 도구는 reason 인자를 받는다 — 모델이 "왜 이 도구를 부르는지"를 스스로 적게 해서
응답의 tool_calls 와 README 에 호출 근거로 남긴다.
"""
from __future__ import annotations

import json
from datetime import date as Date

from ..db import Repository
from .summary import SummaryService

QUERY_MAX_ROWS = 62

_REASON = {"type": "string", "description": "이 도구를 호출하는 이유(한국어 한 문장)"}

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_data_summary",
            "description": "전체 데이터 요약(기간·개수·평균·최대·최소·최근 추세·최근 6개월 월평균)을 다시 조회한다. "
                           "시스템 프롬프트의 요약이 최신인지 확인하거나 원본 JSON 이 필요할 때만 쓴다.",
            "parameters": {"type": "object", "properties": {"reason": _REASON}, "required": ["reason"],
                           "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "요약에 없는 심화 지표: 요일별 평균, 전체 월별 평균(모든 달), 변동성(일간 변화율 표준편차), "
                           "값이 가장 높았던 상위 5일과 메모. '무슨 요일', '몇 월', '가장 높았던 날들', '변동' 질문에 쓴다.",
            "parameters": {"type": "object", "properties": {"reason": _REASON}, "required": ["reason"],
                           "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": f"특정 기간의 일별 값과 메모를 조회한다(최대 {QUERY_MAX_ROWS}일). "
                           "'3월에 어땠어', '지난주', '특정 날짜' 처럼 기간이 정해진 질문에 쓴다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "시작일 YYYY-MM-DD"},
                    "end": {"type": "string", "description": "종료일 YYYY-MM-DD"},
                    "reason": _REASON,
                },
                "required": ["start", "end", "reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "저장된 이전 대화 목록(제목·미리보기)을 조회한다. 사용자가 '지난번에', '전에 물어본' 처럼 "
                           "이전 대화를 언급할 때만 쓴다.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}, "reason": _REASON},
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversation",
            "description": "list_conversations 로 찾은 특정 대화의 메시지를 조회한다(최근 10개).",
            "parameters": {
                "type": "object",
                "properties": {"conversation_id": {"type": "string"}, "reason": _REASON},
                "required": ["conversation_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolError(Exception):
    pass


def _iso(v: str, name: str) -> str:
    try:
        return Date.fromisoformat(v).isoformat()
    except (TypeError, ValueError):
        raise ToolError(f"{name} 는 YYYY-MM-DD 형식이어야 합니다: {v!r}")


class ToolRunner:
    def __init__(self, repo: Repository, summaries: SummaryService) -> None:
        self.repo = repo
        self.summaries = summaries

    def run(self, name: str, args: dict) -> str:
        """도구를 실행하고 모델에게 돌려줄 JSON 문자열을 만든다. 실패도 JSON 으로 돌려 모델이 스스로 고치게 한다."""
        try:
            result = getattr(self, f"_t_{name}")(args) if hasattr(self, f"_t_{name}") else None
            if result is None:
                raise ToolError(f"알 수 없는 도구: {name}")
        except ToolError as e:
            result = {"error": str(e)}
        return json.dumps(result, ensure_ascii=False, default=str)

    def _t_get_data_summary(self, args: dict):
        return self.summaries.summary().model_dump(mode="json")

    def _t_get_statistics(self, args: dict):
        s = self.summaries.statistics().model_dump(mode="json")
        s.pop("series")                     # 그래프용 365개 점은 모델에게 불필요(토큰 절약)
        return s

    def _t_query_data(self, args: dict):
        start, end = _iso(args.get("start"), "start"), _iso(args.get("end"), "end")
        if start > end:
            start, end = end, start
        rows = [r for r in self.summaries.rows() if start <= str(r["date"]) <= end]
        if len(rows) > QUERY_MAX_ROWS:
            raise ToolError(f"{len(rows)}일은 너무 깁니다. {QUERY_MAX_ROWS}일 이하로 나눠 조회하거나 get_statistics 의 월별 평균을 쓰세요.")
        return {"start": start, "end": end, "count": len(rows),
                "items": [{"date": str(r["date"]), "value": r["value"], "memo": r.get("memo", "")} for r in rows]}

    def _t_list_conversations(self, args: dict):
        limit = max(1, min(int(args.get("limit") or 10), 20))
        return [{"id": c["id"], "title": c.get("title", ""), "preview": c.get("preview", ""),
                 "updated_at": c.get("updated_at")} for c in self.repo.list_conversations(limit)]

    def _t_get_conversation(self, args: dict):
        c = self.repo.get_conversation(str(args.get("conversation_id", "")))
        if not c:
            raise ToolError("해당 대화가 없습니다")
        return {"id": c["id"], "title": c.get("title", ""),
                "messages": [{"role": m["role"], "content": m["content"][:500]} for m in c["messages"][-10:]]}
