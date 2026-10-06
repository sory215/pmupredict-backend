import json
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from core.ai.service import analyser_course_id


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        m = re.search(r"/api/ai/([^/]+)/?$", urlparse(self.path).path)
        if not m:
            return self.send(400, {"error": "course_id invalide"})

        course_id = m.group(1)

        try:
            analyses = analyser_course_id(course_id)

            return self.send(
                200,
                {
                    "course_id": course_id,
                    "source": "pmupredict_ai",
                    "analyses": [asdict(analysis) for analysis in analyses],
                },
            )
        except ValueError as e:
            return self.send(404, {"error": str(e)})
        except Exception as e:
            return self.send(500, {"error": str(e)})

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
