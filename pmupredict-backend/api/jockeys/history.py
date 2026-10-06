import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from core.data.history import load_jockey_history, load_jockey_stats


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)

        jockey_name = (params.get("jockey_name") or [""])[0].strip()
        exclude_course_id = (params.get("exclude_course_id") or [None])[0]

        if not jockey_name:
            return self.send(400, {
                "error": "jockey_name requis"
            })

        try:
            history = load_jockey_history(
                jockey_name,
                exclude_course_id=exclude_course_id,
            )

            stats = load_jockey_stats(
                jockey_name,
                exclude_course_id=exclude_course_id,
            )

            return self.send(200, {
                "jockey_name": jockey_name,
                "stats": {
                    key: value
                    for key, value in stats.items()
                    if key != "courses"
                },
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
