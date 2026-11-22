"""/api/data — 분석 데이터 CRUD + 요약(프롬프트 주입용) + 통계·내보내기(보너스)."""
from __future__ import annotations

import csv
import io
import json
from datetime import date as Date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response

from ..db import Repository
from ..deps import repo, summaries
from ..schemas import DataCreate, DataList, DataRecord, DataUpdate, Statistics, Summary
from ..services.summary import SummaryService

router = APIRouter(prefix="/api/data", tags=["data"])

DocId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$", description="문서 ID")]


def _not_found(doc_id: str) -> HTTPException:
    return HTTPException(404, f"데이터를 찾을 수 없습니다: {doc_id}")


@router.post("", response_model=DataRecord, status_code=201, summary="새 데이터 추가")
def create_data(body: DataCreate, r: Repository = Depends(repo), s: SummaryService = Depends(summaries)):
    """같은 날짜가 이미 있으면 409. 시계열은 하루 1개 값을 전제로 요약을 계산하기 때문이다."""
    date = body.date.isoformat()
    if r.find_data_by_date(date):
        raise HTTPException(409, f"{date} 데이터가 이미 있습니다. 수정(PUT)을 사용하세요")
    row = r.create_data({"date": date, "value": body.value, "memo": body.memo})
    s.invalidate()
    return row


@router.get("", response_model=DataList, summary="데이터 목록 조회")
def list_data(
    start: Date | None = Query(None, description="시작일(포함)"),
    end: Date | None = Query(None, description="종료일(포함)"),
    order: Literal["asc", "desc"] = Query("desc", description="날짜 정렬"),
    limit: int | None = Query(None, ge=1, le=2000, description="최대 개수"),
    s: SummaryService = Depends(summaries),
):
    rows = s.rows()   # 캐시된 전체 목록(요약과 같은 원본)에서 거른다 → Firestore 읽기 절약
    lo, hi = (start.isoformat() if start else None), (end.isoformat() if end else None)
    rows = [x for x in rows if (lo is None or x["date"] >= lo) and (hi is None or x["date"] <= hi)]
    if order == "desc":
        rows = rows[::-1]
    if limit:
        rows = rows[:limit]
    return {"count": len(rows), "items": rows}


@router.get("/summary", response_model=Summary, summary="데이터 요약(프롬프트 주입용)")
def get_summary(s: SummaryService = Depends(summaries)):
    """기간·개수·평균/최대/최소·최근 추세. /api/chat 은 이 값을 시스템 프롬프트에 넣는다."""
    return s.summary()


@router.get("/statistics", response_model=Statistics, summary="심화 통계(보너스)")
def get_statistics(s: SummaryService = Depends(summaries)):
    """요일별·월별 평균, 변동성, 상위 5일, 7일 이동평균 시계열(그래프용)."""
    return s.statistics()


@router.get("/export", summary="데이터 내보내기(CSV/JSON, 보너스)")
def export_data(format: Literal["csv", "json"] = "csv", s: SummaryService = Depends(summaries)):
    rows = [{"date": x["date"], "value": int(x["value"]) if float(x["value"]).is_integer() else x["value"],
             "memo": x.get("memo", "")} for x in s.rows()]
    if format == "json":
        body = json.dumps(rows, ensure_ascii=False, indent=2).encode()
        media = "application/json"
    else:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["date", "value", "memo"])
        w.writeheader()
        w.writerows(rows)
        body = ("﻿" + buf.getvalue()).encode()       # BOM: 엑셀에서 한글 메모가 깨지지 않게
        media = "text/csv; charset=utf-8"
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="ai-interest-data.{format}"'})


@router.put("/{doc_id}", response_model=DataRecord, summary="데이터 수정")
def update_data(doc_id: DocId, body: DataUpdate, r: Repository = Depends(repo),
                s: SummaryService = Depends(summaries)):
    """보낸 필드만 바꾼다. 날짜를 바꿀 때 그 날짜가 다른 문서에 이미 있으면 409."""
    changes = body.changes()
    if not changes:
        raise HTTPException(422, "바꿀 필드(date, value, memo)를 하나 이상 보내세요")
    if "date" in changes:
        changes["date"] = changes["date"].isoformat()
        other = r.find_data_by_date(changes["date"])
        if other and other["id"] != doc_id:
            raise HTTPException(409, f"{changes['date']} 데이터가 이미 있습니다")
    row = r.update_data(doc_id, changes)
    if row is None:
        raise _not_found(doc_id)
    s.invalidate()
    return row


@router.delete("/{doc_id}", summary="데이터 삭제")
def delete_data(doc_id: DocId, r: Repository = Depends(repo), s: SummaryService = Depends(summaries)):
    if not r.delete_data(doc_id):
        raise _not_found(doc_id)
    s.invalidate()
    return {"deleted": doc_id}
