"""seed CSV(365일) → Firestore `data` 컬렉션 적재.

  cd backend
  python -m scripts.seed            # 이미 있는 날짜는 건너뜀
  python -m scripts.seed --reset    # data 컬렉션을 비우고 다시 적재(확인 질문 있음)

backend/.env 의 FIREBASE_SERVICE_ACCOUNT_JSON(또는 _PATH)을 사용한다.
"""
from __future__ import annotations

import argparse
import sys

from app.config import load_settings
from app.db import FirestoreRepository
from app.seed import SEED_CSV, load_seed_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="data 컬렉션 전체 삭제 후 적재")
    args = ap.parse_args()

    settings = load_settings()
    if not settings.use_firestore:
        sys.exit("FIREBASE_SERVICE_ACCOUNT_JSON 또는 FIREBASE_SERVICE_ACCOUNT_PATH 를 backend/.env 에 설정하세요")
    repo = FirestoreRepository(settings)
    existing = repo.list_data()

    if args.reset and existing:
        if input(f"data 컬렉션 {len(existing)}건을 삭제합니다. 계속할까요? [y/N] ").lower() != "y":
            sys.exit("취소했습니다")
        for r in existing:
            repo.delete_data(r["id"])
        existing = []

    have = {r["date"] for r in existing}
    rows = [r for r in load_seed_rows() if r["date"] not in have]
    n = repo.create_data_bulk(rows) if rows else 0
    print(f"{SEED_CSV.name}: 새로 {n}건 적재, 기존 {len(have)}건 유지 → 총 {len(have) + n}건")


if __name__ == "__main__":
    main()
