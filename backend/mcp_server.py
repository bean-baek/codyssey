"""보너스: 같은 기능을 MCP Server 로 노출(외부 채널 — Claude Desktop / Claude Code 등).

GPT Function Calling 이 서버 안에서 부르는 도구와 같은 이름·같은 데이터를, MCP 클라이언트가
배포된 REST API(API_BASE_URL)를 거쳐 부른다. 즉 "도구 정의는 하나, 채널은 둘".

  실행(stdio):  API_BASE_URL=https://<render-app>.onrender.com python backend/mcp_server.py
  Claude Code 등록:
    claude mcp add ai-interest -e API_BASE_URL=https://<render-app>.onrender.com -- \
      /절대경로/.venv/bin/python /절대경로/backend/mcp_server.py
"""
from __future__ import annotations

import os

import httpx
from mcp.server.mcpserver import MCPServer

API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = httpx.Timeout(70.0)       # Render 무료 티어 콜드스타트(최대 ~1분) 고려

mcp = MCPServer(
    name="ai-interest",
    instructions="AI 이미지·영상 생성 플랫폼 8종의 위키백과 조회수 합계(관심도) 데이터와 대화 기록을 조회한다.",
)


def _get(path: str, **params) -> dict | list:
    r = httpx.get(f"{API}{path}", params={k: v for k, v in params.items() if v is not None}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


@mcp.tool(description="전체 데이터 요약: 기간, 개수, 평균·최대·최소, 최근 30일 추세, 최근 6개월 월평균")
def get_data_summary() -> dict:
    return _get("/api/data/summary")


@mcp.tool(description="심화 지표: 요일별 평균, 월별 평균, 변동성, 상위 5일(그래프용 시계열 제외)")
def get_statistics() -> dict:
    s = _get("/api/data/statistics")
    s.pop("series", None)
    return s


@mcp.tool(description="특정 기간(YYYY-MM-DD ~ YYYY-MM-DD)의 일별 값과 메모")
def query_data(start: str, end: str) -> dict:
    return _get("/api/data", start=start, end=end, order="asc")


@mcp.tool(description="저장된 대화 목록(제목·미리보기, 최신순)")
def list_conversations(limit: int = 10) -> dict:
    return _get("/api/conversations", limit=max(1, min(limit, 50)))


@mcp.tool(description="특정 대화의 전체 메시지")
def get_conversation(conversation_id: str) -> dict:
    return _get(f"/api/conversations/{conversation_id}")


@mcp.tool(description="서비스의 AI 비서(GPT + 데이터 요약 주입)에게 질문하고 답을 받는다. 대화는 서버에 자동 저장된다.")
def ask_assistant(message: str, conversation_id: str | None = None) -> dict:
    r = httpx.post(f"{API}/api/chat", json={"message": message, "conversation_id": conversation_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    mcp.run("stdio")
