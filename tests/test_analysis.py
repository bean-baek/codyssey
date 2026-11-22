import numpy as np
import pandas as pd
import pytest

from src.analysis import (
    to_wide, flag_spikes, weekday_index, spike_decay_days, pct_change_window,
)


def _long(rows):
    return pd.DataFrame(rows, columns=["date", "platform", "views"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))


def test_to_wide_fills_gap_inside_lifetime_with_zero_but_keeps_pre_launch_nan():
    df = _long([("2024-01-02", "A", 5), ("2024-01-04", "A", 7),
                ("2024-01-01", "B", 1), ("2024-01-02", "B", 1),
                ("2024-01-03", "B", 1), ("2024-01-04", "B", 1)])
    w = to_wide(df)
    assert list(w.index) == list(pd.date_range("2024-01-01", "2024-01-04"))
    assert np.isnan(w.loc["2024-01-01", "A"])      # 문서가 생기기 전 → 결측 유지
    assert w.loc["2024-01-03", "A"] == 0           # 생긴 뒤 빈 날 → 조회수 0
    assert w["B"].tolist() == [1, 1, 1, 1]


def test_flag_spikes_marks_only_extreme_days():
    s = pd.Series([100.0] * 60 + [2000.0] + [100.0] * 10,
                  index=pd.date_range("2024-01-01", periods=71))
    s.iloc[::7] += 5  # 약간의 노이즈 — 대부분 일정해서 MAD=0인 경우도 다뤄야 한다
    flags = flag_spikes(s, window=28, z=5)
    assert flags.sum() == 1
    assert flags.idxmax() == pd.Timestamp("2024-03-01")


def test_flag_spikes_ignores_nan_prefix():
    s = pd.Series([np.nan] * 5 + [10.0, 11.0, 9.0] * 20)
    assert not flag_spikes(s, window=14, z=5).iloc[:5].any()


def test_weekday_index_is_ratio_to_own_weekly_mean():
    idx = pd.date_range("2024-01-01", periods=28)  # 2024-01-01 = 월요일
    s = pd.Series([200.0 if d.day_of_week < 5 else 100.0 for d in idx], index=idx)
    wi = weekday_index(s)
    assert wi.index.tolist() == list(range(7))
    assert wi[0] == pytest.approx(200 / (1200 / 7))
    assert wi[6] == pytest.approx(100 / (1200 / 7))


def test_spike_decay_days_counts_until_back_under_threshold():
    s = pd.Series([100.0] * 30 + [1000.0, 600.0, 300.0, 180.0, 140.0, 110.0] + [100.0] * 10,
                  index=pd.date_range("2024-01-01", periods=46))
    peak = pd.Timestamp("2024-01-31")
    # 기준선(피크 전 28일 중앙값)=100, 기준선 대비 1.5배(150) 아래로 내려가는 데 걸린 날
    assert spike_decay_days(s, peak, factor=1.5) == 4


def test_pct_change_window_compares_mean_of_two_windows():
    s = pd.Series([10.0] * 30 + [15.0] * 30, index=pd.date_range("2024-01-01", periods=60))
    assert pct_change_window(s, days=30) == pytest.approx(50.0)


def test_trim_unsettled_drops_days_before_series_reaches_stable_level():
    from src.analysis import trim_unsettled
    idx = pd.date_range("2024-01-01", periods=90)
    s = pd.Series([np.nan] * 5 + [2.0] * 40 + [300.0] * 45, index=idx)
    t = trim_unsettled(s, min_level=20, window=28)
    first = t.first_valid_index()
    assert first == pd.Timestamp("2024-01-01") + pd.Timedelta(days=45)   # 300이 시작된 날
    assert t.loc[first:].notna().all()
    assert t.loc[:first - pd.Timedelta(days=1)].isna().all()


def test_trim_unsettled_keeps_series_that_is_stable_from_start():
    from src.analysis import trim_unsettled
    s = pd.Series([500.0] * 60, index=pd.date_range("2024-01-01", periods=60))
    assert trim_unsettled(s).equals(s)
