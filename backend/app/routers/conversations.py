"""/api/conversations — 대화 기록 저장·목록·불러오기·삭제.

목록(GET /api/conversations)은 messages 를 빼고 제목·개수·미리보기만 준다(방식 A).
대화를 불러올 때는 GET /api/conversations/{id} 로 전체 messages 를 받는다.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..db import Repository, now
from ..deps import repo
from ..schemas import TITLE_MAX, Conversation, ConversationCreate, ConversationList

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

ConvId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


@router.post("", response_model=Conversation, status_code=201, summary="대화 저장")
def create_conversation(body: ConversationCreate, r: Repository = Depends(repo)):
    """채팅(/api/chat)은 자동 저장된다. 이 API 는 외부에서 만든 대화를 직접 저장할 때 쓴다."""
    t = now()
    messages = [m.model_dump() | {"created_at": m.created_at or t} for m in body.messages]
    title = body.title or next((m["content"] for m in messages if m["role"] == "user"), messages[0]["content"])
    return r.create_conversation(title[:TITLE_MAX], messages)


@router.get("", response_model=ConversationList, summary="대화 목록 조회(messages 제외)")
def list_conversations(limit: int = Query(50, ge=1, le=100), r: Repository = Depends(repo)):
    items = r.list_conversations(limit)
    return {"count": len(items), "items": items}


@router.get("/{conv_id}", response_model=Conversation, summary="특정 대화 불러오기(전체 messages)")
def get_conversation(conv_id: ConvId, r: Repository = Depends(repo)):
    c = r.get_conversation(conv_id)
    if c is None:
        raise HTTPException(404, f"대화를 찾을 수 없습니다: {conv_id}")
    return c


@router.delete("/{conv_id}", summary="대화 삭제")
def delete_conversation(conv_id: ConvId, r: Repository = Depends(repo)):
    if not r.delete_conversation(conv_id):
        raise HTTPException(404, f"대화를 찾을 수 없습니다: {conv_id}")
    return {"deleted": conv_id}
