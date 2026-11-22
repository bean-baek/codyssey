"""a2-1 분석 결과 → a2-2 서비스용 (date, value, memo) 시계열 CSV.

  value : 그날 8개 플랫폼 영어 위키백과 조회수 합계 ("AI 생성 도구 관심도")
  memo  : 그날 스파이크(a2-1 의 robust z ≥ 5 규칙)가 난 플랫폼 이름. 없으면 빈칸
  기간  : 분석 마지막 날 기준 최근 365일

실행(저장소 루트에서, a2-1 의 pandas 환경 필요):
  python backend/scripts/build_seed.py
결과: backend/seed/ai_interest_daily.csv  (Render 배포 폴더 안에 두어 서버가 단독으로 읽을 수 있게 함)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.analysis import flag_spikes  # noqa: E402

DAYS = 365
OUT = ROOT / "backend" / "seed" / "ai_interest_daily.csv"


def main() -> None:
    wide = pd.read_csv(ROOT / "data" / "processed" / "daily_wide.csv", parse_dates=["date"], index_col="date")
    spikes = pd.DataFrame({c: flag_spikes(wide[c].dropna()) for c in wide.columns}).reindex(wide.index).fillna(False)
    recent = wide.iloc[-DAYS:]
    total = recent.sum(axis=1, min_count=1)
    memo = spikes.loc[recent.index].apply(lambda row: ", ".join(f"{p} 급증" for p in row.index[row.astype(bool)]),
                                          axis=1)
    out = pd.DataFrame({"date": recent.index.strftime("%Y-%m-%d"), "value": total.round().astype(int).values,
                        "memo": memo.values})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"{len(out)}행 ({out.date.iloc[0]} ~ {out.date.iloc[-1]}), 메모 있는 날 {(out.memo != '').sum()}일 → {OUT}")


if __name__ == "__main__":
    main()
