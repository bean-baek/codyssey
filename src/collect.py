"""Wikimedia Pageviews API에서 AI 이미지·영상 생성 플랫폼 문서의 일별 조회수를 수집한다.

실행:  python src/collect.py            (기본 기간: 2022-01-01 ~ 어제)
       python src/collect.py --end 20261119

API 문서: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/
- 인증 키가 필요 없다. 대신 Wikimedia 정책상 연락 가능한 User-Agent를 보내야 한다.
- agent=user 로 봇·크롤러 트래픽을 뺀 "사람" 조회수만 받는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "pageviews.csv"

API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "en.wikipedia/all-access/user/{article}/daily/{start}/{end}")
USER_AGENT = "codyssey-a2-1-trend-analysis/1.0 (educational project; python-requests)"

# 플랫폼 이름 → (위키백과 문서 제목, 분류)
PLATFORMS: dict[str, tuple[str, str]] = {
    "Midjourney":       ("Midjourney", "image"),
    "Stable Diffusion": ("Stable_Diffusion", "image"),
    "DALL-E":           ("DALL-E", "image"),
    "Flux":             ("Flux_(text-to-image_model)", "image"),
    "Sora":             ("Sora_(text-to-video_model)", "video"),
    "Runway":           ("Runway_(company)", "video"),
    "Kling":            ("Kling_AI", "video"),
    "Veo":              ("Veo_(text-to-video_model)", "video"),
}


def fetch_article(article: str, start: str, end: str, session: requests.Session) -> pd.DataFrame:
    """문서 하나의 일별 조회수. 문서가 없던 기간은 응답에 아예 행이 없다(→ 정제 단계에서 처리)."""
    url = API.format(article=article, start=start, end=end)
    for attempt in range(3):
        resp = session.get(url, timeout=30)
        if resp.status_code == 429:  # 요청 과다 → 잠깐 쉬고 재시도
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:  # 해당 기간 데이터 없음
            return pd.DataFrame(columns=["date", "views"])
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return pd.DataFrame({
            "date": [pd.to_datetime(i["timestamp"][:8]) for i in items],
            "views": [int(i["views"]) for i in items],
        })
    raise RuntimeError(f"{article}: 재시도 3회 모두 429")


def collect(start: str, end: str) -> pd.DataFrame:
    frames = []
    with requests.Session() as s:
        s.headers["User-Agent"] = USER_AGENT
        for name, (article, kind) in PLATFORMS.items():
            df = fetch_article(article, start, end, s)
            df["platform"], df["kind"], df["article"] = name, kind, article
            print(f"  {name:<17} {len(df):>5}행", file=sys.stderr)
            frames.append(df)
            time.sleep(0.3)  # API 예의상 간격
    out = pd.concat(frames, ignore_index=True)
    return out[["date", "platform", "kind", "article", "views"]].sort_values(["platform", "date"])


def main() -> None:
    yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", default="20220101")
    p.add_argument("--end", default=yesterday)
    a = p.parse_args()
    print(f"수집: {a.start} ~ {a.end}", file=sys.stderr)
    df = collect(a.start, a.end)
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_CSV, index=False, date_format="%Y-%m-%d")
    print(f"저장: {RAW_CSV.relative_to(ROOT)} ({len(df)}행)", file=sys.stderr)


if __name__ == "__main__":
    main()
