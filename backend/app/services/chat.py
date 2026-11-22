"""POST /api/chat 의 흐름(컨텍스트 주입).

1) 데이터 요약 조회 (SummaryService — /api/data/summary 와 같은 계산)
2) 요약을 시스템 프롬프트에 삽입
3) GPT 호출 — 필요하면 도구를 부르고, 결과를 받아 다시 호출(최대 MAX_TOOL_ROUNDS 번)
4) 사용자 질문 + 답변을 conversations 에 자동 저장
"""
from __future__ import annotations

import json
from datetime import date

from ..db import Repository, now
from ..schemas import MESSAGES_PER_CONVERSATION_MAX, TITLE_MAX, ChatResponse, ToolCallLog
from .llm import LLMError
from .summary import SummaryService, summary_to_prompt
from .tools import TOOL_SCHEMAS, ToolRunner

MAX_TOOL_ROUNDS = 3
HISTORY_MESSAGES = 12      # 이전 대화는 최근 12개만 GPT 에 보낸다(토큰 절약)

SYSTEM_TEMPLATE = """당신은 데이터 분석 비서입니다. 사용자는 AI 이미지·영상 생성 플랫폼 8종
(Midjourney, Stable Diffusion, DALL-E, Flux, Sora, Runway, Kling, Veo)의 영어 위키백과 일별 조회수 합계를
'AI 생성 도구에 대한 대중의 관심도' 지표로 기록하고 있습니다.

[사용자 데이터 요약]
{summary}

오늘 날짜: {today}

규칙
- 위 데이터를 기반으로 맞춤형 답변을 하세요. 숫자를 말할 때는 기간과 단위를 함께 밝히세요.
- 요약에 없는 세부(특정 기간의 일별 값, 요일 패턴, 상위 일자, 이전 대화)가 필요할 때만 도구를 호출하세요.
- 데이터에 없는 사실(조회수가 오른 원인 등)은 추측이라고 분명히 표시하세요. 모르면 모른다고 하세요.
- 한국어로 3~6문장, 핵심 숫자부터 답하세요."""


def build_system_prompt(summary_text: str, today: date | None = None) -> str:
    return SYSTEM_TEMPLATE.format(summary=summary_text, today=(today or date.today()).isoformat())


def _reason(args: dict) -> str:
    r = str(args.get("reason", "")).strip()
    extra = ", ".join(f"{k}={v}" for k, v in args.items() if k != "reason")
    return (r or "(이유 없음)") + (f" [{extra}]" if extra else "")


class ChatService:
    def __init__(self, repo: Repository, summaries: SummaryService, llm) -> None:
        self.repo = repo
        self.summaries = summaries
        self.llm = llm
        self.tools = ToolRunner(repo, summaries)

    def chat(self, message: str, conversation_id: str | None) -> ChatResponse:
        conv = None
        if conversation_id:
            conv = self.repo.get_conversation(conversation_id)
            if conv is None:
                raise LookupError("conversation")

        summary = self.summaries.summary()
        msgs: list[dict] = [{"role": "system", "content": build_system_prompt(summary_to_prompt(summary))}]
        if conv:
            msgs += [{"role": m["role"], "content": m["content"]} for m in conv["messages"][-HISTORY_MESSAGES:]]
        msgs.append({"role": "user", "content": message})

        logs: list[ToolCallLog] = []
        reply = None
        for round_ in range(MAX_TOOL_ROUNDS + 1):
            use_tools = round_ < MAX_TOOL_ROUNDS     # 마지막 라운드는 도구 없이 답을 강제
            turn = self.llm.chat(msgs, TOOL_SCHEMAS if use_tools else None)
            if not turn.tool_calls:
                reply = (turn.content or "").strip()
                break
            msgs.append({"role": "assistant", "content": turn.content,
                         "tool_calls": [{"id": c.id, "type": "function",
                                         "function": {"name": c.name, "arguments": c.arguments}}
                                        for c in turn.tool_calls]})
            for c in turn.tool_calls:
                try:
                    args = json.loads(c.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError
                except ValueError:
                    args = {}
                logs.append(ToolCallLog(name=c.name, arguments=args, reason=_reason(args)))
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": self.tools.run(c.name, args)})
        if not reply:
            raise LLMError("모델이 빈 답변을 돌려줬습니다. 다시 시도하세요", 502)

        t = now()
        new_msgs = [
            {"role": "user", "content": message, "created_at": t, "tools": []},
            {"role": "assistant", "content": reply, "created_at": t, "tools": [lg.name for lg in logs]},
        ]
        if conv:
            self.repo.append_messages(conv["id"], new_msgs, MESSAGES_PER_CONVERSATION_MAX)
            conv_id = conv["id"]
        else:
            title = message if len(message) <= TITLE_MAX else message[:TITLE_MAX - 1] + "…"
            conv_id = self.repo.create_conversation(title, new_msgs)["id"]

        return ChatResponse(conversation_id=conv_id, reply=reply, tool_calls=logs,
                            summary_period=summary.period, model=getattr(self.llm, "model", "unknown"))
