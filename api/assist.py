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
    "반드시 emit_candidates 도구를 호출한다.\n"
    "국어사전에 실제로 있는 말만 낸다. 그럴듯해 보이는 말을 지어내지 않는다.\n"
    "같은 말의 활용형을 여러 개 내지 않는다."
)

MODES = {
    "synonym": {
        "count": 5,
        "system": (
            "주어진 단어를 대체할 표현을 제시한다.\n"
            "사전적 동의어가 아니라, 주어진 문맥의 그 자리에 실제로 들어갈 수 있는 말을 고른다.\n"
            "원문의 격식·시대감·화자 태도를 유지한다.\n"
            "\n"
            "[제외]\n"
            "- 주어진 단어 자체와 그 활용형. '쓸쓸하다'를 물었으면 '쓸쓸해 보였다'는 답이 아니다.\n"
            "- 설명, 품사 표기, 따옴표."
        ),
    },
    "recall": {
        "count": 6,
        "system": (
            "사용자가 떠올리지 못하는 단어를 설명만 듣고 찾아준다.\n"
            "\n"
            "[제외]\n"
            "- 설명을 말만 바꿔 옮긴 구. '해가 뜨기 직전'을 '새로운 날이 밝기 직전'이라고\n"
            "  바꿔 쓰는 것은 답이 아니다. 그 시간대를 부르는 이름을 내야 한다.\n"
            "- 없는 말. 그럴듯하게 조합한 낱말은 답이 아니다.\n"
            "- 설명이 가리키는 것과 품사가 다른 말. 대상을 물었으면 명사로 답한다.\n"
            "\n"
            "확실한 것을 앞에 둔다. 한 단어로 표현할 수 없을 때만 짧은 구를 허용한다."
        ),
    },
    "impression": {
        "count": 3,
        "system": (
            "주어진 문장이 독자에게 주는 인상을 낱말로만 답한다.\n"
            "고치라고 하지 않는다. 좋고 나쁨을 판단하지 않는다. 관찰만 한다.\n"
            "\n"
            "[제외]\n"
            "- '-적', '-성'을 임의로 붙여 만든 말. '침묵적'은 없는 말이다.\n"
            "- 문장의 내용 요약."
        ),
    },
    "classify": {
        "count": 4,
        "system": (
            "원고 앞부분을 읽고 분류 태그 3개와 폴더 후보 1개를 제안한다.\n"
            "candidates 배열의 앞 3개는 태그, 마지막 1개는 폴더명으로 반환한다.\n"
            "내용을 요약하지 않는다.\n"
            "태그는 글의 갈래·소재·정서 중에서 고른다."
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


def count_rule(mode, count):
    """개수 지시문.

    '정확히 N개'를 요구하면 모델이 수를 채우려고 없는 말을 만들어 낸다.
    실제로 '물주늘', '한이슬' 같은 조어가 섞여 나왔다. 상한으로 바꾸면 사라진다.
    revise 의 절대 규칙 4번(억지로 채우지 않는다)과 같은 원칙이다.
    """
    if mode == "classify":
        # 이 모드만 자리마다 뜻이 달라(앞 3개=태그, 끝 1개=폴더) 개수가 고정이다.
        return "반드시 4개를 반환한다. 앞 3개는 태그, 마지막 1개는 폴더 이름이다."
    return (
        f"후보는 최대 {count}개다. 확실한 것만 낸다.\n"
        f"개수를 채우려고 억지로 만들지 않는다. 둘뿐이면 둘만 낸다."
    )


def build_user_message(mode, query, context):
    if mode == "synonym":
        # 문맥에 대상 단어가 없으면 모델이 문맥 속 눈에 띄는 다른 단어를 바꾸려 든다.
        # ('쓸쓸하다'를 물었는데 문맥의 '어두웠다' 유의어가 나온 적이 있다)
        # 그래서 문맥을 먼저 주고 대상 단어를 마지막에 둔다.
        if context:
            return (
                f"[참고 문맥]\n{context}\n\n"
                f"위 문맥은 분위기를 보라고 준 것이다. 문맥에 있는 단어는 건드리지 않는다.\n"
                f"바꿀 단어는 오직 하나다 →  「{query}」\n"
                f"「{query}」를 대신할 표현만 낸다."
            )
        return f"바꿀 단어 →  「{query}」\n「{query}」를 대신할 표현만 낸다."
    if mode == "recall":
        return f"찾는 단어에 대한 설명: {query}"
    if mode == "impression":
        return f"문장: {query}"
    return f"원고 앞부분:\n{query}"


def dedupe(items):
    """빈 값과 중복을 걷어낸다. 순서는 유지한다.

    프롬프트로 막아도 '을씨년스럽다 / 을씨년스러웠다 / 을씨년스럽게'처럼
    활용형만 다른 것이 섞여 나온다. 후보 셋 중 둘이 같은 말이면 쓸모가 없다.

    한국어는 불규칙 활용이 많아 어미만 떼서는 같은 말인지 알기 어렵다.
    형태소 분석기를 넣을 자리는 아니므로 앞부분이 얼마나 겹치는지로 판정한다.
    겹치는 길이가 3자 이상이고 짧은 쪽의 60%를 넘으면 같은 줄기로 본다.
    '적막하다'와 '적막감'은 2자만 겹쳐 걸리지 않는다.
    """

    def norm(text):
        return "".join(text.split())

    def same_stem(a, b):
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        return n >= 3 and n >= len(min(a, b, key=len)) * 0.6

    out = []
    for item in items:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        key = norm(value)
        if any(key == norm(k) or same_stem(key, norm(k)) for k in out):
            continue
        out.append(value)
    return out


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
                system=f"{COMMON}\n\n{cfg['system']}\n\n{count_rule(mode, cfg['count'])}",
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
        candidates = dedupe(raw_items)[: cfg["count"]]

        return self._send(200, {"mode": mode, "candidates": candidates})
