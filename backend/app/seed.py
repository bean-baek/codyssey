"""seed/ai_interest_daily.csv 읽기 — Firestore 초기 적재(scripts/seed.py)와 메모리 모드 자동 적재에 쓴다."""
from __future__ import annotations

import csv
from pathlib import Path

SEED_CSV = Path(__file__).resolve().parent.parent / "seed" / "ai_interest_daily.csv"


def load_seed_rows(path: Path = SEED_CSV) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [{"date": r["date"], "value": float(r["value"]), "memo": r.get("memo", "")} for r in csv.DictReader(f)]
