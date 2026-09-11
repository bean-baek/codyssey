"""로컬 개발 서버 — 정적 파일과 api/ 함수를 한 포트에서 서빙한다.

Vercel 없이도 전체 흐름을 확인하기 위한 것이다.
`vercel dev` 는 Vercel 로그인이 필요하지만 이건 필요 없다.

배포 동작을 그대로 흉내 내지는 않는다. 경로 매핑만 맞춘다.
  /api/revise → api/revise.py 의 handler
  /api/assist → api/assist.py 의 handler
  그 외        → 프로젝트 루트의 정적 파일

실행: python tools/dev_server.py [포트]
"""

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """.env 를 읽어 환경 변수로 올린다. 이미 설정된 값은 덮어쓰지 않는다."""
    path = ROOT / ".env"
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


load_env()
sys.path.insert(0, str(ROOT / "api"))
import assist  # noqa: E402
import revise  # noqa: E402

ROUTES = {"/api/revise": revise.handler, "/api/assist": assist.handler}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        route = ROUTES.get(self.path.split("?")[0])
        if route is None:
            self.send_error(404, "Not Found")
            return
        # api/ 의 핸들러는 BaseHTTPRequestHandler 하위 클래스라
        # self 를 그대로 넘겨 do_POST 를 빌려 쓸 수 있다.
        # 다만 do_POST 안에서 쓰는 _send 도 그 클래스에만 있으므로 함께 붙여 준다.
        self._send = route._send.__get__(self)
        route.do_POST(self)

    def end_headers(self):
        # 개발 중에는 CSS/JS 가 캐시되면 고친 게 안 보인다
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in (self.path or ""):
            sys.stderr.write("  %s\n" % (fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    base = os.environ.get("ANTHROPIC_BASE_URL") or "api.anthropic.com (기본)"
    print(f"결 개발 서버  http://localhost:{port}")
    print(f"  API 키   : {'설정됨 (' + str(len(key)) + '자)' if key else '없음 — AI 기능이 동작하지 않습니다'}")
    print(f"  엔드포인트: {base}")
    print(f"  모델     : revise={revise.MODEL_REVISE} / assist={assist.MODEL_ASSIST}")
    print("  중지: Ctrl+C\n")

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
