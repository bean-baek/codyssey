"""저장소 계층.

라우터·서비스는 Repository 인터페이스만 알고, 실제 저장소는 둘 중 하나다.
- FirestoreRepository : 배포·실사용. 서비스 계정 키(환경 변수)가 있을 때
- MemoryRepository    : 키 없이 로컬에서 띄우거나 테스트할 때(서버를 끄면 사라짐)

컬렉션 구조
  data/{autoId}           { date: "YYYY-MM-DD", value: float, memo: str, created_at, updated_at }
  conversations/{autoId}  { title, messages: [{role, content, created_at, tools}], message_count,
                            preview, created_at, updated_at }
date 를 문자열(YYYY-MM-DD)로 저장하는 이유: 사전순 = 날짜순이라 범위 조회·정렬이 그대로 된다.
"""
from __future__ import annotations

import copy
import json
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from .config import Settings

DATA = "data"
CONVERSATIONS = "conversations"
PREVIEW_LEN = 60


def now() -> datetime:
    return datetime.now(timezone.utc)


def _preview(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "assistant":
            return m["content"][:PREVIEW_LEN]
    return messages[-1]["content"][:PREVIEW_LEN] if messages else ""


class Repository(ABC):
    backend: str

    # data
    @abstractmethod
    def list_data(self, start: str | None = None, end: str | None = None,
                  limit: int | None = None, descending: bool = False) -> list[dict]: ...
    @abstractmethod
    def get_data(self, doc_id: str) -> dict | None: ...
    @abstractmethod
    def find_data_by_date(self, date: str) -> dict | None: ...
    @abstractmethod
    def create_data(self, record: dict) -> dict: ...
    @abstractmethod
    def create_data_bulk(self, records: list[dict]) -> int: ...
    @abstractmethod
    def update_data(self, doc_id: str, changes: dict) -> dict | None: ...
    @abstractmethod
    def delete_data(self, doc_id: str) -> bool: ...

    # conversations
    @abstractmethod
    def list_conversations(self, limit: int = 50) -> list[dict]: ...
    @abstractmethod
    def get_conversation(self, conv_id: str) -> dict | None: ...
    @abstractmethod
    def create_conversation(self, title: str, messages: list[dict]) -> dict: ...
    @abstractmethod
    def append_messages(self, conv_id: str, messages: list[dict], max_messages: int) -> dict | None: ...
    @abstractmethod
    def delete_conversation(self, conv_id: str) -> bool: ...


# ---------------------------------------------------------------- memory

class MemoryRepository(Repository):
    backend = "memory"

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._convs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def list_data(self, start=None, end=None, limit=None, descending=False):
        rows = [r for r in self._data.values()
                if (start is None or r["date"] >= start) and (end is None or r["date"] <= end)]
        rows.sort(key=lambda r: r["date"], reverse=descending)
        return [dict(r) for r in (rows[:limit] if limit else rows)]

    def get_data(self, doc_id):
        r = self._data.get(doc_id)
        return dict(r) if r else None

    def find_data_by_date(self, date):
        return next((dict(r) for r in self._data.values() if r["date"] == date), None)

    def create_data(self, record):
        with self._lock:
            doc_id = uuid.uuid4().hex[:20]
            t = now()
            row = {**record, "id": doc_id, "created_at": t, "updated_at": t}
            self._data[doc_id] = row
            return dict(row)

    def create_data_bulk(self, records):
        for r in records:
            self.create_data(r)
        return len(records)

    def update_data(self, doc_id, changes):
        with self._lock:
            if doc_id not in self._data:
                return None
            self._data[doc_id].update(changes, updated_at=now())
            return dict(self._data[doc_id])

    def delete_data(self, doc_id):
        with self._lock:
            return self._data.pop(doc_id, None) is not None

    def list_conversations(self, limit=50):
        rows = sorted(self._convs.values(), key=lambda c: c["updated_at"], reverse=True)[:limit]
        return [{k: v for k, v in c.items() if k != "messages"} for c in rows]

    def get_conversation(self, conv_id):
        c = self._convs.get(conv_id)
        return copy.deepcopy(c) if c else None

    def create_conversation(self, title, messages):
        with self._lock:
            conv_id = uuid.uuid4().hex[:20]
            t = now()
            c = {"id": conv_id, "title": title, "messages": list(messages), "message_count": len(messages),
                 "preview": _preview(messages), "created_at": t, "updated_at": t}
            self._convs[conv_id] = c
            return self.get_conversation(conv_id)

    def append_messages(self, conv_id, messages, max_messages):
        with self._lock:
            c = self._convs.get(conv_id)
            if c is None:
                return None
            c["messages"] = (c["messages"] + list(messages))[-max_messages:]
            c.update(message_count=len(c["messages"]), preview=_preview(c["messages"]), updated_at=now())
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id):
        with self._lock:
            return self._convs.pop(conv_id, None) is not None


