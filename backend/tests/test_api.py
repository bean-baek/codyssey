"""API 테스트 — Firestore·OpenAI 없이 메모리 저장소와 가짜 LLM 으로 실행한다.

  cd backend && python -m pytest -q
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import MemoryRepository
from app.services.llm import AssistantTurn, LLMError, ToolCall
from app.services.summary import compute_summary, compute_trend
from main import create_app


class FakeLLM:
    """받은 messages 를 기록하고, 정해진 순서대로 턴을 돌려준다."""
    model = "fake"

    def __init__(self, turns: list[AssistantTurn] | None = None) -> None:
        self.turns = list(turns or [])
        self.calls: list[list[dict]] = []
        self.tools_seen: list[bool] = []

    def chat(self, messages, tools):
        self.calls.append([dict(m) for m in messages])
        self.tools_seen.append(bool(tools))
        return self.turns.pop(0) if self.turns else AssistantTurn("기본 답변")


def rows(n: int, start_value: float = 100, step: float = 0) -> list[dict]:
    from datetime import date, timedelta
    d0 = date(2026, 1, 1)
    return [{"date": (d0 + timedelta(days=i)).isoformat(), "value": start_value + step * i, "memo": ""}
            for i in range(n)]


def make(llm=None, seed: list[dict] | None = None, **settings):
    repo = MemoryRepository()
    if seed:
        repo.create_data_bulk(seed)
    app = create_app(Settings(allowed_origins=["https://front.example"], **settings), repo, llm or FakeLLM())
    return TestClient(app), repo, app


# ---------------------------------------------------------------- data CRUD + 검증

def test_data_crud_flow():
    c, _, _ = make()
    r = c.post("/api/data", json={"date": "2026-11-20", "value": 3000, "memo": "테스트"})
    assert r.status_code == 201
    doc_id = r.json()["id"]

    assert c.get("/api/data").json()["count"] == 1

    r = c.put(f"/api/data/{doc_id}", json={"value": 3500})
    assert r.status_code == 200 and r.json()["value"] == 3500 and r.json()["memo"] == "테스트"

    assert c.delete(f"/api/data/{doc_id}").status_code == 200
    assert c.get("/api/data").json()["count"] == 0
    assert c.delete(f"/api/data/{doc_id}").status_code == 404


@pytest.mark.parametrize("body", [
    {"date": "2026-13-40", "value": 1},          # 없는 날짜
    {"date": "2026-11-20", "value": -1},         # 음수
    {"date": "2026-11-20"},                      # value 누락
    {"date": "2026-11-20", "value": "많음"},      # 숫자 아님
    {"date": "2026-11-20", "value": 1, "memo": "x" * 201},   # 메모 길이 초과
    {"date": "2026-11-20", "value": 1, "valeu": 2},          # 모르는 필드
])
def test_data_validation_rejects(body):
    c, _, _ = make()
    assert c.post("/api/data", json=body).status_code == 422


def test_duplicate_date_conflicts():
    c, _, _ = make()
    c.post("/api/data", json={"date": "2026-11-20", "value": 1})
    assert c.post("/api/data", json={"date": "2026-11-20", "value": 2}).status_code == 409
    other = c.post("/api/data", json={"date": "2026-11-21", "value": 3}).json()["id"]
    assert c.put(f"/api/data/{other}", json={"date": "2026-11-20"}).status_code == 409


def test_update_requires_a_field_and_valid_id():
    c, _, _ = make(seed=rows(1))
    doc_id = c.get("/api/data").json()["items"][0]["id"]
    assert c.put(f"/api/data/{doc_id}", json={}).status_code == 422
    assert c.put("/api/data/bad%2Fid", json={"value": 1}).status_code in (404, 422)


def test_list_filters_and_order():
    c, _, _ = make(seed=rows(10))
    r = c.get("/api/data", params={"start": "2026-01-03", "end": "2026-01-05", "order": "asc"}).json()
    assert [x["date"] for x in r["items"]] == ["2026-01-03", "2026-01-04", "2026-01-05"]
    assert c.get("/api/data", params={"limit": 2}).json()["items"][0]["date"] == "2026-01-10"


# ---------------------------------------------------------------- summary

def test_summary_reflects_writes():
    c, _, _ = make(seed=rows(60, 100))
    s = c.get("/api/data/summary").json()
    assert s["count"] == 60 and s["metrics"]["max"]["value"] == 100
    c.post("/api/data", json={"date": "2026-12-31", "value": 999})
    s = c.get("/api/data/summary").json()            # 캐시가 무효화돼야 한다
    assert s["count"] == 61 and s["metrics"]["max"] == {"value": 999, "date": "2026-12-31"}


def test_trend_directions():
    assert compute_trend([100] * 30 + [120] * 30).direction == "상승"
    assert compute_trend([100] * 30 + [80] * 30).direction == "하락"
    assert compute_trend([100] * 30 + [103] * 30).direction == "유지"
    assert compute_trend([1] * 59).direction == "데이터 부족"


def test_empty_summary():
    s = compute_summary([])
    assert s.count == 0 and s.metrics is None


def test_statistics_and_export():
    c, _, _ = make(seed=rows(14, 10, 1))
    st = c.get("/api/data/statistics").json()
    assert len(st["weekday"]) == 7 and st["top_days"][0]["value"] == 23
    assert st["series"][5]["ma7"] is None and st["series"][6]["ma7"] == 13.0
    csv_text = c.get("/api/data/export", params={"format": "csv"}).content.decode("utf-8-sig")
    assert csv_text.splitlines()[0] == "date,value,memo" and len(csv_text.splitlines()) == 15
    assert len(c.get("/api/data/export", params={"format": "json"}).json()) == 14


# ---------------------------------------------------------------- conversations

def test_conversation_save_list_load_delete():
    c, _, _ = make()
    r = c.post("/api/conversations", json={"messages": [
        {"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워요"}]})
    assert r.status_code == 201
    conv = r.json()
    assert conv["title"] == "안녕"

    listed = c.get("/api/conversations").json()["items"][0]
    assert "messages" not in listed and listed["message_count"] == 2

    loaded = c.get(f"/api/conversations/{conv['id']}").json()
    assert [m["content"] for m in loaded["messages"]] == ["안녕", "반가워요"]

    assert c.delete(f"/api/conversations/{conv['id']}").status_code == 200
    assert c.get(f"/api/conversations/{conv['id']}").status_code == 404


def test_conversation_validation():
    c, _, _ = make()
    assert c.post("/api/conversations", json={"messages": []}).status_code == 422
    assert c.post("/api/conversations", json={"messages": [{"role": "system", "content": "x"}]}).status_code == 422


# ---------------------------------------------------------------- chat

def test_chat_injects_summary_and_autosaves():
    llm = FakeLLM([AssistantTurn("평균은 100회예요")])
    c, _, _ = make(llm, seed=rows(60, 100))
    r = c.post("/api/chat", json={"message": "평균이 어때?"})
    assert r.status_code == 200
    body = r.json()
    system = llm.calls[0][0]
    assert system["role"] == "system" and "[사용자 데이터 요약]" in system["content"]
    assert "총 레코드: 60개" in system["content"] and "2026-01-01 ~ 2026-03-01" in system["content"]
    assert body["reply"] == "평균은 100회예요" and body["summary_period"] == "2026-01-01 ~ 2026-03-01"

    conv = c.get(f"/api/conversations/{body['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]


def test_chat_continues_conversation_with_history():
    llm = FakeLLM([AssistantTurn("첫 답"), AssistantTurn("둘째 답")])
    c, _, _ = make(llm, seed=rows(5))
    cid = c.post("/api/chat", json={"message": "첫 질문"}).json()["conversation_id"]
    c.post("/api/chat", json={"message": "둘째 질문", "conversation_id": cid})
    sent = [m["content"] for m in llm.calls[1][1:]]
    assert sent == ["첫 질문", "첫 답", "둘째 질문"]
    assert c.get(f"/api/conversations/{cid}").json()["message_count"] == 4
    assert c.post("/api/chat", json={"message": "x", "conversation_id": "nope"}).status_code == 404


def test_chat_tool_call_round_trip():
    llm = FakeLLM([
        AssistantTurn(None, [ToolCall("t1", "query_data",
                                      json.dumps({"start": "2026-01-02", "end": "2026-01-03", "reason": "기간 조회"}))]),
        AssistantTurn("1월 2~3일은 101, 102회예요"),
    ])
    c, _, _ = make(llm, seed=rows(10, 100, 1))
    body = c.post("/api/chat", json={"message": "1월 2일부터 3일까지?"}).json()
    assert body["tool_calls"][0]["name"] == "query_data"
    assert body["tool_calls"][0]["reason"].startswith("기간 조회")
    tool_msg = llm.calls[1][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["count"] == 2
    saved = c.get(f"/api/conversations/{body['conversation_id']}").json()["messages"][-1]
    assert saved["tools"] == ["query_data"]


def test_chat_stops_tool_loop():
    loop = AssistantTurn(None, [ToolCall("t", "get_statistics", '{"reason":"r"}')])
    llm = FakeLLM([loop, loop, loop, AssistantTurn("끝")])
    c, _, _ = make(llm, seed=rows(5))
    assert c.post("/api/chat", json={"message": "?"}).json()["reply"] == "끝"
    assert llm.tools_seen == [True, True, True, False]       # 마지막 호출은 도구 없이


def test_chat_bad_tool_args_are_reported_to_model():
    llm = FakeLLM([AssistantTurn(None, [ToolCall("t", "query_data", '{"start":"어제","end":"오늘","reason":"r"}')]),
                   AssistantTurn("날짜 형식을 다시 확인할게요")])
    c, _, _ = make(llm, seed=rows(5))
    assert c.post("/api/chat", json={"message": "?"}).status_code == 200
    assert "error" in json.loads(llm.calls[1][-1]["content"])


def test_chat_validation_and_llm_error():
    class Boom:
        model = "boom"

        def chat(self, *_):
            raise LLMError("OpenAI 인증 실패", 502)

    c, repo, _ = make(Boom())
    assert c.post("/api/chat", json={"message": ""}).status_code == 422
    assert c.post("/api/chat", json={"message": "x" * 1001}).status_code == 422
    r = c.post("/api/chat", json={"message": "안녕"})
    assert r.status_code == 502 and "인증" in r.json()["detail"]
    assert repo.list_conversations() == []                 # 실패한 대화는 저장하지 않는다


def test_chat_rate_limit():
    c, _, _ = make(chat_rate_per_minute=2)
    assert [c.post("/api/chat", json={"message": "hi"}).status_code for _ in range(3)] == [200, 200, 429]


# ---------------------------------------------------------------- CORS / docs

def test_cors_allows_only_configured_origin():
    c, _, _ = make()
    ok = c.options("/api/data", headers={"Origin": "https://front.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "https://front.example"
    bad = c.options("/api/data", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_swagger_available():
    c, _, _ = make()
    assert c.get("/docs").status_code == 200
    paths = c.get("/openapi.json").json()["paths"]
    for p in ["/api/data", "/api/data/{doc_id}", "/api/data/summary", "/api/conversations",
              "/api/conversations/{conv_id}", "/api/chat"]:
        assert p in paths


def test_openai_client_ignores_empty_base_url_env(monkeypatch):
    from app.services.llm import OpenAILLM
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    llm = OpenAILLM(Settings(openai_api_key="sk-test"))
    assert str(llm._client.base_url).startswith("https://api.openai.com/v1")
