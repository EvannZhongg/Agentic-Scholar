from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


FRONTEND_DIR = Path(__file__).resolve().parent


class FrontendProxyHandler(SimpleHTTPRequestHandler):
    backend_base = "http://127.0.0.1:8000/v1"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            self._proxy_request()
            return
        self.send_error(405, "Only /api/* accepts POST.")

    def _proxy_request(self) -> None:
        parsed = urlparse(self.path)
        upstream_path = parsed.path.removeprefix("/api")
        target_url = self.backend_base.rstrip("/") + upstream_path
        if parsed.query:
            target_url = f"{target_url}?{parsed.query}"

        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length) if content_length else None
        headers: dict[str, str] = {}
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        request = Request(target_url, data=request_body, headers=headers, method=self.command)

        try:
            with urlopen(request, timeout=360) as response:
                response_body = response.read()
                response_type = response.headers.get("Content-Type", "application/json; charset=utf-8")
                self.send_response(response.status)
                self.send_header("Content-Type", response_type)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
        except HTTPError as error:
            response_body = error.read()
            response_type = error.headers.get("Content-Type", "application/json; charset=utf-8")
            self.send_response(error.code)
            self.send_header("Content-Type", response_type)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if response_body:
                self.wfile.write(response_body)
        except URLError as error:
            response_body = json.dumps(
                {
                    "detail": f"Proxy failed to reach backend: {error.reason}",
                    "backend_base": self.backend_base,
                }
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve the standalone frontend and proxy /api/* requests to the existing backend."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the frontend server.")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the frontend server.")
    parser.add_argument(
        "--backend-base",
        default="http://127.0.0.1:8000/v1",
        help="Backend API base, for example http://127.0.0.1:8000/v1",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    handler_cls = partial(FrontendProxyHandler, directory=str(FRONTEND_DIR))
    FrontendProxyHandler.backend_base = args.backend_base
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)
    print(f"Frontend server running at http://{args.host}:{args.port}")
    print(f"Proxying /api/* to {args.backend_base}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
