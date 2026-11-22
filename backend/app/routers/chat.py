"""/api/chat — 데이터 요약을 주입한 AI 대화(자동 저장)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import chat_service, client_ip
from ..schemas import ChatRequest, ChatResponse
from ..services.chat import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="AI 대화(데이터 요약 컨텍스트 주입)")
def chat(body: ChatRequest, request: Request, svc: ChatService = Depends(chat_service)):
    """요약 조회 → 시스템 프롬프트 삽입 → GPT 호출(필요 시 도구 호출) → conversations 자동 저장.

    conversation_id 를 주면 그 대화의 최근 메시지를 함께 보내 이어서 대화한다.
    """
    request.app.state.limiter.check(client_ip(request))
    try:
        return svc.chat(body.message, body.conversation_id)
    except LookupError:
        raise HTTPException(404, f"대화를 찾을 수 없습니다: {body.conversation_id}")
