import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from core.data.history import load_horse_history


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        horse_name = (params.get("horse_name") or [""])[0].strip()
        exclude_course_id = (params.get("exclude_course_id") or [None])[0]

        if not horse_name:
            return self.send(400, {
                "error": "horse_name requis"
            })

        try:
            history = load_horse_history(
                horse_name,
                exclude_course_id=exclude_course_id,
            )

            return self.send(200, {
                "horse_name": horse_name,
                "history": history,
                "count": len(history),
            })

        except Exception as exc:
            return self.send(500, {
                "error": str(exc)
            })

    def send(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )
        self.end_headers()
        self.wfile.write(body)
