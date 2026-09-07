import json,os,sys
from http.server import BaseHTTPRequestHandler

from lib.train import run_training

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secret=os.environ.get("CRON_SECRET")
        if not secret or self.headers.get("Authorization") != f"Bearer {secret}": return self._send(401,{"error":"unauthorized"})
        try:return self._send(200,run_training())
        except Exception as e:return self._send(500,{"error":str(e)})
    def _send(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False,default=str).encode()
        self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.end_headers();self.wfile.write(body)
