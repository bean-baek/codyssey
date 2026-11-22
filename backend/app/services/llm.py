"""LLM 클라이언트.

- OpenAILLM  : 실제 GPT 호출(Chat Completions + tools). max_completion_tokens 로 답변 길이(=과금) 상한
- OfflineLLM : OPENAI_API_KEY 가 없을 때. 요약 수치로 정해진 문장을 돌려주는 데모 모드.
               화면에 "데모 모드"라고 표시되며, 실제 GPT 답변으로 오해되지 않게 model="offline-demo" 로 응답한다.
테스트에서는 같은 인터페이스(chat)를 가진 가짜 객체를 넣는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..config import Settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str          # 모델이 준 JSON 문자열 그대로


@dataclass
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None,
                              timeout=40, max_retries=1)

    def chat(self, messages: list[dict], tools: list[dict] | None) -> AssistantTurn:
        import openai

        kwargs = {"model": self.model, "messages": messages, "max_completion_tokens": self.max_tokens}
        if tools:
            kwargs["tools"] = tools
        try:
            res = self._client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as e:
            raise LLMError("OpenAI 인증 실패 — 서버의 OPENAI_API_KEY 를 확인하세요", 502) from e
        except openai.RateLimitError as e:
            raise LLMError("OpenAI 사용량 한도에 걸렸습니다. 잠시 후 다시 시도하세요", 429) from e
        except openai.APITimeoutError as e:
            raise LLMError("OpenAI 응답이 늦어 중단했습니다. 다시 시도하세요", 504) from e
        except openai.APIError as e:
            raise LLMError(f"OpenAI 호출 실패: {getattr(e, 'message', str(e))[:200]}", 502) from e
        msg = res.choices[0].message
        calls = [ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
                 for c in (msg.tool_calls or []) if c.type == "function"]
        return AssistantTurn(content=msg.content, tool_calls=calls)


class OfflineLLM:
    """키 없이 화면 흐름을 확인하기 위한 데모. 도구 호출 흐름도 흉내 낸다."""
    model = "offline-demo"

    def chat(self, messages: list[dict], tools: list[dict] | None) -> AssistantTurn:
        last = messages[-1]
        if last["role"] == "user" and tools and any(k in last["content"] for k in ("요일", "가장 높", "변동", "월별")):
            return AssistantTurn(None, [ToolCall("demo-1", "get_statistics",
                                                 json.dumps({"reason": "요일·월별·상위 일자 지표가 필요해서"}))])
        if last["role"] == "tool":
            data = json.loads(last["content"])
            wd = max(data.get("weekday", []), key=lambda w: w["average"], default=None)
            top = data.get("top_days", [{}])[0]
            return AssistantTurn(
                f"[데모 모드 — OPENAI_API_KEY 미설정] 통계 도구 결과: 평균이 가장 높은 요일은 "
                f"{wd['weekday'] if wd else '-'}요일, 가장 높았던 날은 {top.get('date', '-')} "
                f"({top.get('value', 0):,.0f}회)입니다.")
        system = messages[0]["content"]
        block = system.split("[사용자 데이터 요약]")[-1].split("\n\n")[0].strip()
        return AssistantTurn("[데모 모드 — OPENAI_API_KEY 미설정] 실제 GPT 대신 시스템 프롬프트에 주입된 요약을 "
                             "그대로 보여 드립니다.\n" + block)


def make_llm(settings: Settings):
    return OpenAILLM(settings) if settings.use_openai else OfflineLLM()
