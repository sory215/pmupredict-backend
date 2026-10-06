import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from core.data.history import load_trainer_standings


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        try:
            limit = int((params.get("limit") or ["50"])[0])
        except ValueError:
            return self.send(400, {
                "error": "limit invalide"
            })

        exclude_course_id = (
            params.get("exclude_course_id") or [None]
        )[0]

        try:
            standings = load_trainer_standings(
                limit=limit,
                exclude_course_id=exclude_course_id,
            )

            return self.send(200, {
                "type": "trainer",
                "standings": standings,
                "count": len(standings),
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
