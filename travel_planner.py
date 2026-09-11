"""국내 여행 추천 CLI

날짜 하나를 받아서
  1) Gemini(LLM)에게 추천 도시 / 날씨 / 행사를 JSON으로 받고
  2) 그 도시로 Kakao Local에서 맛집을 검색한 뒤
  3) 둘을 합쳐 Gemini에게 여행 리포트(Markdown)를 쓰게 한다.

두 API를 SDK 없이 requests로 직접 호출한다.
Gemini는 POST(본문에 JSON), Kakao는 GET(주소에 쿼리스트링)이라
REST에서 메서드가 어떻게 갈리는지 코드에서 바로 보인다.
"""

import argparse
import datetime
import json
import os
import sys

import requests
from dotenv import load_dotenv

RESULTS_DIR = "results"

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

KAKAO_KEYWORD_ENDPOINT = "https://dapi.kakao.com/v2/local/search/keyword.json"

TIMEOUT = 30


# ---------------------------------------------------------------- 공통 도구


def log(step, message):
    """[1/3] 형태의 진행 로그를 출력한다."""
    print(f"{step} {message}", flush=True)


def add_error(errors, step, error_type, message):
    """오류를 목록에 쌓는다. 리포트의 errors 섹션과 원본 JSON에 그대로 실린다."""
    errors.append({"step": step, "type": error_type, "message": str(message)[:500]})


class ConfigError(Exception):
    """API 키가 없을 때처럼, 프로그램을 계속할 수 없는 설정 문제."""


# ---------------------------------------------------------------- CLI


def valid_date(text):
    """YYYY-MM-DD 형식인지 검사한다. 아니면 argparse가 사용법을 출력하고 종료한다."""
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"날짜 형식이 올바르지 않습니다: '{text}' (예: 2026-03-15)"
        )


def parse_args(argv=None):
    """CLI 옵션을 읽는다."""
    parser = argparse.ArgumentParser(
        prog="travel_planner.py",
        description="날짜를 받아 국내 여행 추천 리포트를 만든다.",
        epilog='예시: python travel_planner.py --date "2026-03-15"',
    )
    # 미션 본문은 -date, 예시는 --date 로 적혀 있어 둘 다 받도록 했다.
    parser.add_argument(
        "-date",
        "--date",
        dest="date",
        type=valid_date,
        required=True,
        metavar="YYYY-MM-DD",
        help="여행 날짜 (필수)",
    )
    parser.add_argument(
        "--cities",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="추천받을 도시 수 (보너스, 기본 1)",
    )
    parser.add_argument(
        "--places",
        type=int,
        default=5,
        help="도시당 검색할 맛집 수 (기본 5)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="캐시를 무시하고 API를 다시 호출한다",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="사용 가능한 Gemini 모델 목록만 출력하고 종료한다",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------- API 키


def load_keys():
    """.env 또는 환경변수에서 키를 읽는다. 없으면 ConfigError를 던진다."""
    load_dotenv()

    gemini = os.getenv("GEMINI_API_KEY", "").strip()
    kakao = os.getenv("KAKAO_REST_API_KEY", "").strip()

    missing = []
    if not gemini:
        missing.append("GEMINI_API_KEY")
    if not kakao:
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        raise ConfigError(
            "다음 API 키가 설정되어 있지 않습니다: " + ", ".join(missing) + "\n\n"
            "설정 방법 (둘 중 하나)\n"
            "  1) .env 파일 사용 (권장)\n"
            "       cp .env.example .env\n"
            "       그 다음 .env 를 열어 키를 붙여 넣으세요.\n"
            "  2) 환경변수로 현재 터미널 세션에만 적용\n"
            '       export GEMINI_API_KEY="YOUR_KEY"\n'
            '       export KAKAO_REST_API_KEY="YOUR_KEY"\n\n'
            "키 발급처\n"
            "  GEMINI_API_KEY     https://aistudio.google.com/apikey\n"
            "  KAKAO_REST_API_KEY https://developers.kakao.com → 내 애플리케이션 → 앱 키 → REST API 키\n\n"
            "키는 코드나 README, 결과 파일에 직접 적지 마세요."
        )

    return {
        "gemini": gemini,
        "kakao": kakao,
        "model": os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL,
    }
