"""데이터 요약·통계 계산(순수 함수) + 캐시.

요약은 채팅마다 시스템 프롬프트에 들어가므로 매번 Firestore 전체를 읽으면
읽기 횟수(무료 50,000회/일)가 금방 찬다. 그래서 계산 결과를 메모리에 두고,
데이터가 추가·수정·삭제될 때만 버린다(SummaryService.invalidate).
"""
from __future__ import annotations

import statistics as st
import threading
from collections import defaultdict
from datetime import date as Date

from ..db import Repository
from ..schemas import (DataRecord, Extreme, Metrics, MonthlyPoint, SeriesPoint, Statistics, Summary, Trend,
                       WeekdayPoint)

TREND_WINDOW = 30          # 최근 30일 vs 직전 30일
TREND_THRESHOLD = 5.0      # ±5% 이내면 "유지"
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _d(r: dict) -> Date:
    v = r["date"]
    return v if isinstance(v, Date) else Date.fromisoformat(v)


def _r1(x: float) -> float:
    return round(float(x), 1)


def compute_trend(values: list[float], window: int = TREND_WINDOW, threshold: float = TREND_THRESHOLD) -> Trend:
    """최근 window 개 평균이 직전 window 개 평균보다 몇 % 변했나.

    하루치 비교는 스파이크·요일 효과에 휘둘리므로 30일 평균끼리 비교한다.
    """
    if len(values) < window * 2:
        return Trend(direction="데이터 부족", change_pct=None, recent_avg=None, previous_avg=None,
                     label=f"데이터 부족 (추세 판단에 최소 {window * 2}개 필요)")
    recent = st.fmean(values[-window:])
    prev = st.fmean(values[-window * 2:-window])
    if prev == 0:
        pct = None
        direction = "상승" if recent > 0 else "유지"
    else:
        pct = (recent / prev - 1) * 100
        direction = "상승" if pct > threshold else "하락" if pct < -threshold else "유지"
    pct_txt = "" if pct is None else f" {pct:+.1f}%"
    return Trend(direction=direction, change_pct=None if pct is None else round(pct, 1),
                 recent_avg=_r1(recent), previous_avg=_r1(prev),
                 label=f"{direction} (최근 {window}일 평균{pct_txt}, 직전 {window}일 대비)")


def monthly(rows: list[dict]) -> list[MonthlyPoint]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        buckets[_d(r).strftime("%Y-%m")].append(float(r["value"]))
    return [MonthlyPoint(month=m, average=_r1(st.fmean(v)), total=_r1(sum(v)), days=len(v))
            for m, v in sorted(buckets.items())]


def compute_summary(rows: list[dict]) -> Summary:
    """rows 는 날짜 오름차순."""
    if not rows:
        return Summary(period="데이터 없음", start=None, end=None, count=0, metrics=None,
                       trend=compute_trend([]), latest=None, monthly=[])
    values = [float(r["value"]) for r in rows]
    hi = max(rows, key=lambda r: r["value"])
    lo = min(rows, key=lambda r: r["value"])
    metrics = Metrics(
        total=_r1(sum(values)), average=_r1(st.fmean(values)), median=_r1(st.median(values)),
        max=Extreme(value=hi["value"], date=_d(hi)), min=Extreme(value=lo["value"], date=_d(lo)),
        std=_r1(st.pstdev(values)),
    )
    start, end = _d(rows[0]), _d(rows[-1])
    return Summary(period=f"{start} ~ {end}", start=start, end=end, count=len(rows), metrics=metrics,
                   trend=compute_trend(values), latest=DataRecord(**rows[-1]), monthly=monthly(rows)[-6:])


def compute_statistics(rows: list[dict], top: int = 5) -> Statistics:
    values = [float(r["value"]) for r in rows]
    changes = [(b / a - 1) * 100 for a, b in zip(values, values[1:]) if a > 0]
    by_wd: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_wd[_d(r).weekday()].append(float(r["value"]))
    series = []
    for i, r in enumerate(rows):
        win = values[max(0, i - 6):i + 1]
        series.append(SeriesPoint(date=_d(r), value=values[i], ma7=_r1(st.fmean(win)) if len(win) == 7 else None))
    return Statistics(
        count=len(rows),
        volatility_pct=round(st.pstdev(changes), 1) if len(changes) >= 2 else None,
        weekday=[WeekdayPoint(weekday=WEEKDAYS[w], average=_r1(st.fmean(by_wd[w]))) for w in sorted(by_wd)],
        monthly=monthly(rows),
        top_days=[DataRecord(**r) for r in sorted(rows, key=lambda r: r["value"], reverse=True)[:top]],
        series=series,
    )


def summary_to_prompt(s: Summary) -> str:
    """시스템 프롬프트에 넣을 요약 블록. 숫자는 읽기 쉽게 천 단위 쉼표."""
    if s.count == 0 or s.metrics is None:
        return "- 저장된 데이터가 없습니다."
    m = s.metrics
    lines = [
        f"- 데이터 기간: {s.period}",
        f"- 총 레코드: {s.count}개 (하루 1개)",
        f"- 단위: {s.unit}",
        f"- 주요 지표: 합계 {m.total:,.0f} / 하루 평균 {m.average:,.0f} / 중앙값 {m.median:,.0f} / "
        f"최대 {m.max.value:,.0f} ({m.max.date}) / 최소 {m.min.value:,.0f} ({m.min.date}) / 표준편차 {m.std:,.0f}",
        f"- 최근 트렌드: {s.trend.label}",
    ]
    if s.latest:
        memo = f", 메모: {s.latest.memo}" if s.latest.memo else ""
        lines.append(f"- 가장 최근 값: {s.latest.date} = {s.latest.value:,.0f}{memo}")
    if s.monthly:
        lines.append("- 최근 월평균: " + ", ".join(f"{p.month} {p.average:,.0f}" for p in s.monthly))
    return "\n".join(lines)


class SummaryService:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self._rows: list[dict] | None = None
        self._summary: Summary | None = None
        self._stats: Statistics | None = None
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        with self._lock:
            self._rows = self._summary = self._stats = None

    def rows(self) -> list[dict]:
        with self._lock:
            if self._rows is None:
                self._rows = self._repo.list_data()
            return self._rows

    def summary(self) -> Summary:
        rows = self.rows()
        with self._lock:
            if self._summary is None:
                self._summary = compute_summary(rows)
            return self._summary

    def statistics(self) -> Statistics:
        rows = self.rows()
        with self._lock:
            if self._stats is None:
                self._stats = compute_statistics(rows)
            return self._stats
