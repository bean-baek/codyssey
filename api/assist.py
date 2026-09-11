"""
POST /api/assist — 인라인 도우미 (유의어 / 역방향 사전 / 인상 / 분류)

설계 근거: AGENTS.md 3장
revise와 분리된 이유는 하나다. 이쪽은 빨라야 한다.
모델·토큰·타임아웃을 모두 낮춰 체감 지연을 1~2초로 유지한다.
"""

import json
import os
from http.server import BaseHTTPRequestHandler

from anthropic import Anthropic

# 모델 ID와 엔드포인트는 환경 변수로 바꿀 수 있다. revise.py 와 같은 이유다.
MODEL_ASSIST = os.environ.get("MODEL_ASSIST") or "claude-haiku-4"
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL") or None

MAX_TOKENS = 300
TIMEOUT_SEC = 10.0
MAX_QUERY = 500

COMMON = (
    "당신은 한국어로 글 쓰는 사람을 돕는 도구다. 설명하지 말고 결과만 반환한다.\n"
    "반드시 emit_candidates 도구를 호출한다."
)

MODES = {
    "synonym": {
        "count": 5,
        "system": (
            "주어진 단어를 대체할 표현을 제시한다.\n"
            "사전적 동의어가 아니라, 주어진 문맥의 그 자리에 실제로 들어갈 수 있는 말을 고른다.\n"
            "원문의 격식·시대감·화자 태도를 유지한다.\n"
            "설명이나 품사 표기를 붙이지 않는다."
        ),
    },
    "recall": {
        "count": 6,
        "system": (
            "사용자가 떠올리지 못하는 단어를 설명만 듣고 찾아준다.\n"
            "설명을 되풀이하지 말고 후보 단어·표현만 낸다.\n"
            "한 단어로 표현할 수 없으면 짧은 구도 허용한다.\n"
            "서로 다른 결의 후보를 섞어서 낸다. 비슷한 말만 나열하지 않는다."
        ),
    },
    "impression": {
        "count": 3,
        "system": (
            "주어진 문장이 독자에게 주는 인상을 형용사 또는 명사 3개로만 답한다.\n"
            "고치라고 하지 않는다. 좋고 나쁨을 판단하지 않는다.\n"
            "관찰만 한다."
        ),
    },
    "classify": {
        "count": 4,
        "system": (
            "원고 앞부분을 읽고 분류 태그 3개와 폴더 후보 1개를 제안한다.\n"
            "candidates 배열의 앞 3개는 태그, 마지막 1개는 폴더명으로 반환한다.\n"
            "내용을 요약하지 않는다."
        ),
    },
}

ASSIST_TOOL = {
    "name": "emit_candidates",
    "description": "후보 목록만 반환한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "candidates": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["candidates"],
    },
}


def build_user_message(mode, query, context):
    if mode == "synonym":
        ctx = f"\n\n[앞뒤 문맥]\n{context}" if context else ""
        return f"단어: {query}{ctx}"
    if mode == "recall":
        return f"찾는 단어에 대한 설명: {query}"
    if mode == "impression":
        return f"문장: {query}"
    return f"원고 앞부분:\n{query}"


def error(code, message):
    return {"error": {"code": code, "message": message}}


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, error("BAD_REQUEST", "요청 형식이 올바르지 않습니다."))

        mode = body.get("mode")
        if mode not in MODES:
            return self._send(400, error("BAD_REQUEST", "지원하지 않는 모드입니다."))

        query = body.get("query") or ""
        if not isinstance(query, str) or not query.strip():
            return self._send(400, error("EMPTY_INPUT", "찾을 내용을 입력해 주세요."))
        query = query.strip()[:MAX_QUERY]

        context = (body.get("context") or "")
        if not isinstance(context, str):
            context = ""
        context = context.strip()[:MAX_QUERY]

        cfg = MODES[mode]

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return self._send(500, error("UPSTREAM_ERROR", "잠시 후 다시 시도해 주세요."))

        client = Anthropic(
            api_key=api_key, base_url=BASE_URL, timeout=TIMEOUT_SEC, max_retries=0
        )

        try:
            resp = client.messages.create(
                model=MODEL_ASSIST,
                max_tokens=MAX_TOKENS,
                system=f"{COMMON}\n\n{cfg['system']}\n\n후보는 {cfg['count']}개 반환한다.",
                messages=[
                    {"role": "user", "content": build_user_message(mode, query, context)}
                ],
                tools=[ASSIST_TOOL],
                tool_choice={"type": "tool", "name": "emit_candidates"},
            )
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "status_code", None) == 429:
                return self._send(
                    429,
                    error("RATE_LIMITED", "요청이 몰리고 있습니다. 잠시 후 다시 시도해 주세요."),
                )
            return self._send(502, error("UPSTREAM_ERROR", "불러오지 못했습니다."))

        block = next((b for b in resp.content if b.type == "tool_use"), None)
        if block is None:
            return self._send(502, error("BAD_SCHEMA", "불러오지 못했습니다."))

        raw_items = block.input.get("candidates", [])
        candidates = [
            c.strip() for c in raw_items
            if isinstance(c, str) and c.strip()
        ][: cfg["count"]]

        return self._send(200, {"mode": mode, "candidates": candidates})
