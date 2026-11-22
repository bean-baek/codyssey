"""수집한 조회수로 정제 → 분석 → 그래프·통계 파일을 만든다.

실행:  python src/analyze.py
입력:  data/raw/pageviews.csv              (src/collect.py 가 만든 파일)
출력:  data/processed/daily_wide.csv       정제된 일별 표 (날짜 × 플랫폼)
       results/stats.json                 REPORT.md 의 모든 수치 출처
       figures/*.png                      리포트에 넣는 그래프 7장
       dashboard/data.json                보너스 대시보드용 데이터
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib import font_manager
from statsmodels.tsa.seasonal import STL

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.analysis import (  # noqa: E402
    flag_spikes, pct_change_window, spike_decay_days, to_wide, trim_unsettled, weekday_index,
)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "pageviews.csv"
FIG = ROOT / "figures"
OUT_STATS = ROOT / "results" / "stats.json"
OUT_WIDE = ROOT / "data" / "processed" / "daily_wide.csv"
OUT_DASH = ROOT / "dashboard" / "data.json"

IMAGE = ["Midjourney", "Stable Diffusion", "DALL-E", "Flux"]
VIDEO = ["Sora", "Runway", "Kling", "Veo"]
ORDER = IMAGE + VIDEO
COLORS = {  # 이미지 = 파랑 계열, 영상 = 주황 계열
    "Midjourney": "#1f4e9c", "Stable Diffusion": "#3a7bd5", "DALL-E": "#6fa8ef", "Flux": "#9cc3f5",
    "Sora": "#c2410c", "Runway": "#ea580c", "Kling": "#f59e0b", "Veo": "#fbbf24",
}
KIND_COLORS = {"image": "#2f6fd0", "video": "#e0661b"}
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
MIN_BASELINE = 20  # 스파이크 배수를 계산할 최소 기준선(하루 조회수)


def setup_font() -> None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ["AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic", "Noto Sans CJK KR"]:
        if cand in names:
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 110, "savefig.dpi": 150,
                         "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name: str) -> str:
    FIG.mkdir(exist_ok=True)
    path = FIG / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


# ---------------------------------------------------------------- 1. 데이터 기본 정보

def basic_info(raw: pd.DataFrame, wide_untrimmed: pd.DataFrame, wide: pd.DataFrame) -> dict:
    info = {}
    for p in ORDER:
        s_raw = raw[raw.platform == p]
        first, last = s_raw.date.min(), s_raw.date.max()
        expected = (last - first).days + 1
        info[p] = {
            "kind": "image" if p in IMAGE else "video",
            "article": s_raw.article.iloc[0],
            "start": first.date().isoformat(), "end": last.date().isoformat(),
            "rows_from_api": int(len(s_raw)),
            "missing_days_filled_with_0": int(expected - len(s_raw)),
            "analysis_start": wide[p].first_valid_index().date().isoformat(),
            "days_trimmed_unsettled": int(wide_untrimmed[p].notna().sum() - wide[p].notna().sum()),
            "missing_filled_after_trim": int((wide[p] == 0).sum()),
            "median_daily": float(wide[p].median()),
            "max_daily": int(wide[p].max()),
            "max_date": wide[p].idxmax().date().isoformat(),
        }
    return info


# ---------------------------------------------------------------- 2. 그래프

def fig_trend(wide: pd.DataFrame, spikes: pd.DataFrame) -> str:
    fig, axes = plt.subplots(2, 4, figsize=(16, 6.5), sharex=True)
    for ax, p in zip(axes.flat, ORDER):
        s = wide[p].dropna()
        ax.plot(s.index, s, color="#c9ced6", lw=0.6, label="일별")
        ax.plot(s.index, s.rolling(28, min_periods=7).mean(), color=COLORS[p], lw=2, label="28일 이동평균")
        sp = s[spikes[p].reindex(s.index, fill_value=False)]
        ax.scatter(sp.index, sp, s=10, color="#d1242f", zorder=3, label="스파이크(이상치)")
        ax.set_yscale("log")
        ax.set_title(f"{p}  ({'이미지' if p in IMAGE else '영상'})", fontsize=11, loc="left")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="y", alpha=0.3, which="major")
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, frameon=False, fontsize=10)
    fig.suptitle("플랫폼별 위키백과 일별 조회수 (로그 축) — 회색: 일별, 색 선: 28일 이동평균, 빨간 점: 스파이크",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return save(fig, "fig1_trend_moving_average.png")


def kind_totals(wide: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"image": wide[IMAGE].sum(axis=1, min_count=1),
                         "video": wide[VIDEO].sum(axis=1, min_count=1).fillna(0)})


def fig_share(wide: pd.DataFrame) -> tuple[str, dict]:
    monthly = kind_totals(wide).resample("MS").sum()
    monthly = monthly.iloc[:-1] if wide.index.max().day < 28 else monthly  # 덜 끝난 달 제외
    # 영상 문서가 하나도 없던 달은 '0%'가 아니라 측정 불가 → 그리지 않는다
    share = (monthly["video"] / monthly.sum(axis=1) * 100).where(monthly["video"] > 0)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [1.3, 1]})
    ax1.stackplot(monthly.index, monthly["image"] / 1e3, monthly["video"] / 1e3,
                  colors=[KIND_COLORS["image"], KIND_COLORS["video"]], labels=["이미지 생성 4종", "영상 생성 4종"], alpha=0.85)
    ax1.set_ylabel("월간 조회수 (천 회)")
    ax1.legend(loc="upper left", frameon=False)
    ax1.set_title("월간 조회수: 이미지 vs 영상", loc="left")
    ax2.plot(share.index, share, color=KIND_COLORS["video"], lw=2.2, marker="o", ms=3)
    ax2.axhline(50, color="#888", ls="--", lw=1)
    ax2.set_ylabel("영상 비중 (%)")
    ax2.set_ylim(0, 100)
    ax2.set_title("전체 중 영상 생성 플랫폼의 비중", loc="left")
    ax2.grid(alpha=0.3)
    cross = share[share >= 50]
    if not cross.empty:
        ax2.annotate(f"처음 50% 돌파: {cross.index[0]:%Y-%m}", (cross.index[0], cross.iloc[0]),
                     xytext=(-150, 20), textcoords="offset points", arrowprops={"arrowstyle": "->"})
    fig.tight_layout()
    yearly = kind_totals(wide).groupby(wide.index.year).sum()
    stats = {
        "video_share_by_month": {d.strftime("%Y-%m"): round(v, 1) for d, v in share.dropna().items()},
        "first_month_video_over_50": cross.index[0].strftime("%Y-%m") if not cross.empty else None,
        "months_video_over_50": int((share >= 50).sum()),
        "yearly_totals": {int(y): {"image": int(r.image), "video": int(r.video),
                                   "video_share_pct": round(r.video / (r.image + r.video) * 100, 1)}
                          for y, r in yearly.iterrows()},
    }
    return save(fig, "fig2_image_vs_video_share.png"), stats


def momentum(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for p in ORDER:
        s = wide[p].dropna()
        rows.append({
            "platform": p,
            "recent_90d_mean": round(float(s.iloc[-90:].mean()), 1),
            "chg_90d_vs_prev_90d_pct": round(pct_change_window(s, 90), 1),
            "chg_90d_vs_year_ago_pct": round(pct_change_window(s, 90, lag=365), 1),
            "volatility_cv_90d": round(float(s.iloc[-90:].std() / s.iloc[-90:].mean()), 2),
        })
    return pd.DataFrame(rows).set_index("platform")


def fig_momentum(m: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharey=True)
    order = m.sort_values("recent_90d_mean").index
    cols = [COLORS[p] for p in order]
    axes[0].barh(order, m.loc[order, "recent_90d_mean"], color=cols)
    axes[0].set_title("최근 90일 하루 평균 조회수", loc="left")
    for i, v in enumerate(m.loc[order, "recent_90d_mean"]):
        axes[0].text(v, i, f" {v:,.0f}", va="center", fontsize=9)
    for ax, col, title in [(axes[1], "chg_90d_vs_prev_90d_pct", "직전 90일 대비 변화율 (%)"),
                           (axes[2], "chg_90d_vs_year_ago_pct", "1년 전 같은 90일 대비 변화율 (%)")]:
        vals = m.loc[order, col]
        ax.barh(order, vals.fillna(0), color=["#1a7f37" if v > 0 else "#cf222e" for v in vals.fillna(0)])
        ax.axvline(0, color="#333", lw=0.8)
        ax.set_title(title, loc="left")
        lo, hi = min(vals.min(), 0), max(vals.max(), 0)
        ax.set_xlim(lo - (hi - lo) * 0.22, hi + (hi - lo) * 0.22)
        for i, v in enumerate(vals):
            ax.text(0 if np.isnan(v) else v, i, " 비교 불가(1년 미만)" if np.isnan(v) else f" {v:+.0f}% ",
                    va="center", fontsize=9, ha="left" if np.isnan(v) or v >= 0 else "right")
    fig.suptitle("지금 관심이 어디로 움직이나 — 최근 90일 기준", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return save(fig, "fig3_recent_momentum.png")


def spike_events(wide: pd.DataFrame, spikes: pd.DataFrame) -> list[dict]:
    """플랫폼마다 스파이크 '사건'(연속된 스파이크 날을 하나로 묶음)과 회복 일수."""
    events = []
    for p in ORDER:
        s = wide[p].dropna()
        f = spikes[p].reindex(s.index, fill_value=False)
        if not f.any():
            continue
        groups = (f != f.shift()).cumsum()[f]
        for _, g in groups.groupby(groups):
            seg = s.loc[g.index.min(): g.index.max() + pd.Timedelta(days=3)]
            peak = seg.idxmax()
            base = s.loc[peak - pd.Timedelta(days=28): peak - pd.Timedelta(days=1)].median()
            if not base >= MIN_BASELINE:  # 기준선이 너무 작으면 "몇 배"가 의미 없다 (NaN 포함)
                continue
            events.append({"platform": p, "start": g.index.min().date().isoformat(),
                           "peak": peak.date().isoformat(), "peak_views": int(s[peak]),
                           "baseline": float(base), "multiple": round(float(s[peak] / base), 1),
                           "days_to_1_5x_baseline": spike_decay_days(s, peak, 1.5)})
    return sorted(events, key=lambda e: -e["multiple"])


def fig_decay(wide: pd.DataFrame, events: list[dict]) -> str:
    big = [e for e in events if e["multiple"] >= 3]
    top_per_platform: dict[str, dict] = {}
    for e in big:
        top_per_platform.setdefault(e["platform"], e)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), gridspec_kw={"width_ratios": [1.5, 1]})
    for p, e in top_per_platform.items():
        peak = pd.Timestamp(e["peak"])
        win = wide[p].loc[peak - pd.Timedelta(days=7): peak + pd.Timedelta(days=60)]
        x = (win.index - peak).days
        ax.plot(x, (win / e["baseline"]).rolling(3, center=True, min_periods=1).mean(),
                color=COLORS[p], lw=2, label=f"{p} {e['peak']} (최대 ×{e['multiple']:.0f})")
    ax.axhline(1.5, color="#555", ls="--", lw=1)
    ax.text(60, 1.55, "기준선×1.5", ha="right", va="bottom", fontsize=9)
    ax.set_yscale("log")
    ax.set_xlabel("피크로부터 지난 날 수")
    ax.set_ylabel("기준선(피크 직전 28일 중앙값) 대비 배수, 3일 평균")
    ax.set_title("(a) 플랫폼별 최대 스파이크를 피크 날에 맞춰 겹침", loc="left")
    ax.legend(fontsize=9, frameon=False, loc="upper right")
    ax.grid(alpha=0.3)

    CAP = 125  # 120일 안에 회복 못 함
    for e in big:
        d = e["days_to_1_5x_baseline"]
        ax2.scatter(e["multiple"], CAP if d is None else max(d, 0.8), s=60, color=COLORS[e["platform"]],
                    edgecolor="white", zorder=3, marker="^" if d is None else "o")
    ax2.axhline(CAP, color="#999", lw=0.8, ls=":")
    ax2.text(3, CAP * 1.08, "▲ 120일 넘게 회복 안 됨 = 일시적 스파이크가 아니라 '수준 이동'", fontsize=9)
    ax2.set_xscale("log"); ax2.set_yscale("log")
    from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter
    for axis, ticks in [(ax2.xaxis, [3, 5, 10, 20, 40]), (ax2.yaxis, [1, 3, 7, 14, 30, 60, 120])]:
        axis.set_major_locator(FixedLocator(ticks)); axis.set_minor_locator(NullLocator())
        axis.set_major_formatter(ScalarFormatter())
    ax2.set_xlabel("스파이크 크기 (기준선 대비 배수)")
    ax2.set_ylabel("기준선×1.5 아래로 돌아오기까지 일수")
    ax2.set_title(f"(b) 3배 이상 스파이크 {len(big)}건: 크기 vs 회복 기간", loc="left")
    ax2.grid(alpha=0.3, which="both")
    ax2.set_ylim(0.7, CAP * 1.6)
    fig.suptitle("관심 폭발 후 얼마나 빨리 식나", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    return save(fig, "fig4_spike_decay.png")


def fig_weekday(wide: pd.DataFrame) -> tuple[str, dict]:
    wi = pd.DataFrame({p: weekday_index(wide[p]) for p in ORDER}).T
    wi.columns = WEEKDAYS
    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.imshow(wi.values, cmap="RdBu_r", vmin=0.8, vmax=1.2, aspect="auto")
    ax.set_xticks(range(7), WEEKDAYS)
    ax.set_yticks(range(len(ORDER)), ORDER)
    for i in range(len(ORDER)):
        for j in range(7):
            ax.text(j, i, f"{wi.iat[i, j]:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, label="그 주 평균 대비 배수")
    ax.set_title("요일 패턴 — 1.00보다 크면 그 주 평균보다 많이 찾아본 요일", loc="left")
    fig.tight_layout()
    stats = {p: {d: round(float(v), 3) for d, v in row.items()} for p, row in wi.iterrows()}
    return save(fig, "fig5_weekday_pattern.png"), stats


def fig_stl(wide: pd.DataFrame, platform: str = "Midjourney") -> tuple[str, dict]:
    s = np.log(wide[platform].dropna().clip(lower=1))
    res = STL(s, period=7, robust=True).fit()
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    for ax, (y, title, c) in zip(axes, [(np.exp(s), "원본 (일별 조회수)", "#888"),
                                        (np.exp(res.trend), "추세 (trend)", COLORS[platform]),
                                        (np.exp(res.seasonal), "주간 계절성 (배수)", "#7c3aed"),
                                        (np.exp(res.resid), "잔차/노이즈 (배수)", "#d1242f")]):
        ax.plot(y.index, y, color=c, lw=1 if title.startswith("원본") else 1.4)
        ax.set_title(title, loc="left", fontsize=11)
        ax.grid(alpha=0.3)
    axes[0].set_yscale("log"); axes[1].set_yscale("log")
    axes[2].axhline(1, color="#333", lw=0.6); axes[3].axhline(1, color="#333", lw=0.6)
    fig.suptitle(f"STL 시계열 분해 — {platform} (로그 변환 후 주기 7일)", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    var = lambda x: float(np.var(x))  # noqa: E731
    stats = {
        "platform": platform,
        "variance_share_pct": {k: round(var(v) / var(s) * 100, 1)
                               for k, v in [("trend", res.trend), ("seasonal", res.seasonal), ("resid", res.resid)]},
        "seasonal_amplitude_pct": round(float((np.exp(res.seasonal.iloc[-28:]).max()
                                               / np.exp(res.seasonal.iloc[-28:]).min() - 1) * 100), 1),
        "trend_peak": {"date": res.trend.idxmax().date().isoformat(), "views": round(float(np.exp(res.trend.max())))},
        "trend_latest": round(float(np.exp(res.trend.iloc[-1]))),
    }
    return save(fig, "fig6_stl_decomposition.png"), stats


def fig_forecast(wide: pd.DataFrame, platform: str = "Midjourney", horizon: int = 28) -> tuple[str, dict]:
    s = wide[platform].dropna()
    train, test = s.iloc[:-horizon], s.iloc[-horizon:]
    idx = test.index
    last_week = train.iloc[-7:].values
    drift = (train.iloc[-1] - train.iloc[-91]) / 90
    fc = {
        "단순(마지막 값 유지)": pd.Series(train.iloc[-1], index=idx),
        "28일 평균": pd.Series(train.iloc[-28:].mean(), index=idx),
        "계절 단순(지난주 같은 요일)": pd.Series(np.tile(last_week, horizon // 7 + 1)[:horizon], index=idx),
        "추세 연장(최근 90일 기울기)": pd.Series(train.iloc[-1] + drift * np.arange(1, horizon + 1), index=idx),
    }
    metrics = {k: {"MAE": round(float((v - test).abs().mean()), 1),
                   "MAPE_pct": round(float(((v - test).abs() / test).mean() * 100), 1)} for k, v in fc.items()}
    fig, ax = plt.subplots(figsize=(12, 5))
    hist = s.iloc[-120:]
    ax.plot(hist.index, hist, color="#333", lw=1.3, label="실제 조회수")
    styles = ["-", "--", "-", ":"]
    pal = ["#9ca3af", "#2563eb", "#16a34a", "#dc2626"]
    for (k, v), ls, c in zip(fc.items(), styles, pal):
        ax.plot(v.index, v, ls=ls, color=c, lw=2, label=f"{k} — MAPE {metrics[k]['MAPE_pct']}%")
    ax.axvspan(idx[0], idx[-1], color="#f3f4f6", zorder=0)
    ax.text(idx[0], ax.get_ylim()[1], " 예측 구간(마지막 28일, 학습에 안 씀)", va="top", fontsize=9)
    ax.set_title(f"베이스라인 예측 비교 — {platform}, 마지막 {horizon}일을 가려 두고 맞혀 보기", loc="left")
    ax.legend(fontsize=9, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    best = min(metrics, key=lambda k: metrics[k]["MAPE_pct"])
    return save(fig, "fig7_baseline_forecast.png"), {
        "platform": platform, "horizon_days": horizon,
        "test_period": f"{idx[0].date()} ~ {idx[-1].date()}", "metrics": metrics, "best": best}


# ---------------------------------------------------------------- main

def main() -> None:
    setup_font()
    raw = pd.read_csv(RAW, parse_dates=["date"])
    wide_untrimmed = to_wide(raw)[ORDER]
    wide = wide_untrimmed.apply(trim_unsettled)
    OUT_WIDE.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUT_WIDE, date_format="%Y-%m-%d")

    spikes = pd.DataFrame({p: flag_spikes(wide[p]) for p in ORDER})
    info = basic_info(raw, wide_untrimmed, wide)
    for p in ORDER:
        info[p]["spike_days"] = int(spikes[p].sum())

    figures = {}
    figures["trend"] = fig_trend(wide, spikes)
    figures["share"], share_stats = fig_share(wide)
    m = momentum(wide)
    figures["momentum"] = fig_momentum(m)
    events = spike_events(wide, spikes)
    figures["decay"] = fig_decay(wide, events)
    figures["weekday"], weekday_stats = fig_weekday(wide)
    figures["stl"], stl_stats = fig_stl(wide)
    figures["forecast"], fc_stats = fig_forecast(wide)

    yearly_mean = wide.groupby(wide.index.year).mean().round(0)
    decays = [e["days_to_1_5x_baseline"] for e in events if e["multiple"] >= 3 and e["days_to_1_5x_baseline"] is not None]
    stats = {
        "period": {"start": wide.index.min().date().isoformat(), "end": wide.index.max().date().isoformat(),
                   "days": int(len(wide)), "data_points": int(wide.notna().sum().sum())},
        "platforms": info,
        "yearly_mean_daily": {p: {int(y): (None if np.isnan(v) else int(v)) for y, v in yearly_mean[p].items()} for p in ORDER},
        "share": share_stats,
        "momentum": m.to_dict(orient="index"),
        "spike_events_top15": events[:15],
        "spike_decay_summary": {"events_over_3x": len([e for e in events if e["multiple"] >= 3]),
                                "median_days_to_recover": float(np.median(decays)) if decays else None,
                                "max_days_to_recover": max(decays) if decays else None},
        "weekday_index": weekday_stats,
        "stl": stl_stats,
        "forecast": fc_stats,
        "figures": figures,
    }
    OUT_STATS.parent.mkdir(exist_ok=True)
    OUT_STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2))

    OUT_DASH.parent.mkdir(exist_ok=True)
    OUT_DASH.write_text(json.dumps({
        "generated_from": "src/analyze.py",
        "dates": [d.strftime("%Y-%m-%d") for d in wide.index],
        "platforms": {p: {"kind": info[p]["kind"], "color": COLORS[p],
                          "views": [None if np.isnan(v) else int(v) for v in wide[p]],
                          "spikes": [bool(x) for x in spikes[p]]} for p in ORDER},
    }, ensure_ascii=False, separators=(",", ":")))

    print(f"데이터 포인트 {stats['period']['data_points']}개, 그래프 {len(figures)}장 → figures/, 통계 → results/stats.json")


if __name__ == "__main__":
    main()
