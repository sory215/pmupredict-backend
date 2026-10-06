import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from core.data.history import load_trainer_horses


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        trainer_name = (params.get("trainer_name") or [""])[0].strip()
        exclude_course_id = (params.get("exclude_course_id") or [None])[0]

        if not trainer_name:
            return self.send(400, {
                "error": "trainer_name requis"
            })

        try:
            horses = load_trainer_horses(
                trainer_name,
                exclude_course_id=exclude_course_id,
            )

            return self.send(200, {
                "trainer_name": trainer_name,
                "horses": horses,
                "count": len(horses),
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
