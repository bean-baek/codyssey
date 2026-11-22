"""정제·시계열 분석에 쓰는 순수 함수 모음 (그래프·파일 입출력 없음 → 테스트 가능)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """long(date, platform, views) → wide(날짜 × 플랫폼), 하루 간격으로 빈 날짜를 채운다.

    결측 처리 기준
    - Pageviews API는 조회수가 0인 날을 응답에서 **생략**한다.
      → 문서가 처음 등장한 날 이후의 빈 날짜는 0으로 채운다.
    - 문서가 생기기 전 기간은 "관심 0"이 아니라 "측정 불가"이므로 NaN으로 둔다.
    """
    w = df.pivot_table(index="date", columns="platform", values="views", aggfunc="sum")
    full = pd.date_range(w.index.min(), w.index.max(), freq="D")
    w = w.reindex(full)
    w.index.name = "date"
    for col in w.columns:
        first = w[col].first_valid_index()
        w.loc[first:, col] = w.loc[first:, col].fillna(0)
    return w


def flag_spikes(s: pd.Series, window: int = 28, z: float = 5.0) -> pd.Series:
    """이상치(스파이크) 표시: 직전 `window`일 중앙값 대비 robust z-score가 `z` 이상인 날.

    평균·표준편차 대신 중앙값·MAD를 쓰는 이유: 스파이크 자체가 평균과 표준편차를
    끌어올려 자기 자신을 가려 버리기 때문. 직전 구간만 보므로(미래 정보 없음)
    "그날 처음 튄 날"이 잡힌다.
    """
    past = s.shift(1).rolling(window, min_periods=window // 2)
    med = past.median()
    mad = past.apply(lambda x: np.nanmedian(np.abs(x - np.nanmedian(x))), raw=True)
    # MAD → 정규분포 표준편차 환산. 직전 구간이 거의 일정하면 MAD가 0이 되므로
    # 하한(중앙값의 5%, 최소 1회)을 둬서 0 나눗셈과 사소한 변동의 과잉 탐지를 함께 막는다.
    scale = np.maximum(1.4826 * mad, np.maximum(0.05 * med, 1.0))
    score = (s - med) / scale
    return (score >= z).fillna(False).astype(bool)


def weekday_index(s: pd.Series) -> pd.Series:
    """요일 지수(0=월 … 6=일). 각 주의 평균 대비 그 요일 조회수 비율의 중앙값.

    주 단위로 나눠 비교하므로 장기 추세(관심이 늘거나 줄어드는 흐름)의 영향이 빠진다.
    """
    s = s.dropna()
    s = s[s.index.to_period("W-SUN").to_timestamp() >= s.index.min()]
    week = s.index.to_period("W-SUN")
    weekly_mean = s.groupby(week).transform("mean")
    full_weeks = s.groupby(week).transform("size") == 7
    ratio = (s / weekly_mean)[full_weeks & (weekly_mean > 0)]
    return ratio.groupby(ratio.index.day_of_week).median()


def spike_decay_days(s: pd.Series, peak: pd.Timestamp, factor: float = 1.5,
                     baseline_days: int = 28, max_days: int = 120) -> int | None:
    """피크 이후 조회수가 "기준선 × factor" 아래로 처음 내려오기까지 걸린 일수.

    기준선 = 피크 직전 `baseline_days`일 중앙값. `max_days` 안에 안 내려오면 None.
    """
    base = s.loc[peak - pd.Timedelta(days=baseline_days): peak - pd.Timedelta(days=1)].median()
    after = s.loc[peak: peak + pd.Timedelta(days=max_days)]
    below = after[after < base * factor]
    if below.empty:
        return None
    return int((below.index[0] - peak).days)


def pct_change_window(s: pd.Series, days: int = 30, lag: int | None = None) -> float:
    """최근 `days`일 평균이 그 직전(또는 `lag`일 전) 같은 길이 구간 평균보다 몇 % 변했나."""
    lag = days if lag is None else lag
    s = s.dropna()
    recent = s.iloc[-days:].mean()
    prev = s.iloc[-days - lag: -lag].mean() if len(s) >= days + lag else np.nan
    return float((recent / prev - 1) * 100) if prev else float("nan")


def trim_unsettled(s: pd.Series, min_level: float = 20, window: int = 28) -> pd.Series:
    """문서가 '자리 잡기 전' 구간을 NaN으로 바꾼다.

    시작일 = 그날 조회수가 `min_level` 이상이고, 그날부터 `window`일 중앙값도 `min_level` 이상인 첫날.
    이유: 문서가 다른 문서로 넘겨 주는 넘겨주기(redirect)이거나 막 생긴 토막글일 때는
    하루 몇 회 수준이라 실제 관심을 대표하지 못한다. 이 구간을 그대로 두면
    '1년 전 대비 +600%' 같은 착시가 생긴다.
    """
    fwd_median = s[::-1].rolling(window, min_periods=window // 2).median()[::-1]
    ok = (s >= min_level) & (fwd_median >= min_level)
    if not ok.any():
        return s * np.nan
    start = ok.idxmax()
    out = s.copy()
    out.loc[:start - pd.Timedelta(days=1)] = np.nan
    return out
