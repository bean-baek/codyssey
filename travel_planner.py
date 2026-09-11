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
    parser.add_argument(
        "--check-keys",
        action="store_true",
        help="두 API 키가 실제로 동작하는지 점검하고 종료한다",
    )

    # --check-keys / --list-models 만 쓸 때는 --date 없이도 돌 수 있게 한다
    if argv is None:
        argv = sys.argv[1:]
    if any(flag in argv for flag in ("--check-keys", "--list-models")):
        for action in parser._actions:
            if action.dest == "date":
                action.required = False

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


# ---------------------------------------------------------------- 키 점검


def describe_key(value):
    """키 값을 노출하지 않고 형태만 알려 준다."""
    return f"{len(value)}자, 앞 4자 '{value[:4]}…'"


def check_keys(keys):
    """두 키가 실제로 동작하는지 최소 호출로 확인한다. 모두 정상이면 True."""
    all_ok = True

    # --- Kakao ---------------------------------------------------------
    print("[Kakao] REST API 키 점검")
    kakao = keys["kakao"]
    print(f"   형태: {describe_key(kakao)}")

    if kakao.lower().startswith("kakaoak"):
        print("   ✗ 'KakaoAK' 접두어까지 복사했습니다. 키 값만 남기세요.")
        all_ok = False
    elif len(kakao) != 32 or not all(c in "0123456789abcdefABCDEF" for c in kakao):
        print("   ! 카카오 앱 키는 보통 32자리 16진수입니다. 값이 잘렸는지 확인하세요.")

    try:
        response = requests.get(
            KAKAO_KEYWORD_ENDPOINT,
            headers={"Authorization": f"KakaoAK {kakao}"},
            params={"query": "서울 맛집", "size": 1},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            count = len(response.json().get("documents", []))
            print(f"   ✓ 정상 (테스트 검색 {count}건)")
        elif response.status_code == 401:
            print("   ✗ 401 인증 실패 — 키 값이 틀렸습니다.")
            print("     앱 설정 → 앱 키 에서 'REST API 키'를 다시 복사하세요.")
            print("     (네이티브 앱 키 / JavaScript 키 / Admin 키는 여기서 동작하지 않습니다)")
            all_ok = False
        elif response.status_code == 403:
            print("   ✗ 403 권한 없음 — 키는 맞지만 앱 설정이 막고 있습니다.")
            print("     앱 설정 → 플랫폼 에서 Web 플랫폼을 추가해 보세요.")
            all_ok = False
        else:
            print(f"   ✗ HTTP {response.status_code} — {response.text[:160]}")
            all_ok = False
    except requests.RequestException as exc:
        print(f"   ✗ 네트워크 오류: {exc}")
        all_ok = False

    # --- Gemini --------------------------------------------------------
    print("\n[Gemini] API 키 점검")
    gemini = keys["gemini"]
    print(f"   형태: {describe_key(gemini)}")
    if not gemini.startswith("AIza"):
        print("   ! Google AI Studio 키는 보통 'AIza' 로 시작합니다.")

    try:
        response = requests.get(
            GEMINI_MODELS_ENDPOINT,
            headers={"x-goog-api-key": gemini},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            names = [
                model.get("name", "").replace("models/", "")
                for model in response.json().get("models", [])
                if "generateContent" in model.get("supportedGenerationMethods", [])
            ]
            print(f"   ✓ 정상 (쓸 수 있는 모델 {len(names)}개)")
            if keys["model"] in names:
                print(f"   ✓ 설정된 모델 '{keys['model']}' 사용 가능")
            else:
                print(f"   ✗ 설정된 모델 '{keys['model']}' 을(를) 쓸 수 없습니다.")
                if names:
                    print(f"     .env 의 GEMINI_MODEL 을 이 중 하나로 바꾸세요: {', '.join(names[:5])}")
                all_ok = False
        elif response.status_code in (400, 401, 403):
            # 키가 틀리면 Gemini는 401이 아니라 400 INVALID_ARGUMENT 로 답한다
            print(f"   ✗ {response.status_code} 인증 실패 — 키가 유효하지 않습니다.")
            print("     https://aistudio.google.com/apikey 에서 다시 발급받으세요.")
            all_ok = False
        else:
            print(f"   ✗ HTTP {response.status_code} — {response.text[:160]}")
            all_ok = False
    except requests.RequestException as exc:
        print(f"   ✗ 네트워크 오류: {exc}")
        all_ok = False

    print("\n" + ("모두 정상입니다. 이제 --date 로 실행하세요." if all_ok else "위 ✗ 항목을 고친 뒤 다시 점검하세요."))
    return all_ok


# ---------------------------------------------------------------- Gemini (POST)


def call_gemini(keys, prompt, as_json=False):
    """Gemini에 POST로 프롬프트를 보내고 생성된 텍스트를 돌려준다.

    REST 관점에서 볼 것:
      - 메서드는 POST. 보낼 내용이 길고 구조가 있어서 URL이 아니라 '본문(body)'에 싣는다.
      - 인증은 x-goog-api-key 헤더. 키를 URL에 붙이면 로그에 남기 쉬워서 헤더를 쓴다.
      - as_json=True면 응답을 JSON 문자열로만 내놓도록 모델에 강제한다.
    """
    url = GEMINI_ENDPOINT.format(model=keys["model"])
    headers = {
        "x-goog-api-key": keys["gemini"],
        "Content-Type": "application/json",
    }
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    if as_json:
        body["generationConfig"]["responseMimeType"] = "application/json"

    response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)

    if response.status_code == 401 or response.status_code == 403:
        raise RuntimeError(f"인증 실패(HTTP {response.status_code}). GEMINI_API_KEY를 확인하세요.")
    if response.status_code == 429:
        raise RuntimeError("요청 한도 초과(HTTP 429). 잠시 후 다시 시도하세요.")
    if response.status_code == 404:
        raise RuntimeError(
            f"모델을 찾을 수 없습니다(HTTP 404): {keys['model']}\n"
            "  --list-models 로 사용 가능한 모델을 확인한 뒤 .env의 GEMINI_MODEL을 바꾸세요."
        )
    response.raise_for_status()

    payload = response.json()
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"응답에 생성 결과가 없습니다: {json.dumps(payload)[:200]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("응답 텍스트가 비어 있습니다.")
    return text


def list_models(keys):
    """사용 가능한 모델을 GET으로 조회해 출력한다. (POST와 대비되는 예)"""
    response = requests.get(
        GEMINI_MODELS_ENDPOINT,
        headers={"x-goog-api-key": keys["gemini"]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    print("generateContent 를 지원하는 모델:")
    for model in response.json().get("models", []):
        if "generateContent" in model.get("supportedGenerationMethods", []):
            print("  -", model.get("name", "").replace("models/", ""))


def extract_json(text):
    """모델이 ```json 울타리를 씌워 보내도 벗겨 내고 dict로 만든다."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[: -len("```")]
    cleaned = cleaned.strip()

    # 앞뒤에 설명이 붙어 있으면 가장 바깥 중괄호만 잘라 본다
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("JSON을 찾지 못했습니다.")
        cleaned = cleaned[start : end + 1]

    return json.loads(cleaned)


# ---------------------------------------------------------------- 1차 추천


REQUIRED_KEYS = {
    "recommended_city": str,
    "weather": str,
    "events": list,
    "reason": str,
}


def build_recommend_prompt(date, city_count, retry=False):
    """1차 추천용 프롬프트. retry=True면 형식만 다시 강조한다."""
    if retry:
        return (
            "아래 키를 가진 JSON 객체 하나만 출력하세요. 설명, 인사말, 코드블록 표시를 붙이지 마세요.\n"
            '{"recommended_city": "도시명", "weather": "날씨 요약", '
            '"events": ["행사1", "행사2"], "reason": "추천 이유"}\n'
            f"기준 날짜: {date.isoformat()} (대한민국 국내 여행)"
        )

    extra = ""
    if city_count > 1:
        extra = (
            f'\n- "recommended_cities": 추천 도시 {city_count}개를 문자열 배열로. '
            '첫 번째는 "recommended_city"와 같아야 합니다.'
        )

    return (
        f"당신은 대한민국 국내 여행 플래너입니다.\n"
        f"{date.isoformat()}에 떠나는 국내 여행지를 추천해 주세요.\n\n"
        "아래 키를 가진 JSON 객체 하나만 출력하세요.\n"
        '- "recommended_city": 도시/지역 이름 한 개 (예: "제주", "강릉")\n'
        '- "weather": 그 시기 일반적인 날씨 요약 한두 문장\n'
        '- "events": 그 시기 행사/축제 후보 1~3개를 담은 문자열 배열\n'
        '- "reason": 추천 근거 2~4문장'
        f"{extra}\n\n"
        "주의사항\n"
        "- 실제 개최가 확정되지 않은 행사는 '(일정 변동 가능)'처럼 단서를 달아 주세요.\n"
        "- JSON 외의 텍스트는 절대 출력하지 마세요."
    )


def validate_recommendation(data):
    """필수 키와 타입을 확인한다. 문제가 있으면 사유 문자열, 없으면 None."""
    if not isinstance(data, dict):
        return "최상위가 객체가 아닙니다."
    for key, expected in REQUIRED_KEYS.items():
        if key not in data:
            return f"필수 키 누락: {key}"
        if not isinstance(data[key], expected):
            return f"타입 불일치: {key} (기대 {expected.__name__})"
    if not data["recommended_city"].strip():
        return "recommended_city 가 비어 있습니다."
    return None


def get_recommendation(keys, date, city_count, errors):
    """1차 추천 JSON을 받아 온다. 파싱/검증 실패 시 재시도는 최대 1회."""
    for attempt in (1, 2):
        prompt = build_recommend_prompt(date, city_count, retry=(attempt == 2))
        try:
            raw = call_gemini(keys, prompt, as_json=True)
            data = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            add_error(errors, "llm_recommend", "PARSE_ERROR", f"{attempt}차 파싱 실패: {exc}")
            if attempt == 2:
                raise RuntimeError("1차 추천 JSON 파싱에 두 번 실패했습니다.") from exc
            log("   ", "JSON 파싱 실패 — 형식을 강조해 1회 재요청합니다.")
            continue
        except requests.RequestException as exc:
            add_error(errors, "llm_recommend", "NETWORK_ERROR", exc)
            raise RuntimeError(f"Gemini 요청 실패: {exc}") from exc

        problem = validate_recommendation(data)
        if problem is None:
            return data

        add_error(errors, "llm_recommend", "SCHEMA_ERROR", f"{attempt}차 검증 실패: {problem}")
        if attempt == 2:
            raise RuntimeError(f"1차 추천 JSON 검증에 두 번 실패했습니다: {problem}")
        log("   ", f"응답 형식 문제({problem}) — 1회 재요청합니다.")

    raise RuntimeError("1차 추천을 받지 못했습니다.")


# ---------------------------------------------------------------- Kakao Local (GET)


def search_restaurants(keys, city, size, errors):
    """도시 이름으로 맛집을 검색한다. 실패해도 예외를 던지지 않고 빈 리스트를 돌려준다.

    REST 관점에서 볼 것:
      - 메서드는 GET. '무엇을 달라'는 조회라서 조건을 URL 쿼리스트링에 붙인다.
      - 인증은 Authorization: KakaoAK <키> 헤더.
      - 같은 주소를 그대로 브라우저에 넣어도 결과를 볼 수 있는 게 GET의 특징이다.

    미션 정책상 이 단계의 실패는 프로그램을 멈추지 않는다.
    오류를 errors에 남기고 맛집을 '데이터 없음'으로 두고 계속 간다.
    """
    headers = {"Authorization": f"KakaoAK {keys['kakao']}"}
    params = {"query": f"{city} 맛집", "size": size, "page": 1}

    try:
        response = requests.get(
            KAKAO_KEYWORD_ENDPOINT, headers=headers, params=params, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        add_error(errors, "place_search", "NETWORK_ERROR", exc)
        log("   ", f"오류: 네트워크 문제로 맛집 검색 실패 ({exc.__class__.__name__})")
        return []

    if response.status_code in (401, 403):
        add_error(errors, "place_search", "AUTH_ERROR", f"HTTP {response.status_code}")
        log("   ", f"오류: 인증 실패({response.status_code}). KAKAO_REST_API_KEY를 확인하세요.")
        return []
    if response.status_code == 429:
        add_error(errors, "place_search", "QUOTA_ERROR", "HTTP 429")
        log("   ", "오류: 요청 한도 초과(429).")
        return []
    if response.status_code != 200:
        add_error(errors, "place_search", "HTTP_ERROR", f"HTTP {response.status_code}")
        log("   ", f"오류: 장소 API가 HTTP {response.status_code}를 반환했습니다.")
        return []

    try:
        documents = response.json().get("documents", [])
    except ValueError as exc:
        add_error(errors, "place_search", "PARSE_ERROR", exc)
        log("   ", "오류: 장소 API 응답을 JSON으로 읽지 못했습니다.")
        return []

    if not documents:
        add_error(errors, "place_search", "EMPTY_RESULT", f"0 results for query={params['query']}")
        log("   ", f"검색 결과 0건 ({city}) — '데이터 없음'으로 두고 다음 단계로 진행합니다.")
        return []

    return [normalize_place(document) for document in documents]


def normalize_place(document):
    """카카오 응답에서 미션이 요구하는 필드만 골라 담는다."""
    return {
        "name": document.get("place_name", ""),
        "address": document.get("road_address_name") or document.get("address_name", ""),
        "category": document.get("category_name", ""),
        "url": document.get("place_url", ""),
        "phone": document.get("phone", ""),
        "x": to_float(document.get("x")),  # 경도(lng)
        "y": to_float(document.get("y")),  # 위도(lat)
    }


def to_float(value):
    """카카오는 좌표를 문자열로 준다. 숫자로 바꾸되 실패하면 None."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 최종 리포트


def build_report_prompt(date, recommendation, places_by_city):
    """1차 추천과 맛집 목록을 함께 넘겨 Markdown 리포트를 요청한다."""
    return (
        f"당신은 여행 리포트를 쓰는 편집자입니다.\n"
        f"아래 두 자료만 근거로 {date.isoformat()} 국내 여행 리포트를 Markdown으로 작성하세요.\n\n"
        "[1차 추천 자료]\n"
        f"{json.dumps(recommendation, ensure_ascii=False, indent=2)}\n\n"
        "[맛집 검색 결과]\n"
        f"{json.dumps(places_by_city, ensure_ascii=False, indent=2)}\n\n"
        "작성 규칙\n"
        f"1. 첫 줄은 '# {date.isoformat()} 국내 여행 추천 리포트' 로 시작합니다.\n"
        "2. 다음 `##` 섹션을 이 순서로 모두 넣습니다: "
        "추천 지역 / 추천 이유 / 날씨 요약 / 행사·축제 / 맛집 추천 / 1일 일정 제안\n"
        "3. 맛집은 도시별로 묶고 이름·주소·카테고리를 적습니다. "
        "url이 있으면 이름에 링크를 겁니다.\n"
        "4. 맛집 목록이 비어 있는 도시는 '- 데이터 없음 (장소 검색 결과 0건)' 이라고만 적습니다.\n"
        "5. 1일 일정은 오전/오후/저녁 세 덩어리로 제안합니다.\n"
        "6. 위 자료에 없는 가게 이름, 주소, 전화번호를 지어내지 마세요.\n"
        "7. Markdown 본문만 출력하고 코드블록으로 감싸지 마세요."
    )


def generate_report(keys, date, recommendation, places_by_city, errors):
    """LLM으로 리포트를 만든다. 실패하면 로컬에서 조립한 리포트로 대체한다."""
    prompt = build_report_prompt(date, recommendation, places_by_city)
    try:
        text = call_gemini(keys, prompt)
    except (requests.RequestException, RuntimeError) as exc:
        add_error(errors, "llm_report", "GENERATION_ERROR", exc)
        log("   ", f"오류: 리포트 생성 실패 ({exc}) — 수집한 자료로 직접 작성합니다.")
        return fallback_report(date, recommendation, places_by_city), True

    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
    return text.strip(), False


def fallback_report(date, recommendation, places_by_city):
    """LLM 없이 수집한 자료만으로 만드는 대체 리포트."""
    lines = [f"# {date.isoformat()} 국내 여행 추천 리포트", ""]
    lines += ["## 추천 지역", "", f"- {', '.join(places_by_city.keys())}", ""]
    lines += ["## 추천 이유", "", recommendation.get("reason", "(없음)"), ""]
    lines += ["## 날씨 요약", "", recommendation.get("weather", "(없음)"), ""]

    lines += ["## 행사·축제", ""]
    events = recommendation.get("events") or []
    lines += [f"- {event}" for event in events] if events else ["- 데이터 없음"]
    lines.append("")

    lines += ["## 맛집 추천", ""]
    for city, places in places_by_city.items():
        lines += [f"### {city}", ""]
        if not places:
            lines += ["- 데이터 없음 (장소 검색 결과 0건)", ""]
            continue
        for place in places:
            name = f"[{place['name']}]({place['url']})" if place["url"] else place["name"]
            lines.append(f"- {name} — {place['address']} ({place['category']})")
        lines.append("")

    lines += [
        "## 1일 일정 제안",
        "",
        "- 오전: 숙소 주변 산책 후 대표 명소 한 곳",
        "- 오후: 행사/축제 일정 확인 후 참여, 이동은 여유 있게",
        "- 저녁: 위 맛집 목록에서 한 곳 방문",
        "",
        "> 이 리포트는 LLM 호출 실패로 수집한 자료만 사용해 자동 작성되었습니다.",
        "",
    ]
    return "\n".join(lines)


def append_errors_section(report, errors):
    """리포트 끝에 오류 요약 섹션을 붙인다. 비어 있어도 섹션은 남긴다."""
    lines = [report.rstrip(), "", "## 오류 요약(errors)", ""]
    if not errors:
        lines.append("- 없음")
    else:
        for error in errors:
            lines.append(f"- `{error['step']}` / `{error['type']}` — {error['message']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- 저장 / 캐시


def result_paths(date):
    """날짜 기준 결과 파일 두 개의 경로를 만든다."""
    stamp = date.isoformat()
    return (
        os.path.join(RESULTS_DIR, f"{stamp}_raw.json"),
        os.path.join(RESULTS_DIR, f"{stamp}_travel_plan.md"),
    )


def load_cache(json_path):
    """같은 날짜의 원본 JSON이 있으면 읽어 온다. (보너스: 캐싱)"""
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            cached = json.load(file)
    except (OSError, ValueError):
        return None
    if "recommendation" in cached and "places_by_city" in cached:
        return cached
    return None


def save_results(json_path, md_path, payload, report):
    """원본 JSON과 리포트 Markdown을 저장한다."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as file:
        file.write(report)


# ---------------------------------------------------------------- 진행 흐름


def pick_cities(recommendation, city_count):
    """추천 도시 목록을 정한다. (보너스: 복수 지역)"""
    cities = [recommendation["recommended_city"].strip()]

    if city_count > 1:
        for city in recommendation.get("recommended_cities") or []:
            name = str(city).strip()
            if name and name not in cities:
                cities.append(name)
    return cities[:city_count]


def main(argv=None):
    args = parse_args(argv)
    errors = []

    try:
        keys = load_keys()
    except ConfigError as exc:
        print(f"\n[설정 오류] {exc}\n", file=sys.stderr)
        return 1

    if args.check_keys:
        return 0 if check_keys(keys) else 1

    if args.list_models:
        try:
            list_models(keys)
        except requests.RequestException as exc:
            print(f"[오류] 모델 목록 조회 실패: {exc}", file=sys.stderr)
            return 1
        return 0

    json_path, md_path = result_paths(args.date)

    cached = None if args.refresh else load_cache(json_path)
    if cached:
        log("[캐시]", f"{json_path} 를 재사용합니다. (다시 호출하려면 --refresh)")
        recommendation = cached["recommendation"]
        places_by_city = cached["places_by_city"]
        errors = list(cached.get("errors", []))
    else:
        log("[1/3]", "1차 추천 생성 중(LLM)...")
        try:
            recommendation = get_recommendation(keys, args.date, args.cities, errors)
        except RuntimeError as exc:
            print(f"\n[오류] {exc}", file=sys.stderr)
            print("      추천 없이는 이후 단계를 진행할 수 없어 종료합니다.", file=sys.stderr)
            return 1
        log("     ", f"- recommended_city: \"{recommendation['recommended_city']}\"")

        cities = pick_cities(recommendation, args.cities)
        if len(cities) > 1:
            log("     ", f"- 추가 추천 도시: {', '.join(cities[1:])}")

        log("[2/3]", "맛집 검색 중(지도/장소 API)...")
        places_by_city = {}
        for city in cities:
            places = search_restaurants(keys, city, args.places, errors)
            places_by_city[city] = places
            if places:
                log("     ", f"- {city}: 맛집 {len(places)}곳 검색 완료")

    log("[3/3]", "최종 리포트 생성 중(LLM)...")
    report, used_fallback = generate_report(
        keys, args.date, recommendation, places_by_city, errors
    )
    report = append_errors_section(report, errors)
    log("     ", "- 리포트 생성 완료" + (" (대체 리포트)" if used_fallback else ""))

    payload = {
        "date": args.date.isoformat(),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "recommendation": recommendation,
        "places_by_city": places_by_city,
        "errors": errors,
    }

    try:
        save_results(json_path, md_path, payload, report)
    except OSError as exc:
        print(f"\n[오류] 결과 저장 실패: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"완료! {md_path} 를 확인하세요.")
    print(f"      원본 데이터는 {json_path} 에 있습니다.")
    if errors:
        print(f"      처리 중 {len(errors)}건의 오류가 있었습니다. 리포트의 '오류 요약' 섹션을 보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