# ---------------------------------------------------------------- firestore

class FirestoreRepository(Repository):
    backend = "firestore"

    def __init__(self, settings: Settings) -> None:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if settings.firebase_service_account_json:
            try:
                info: Any = json.loads(settings.firebase_service_account_json)
            except json.JSONDecodeError as e:
                raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON 이 올바른 JSON 이 아닙니다") from e
            cred = credentials.Certificate(info)
        else:
            cred = credentials.Certificate(settings.firebase_service_account_path)
        app = firebase_admin.initialize_app(cred) if not firebase_admin._apps else firebase_admin.get_app()
        self._db = firestore.client(app)
        self._fs = firestore

    def _doc(self, snap) -> dict:
        return {"id": snap.id, **snap.to_dict()}

    # data
    def list_data(self, start=None, end=None, limit=None, descending=False):
        q = self._db.collection(DATA)
        if start:
            q = q.where(filter=self._fs.FieldFilter("date", ">=", start))
        if end:
            q = q.where(filter=self._fs.FieldFilter("date", "<=", end))
        q = q.order_by("date", direction=self._fs.Query.DESCENDING if descending else self._fs.Query.ASCENDING)
        if limit:
            q = q.limit(limit)
        return [self._doc(s) for s in q.stream()]

    def get_data(self, doc_id):
        snap = self._db.collection(DATA).document(doc_id).get()
        return self._doc(snap) if snap.exists else None

    def find_data_by_date(self, date):
        q = self._db.collection(DATA).where(filter=self._fs.FieldFilter("date", "==", date)).limit(1)
        return next((self._doc(s) for s in q.stream()), None)

    def create_data(self, record):
        t = now()
        ref = self._db.collection(DATA).document()
        body = {**record, "created_at": t, "updated_at": t}
        ref.set(body)
        return {"id": ref.id, **body}

    def create_data_bulk(self, records):
        t = now()
        n = 0
        for i in range(0, len(records), 400):        # 배치 1회 최대 500건
            batch = self._db.batch()
            for r in records[i:i + 400]:
                batch.set(self._db.collection(DATA).document(), {**r, "created_at": t, "updated_at": t})
                n += 1
            batch.commit()
        return n

    def update_data(self, doc_id, changes):
        ref = self._db.collection(DATA).document(doc_id)
        if not ref.get().exists:
            return None
        ref.update({**changes, "updated_at": now()})
        return self.get_data(doc_id)

    def delete_data(self, doc_id):
        ref = self._db.collection(DATA).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # conversations
    def list_conversations(self, limit=50):
        q = (self._db.collection(CONVERSATIONS)
             .select(["title", "message_count", "preview", "created_at", "updated_at"])
             .order_by("updated_at", direction=self._fs.Query.DESCENDING).limit(limit))
        return [self._doc(s) for s in q.stream()]

    def get_conversation(self, conv_id):
        snap = self._db.collection(CONVERSATIONS).document(conv_id).get()
        return self._doc(snap) if snap.exists else None

    def create_conversation(self, title, messages):
        t = now()
        ref = self._db.collection(CONVERSATIONS).document()
        body = {"title": title, "messages": messages, "message_count": len(messages),
                "preview": _preview(messages), "created_at": t, "updated_at": t}
        ref.set(body)
        return {"id": ref.id, **body}

    def append_messages(self, conv_id, messages, max_messages):
        ref = self._db.collection(CONVERSATIONS).document(conv_id)
        transaction = self._db.transaction()

        @self._fs.transactional
        def _append(tx):
            snap = ref.get(transaction=tx)
            if not snap.exists:
                return None
            msgs = (snap.to_dict().get("messages", []) + messages)[-max_messages:]
            tx.update(ref, {"messages": msgs, "message_count": len(msgs),
                            "preview": _preview(msgs), "updated_at": now()})
            return True

        return self.get_conversation(conv_id) if _append(transaction) else None

    def delete_conversation(self, conv_id):
        ref = self._db.collection(CONVERSATIONS).document(conv_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


def make_repository(settings: Settings) -> Repository:
    return FirestoreRepository(settings) if settings.use_firestore else MemoryRepository()
