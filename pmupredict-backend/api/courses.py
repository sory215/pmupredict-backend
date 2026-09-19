import os,json
from datetime import date
from urllib.parse import urlparse,parse_qs
from http.server import BaseHTTPRequestHandler
from supabase import create_client

URL=os.environ["SUPABASE_URL"];KEY=os.environ["SUPABASE_ANON_KEY"];supabase=create_client(URL,KEY)

class handler(BaseHTTPRequestHandler):
 def do_GET(self):
  try:
   jour=parse_qs(urlparse(self.path).query).get("date",[date.today().isoformat()])[0]
   reunions=supabase.table("reunions").select("id,numero,date,hippodromes(nom,code)").eq("date",jour).execute().data or []
   if not reunions:
    latest=supabase.table("reunions").select("date").order("date",desc=True).limit(1).execute().data
    if latest:
     jour=latest[0]["date"]
     reunions=supabase.table("reunions").select("id,numero,date,hippodromes(nom,code)").eq("date",jour).execute().data or []
   ids=[r["id"] for r in reunions]
   courses=supabase.table("courses").select("id,reunion_id,numero,libelle,discipline,heure_depart,statut").in_("reunion_id",ids).order("heure_depart").execute().data if ids else []
   rm={r["id"]:r for r in reunions}
   for c in courses:
    c["reunions"]={"numero":rm[c["reunion_id"]]["numero"],"date":jour,"hippodromes":rm[c["reunion_id"]].get("hippodromes")}
   return self.send(200,{"date":jour,"courses":courses})
  except Exception as e:
   return self.send(500,{"error":str(e)})
 def send(self,status,payload):
  b=json.dumps(payload,ensure_ascii=False,default=str).encode()
  self.send_response(status)
  self.send_header("Content-Type","application/json; charset=utf-8")
  self.send_header("Access-Control-Allow-Origin","*")
  self.end_headers()
  self.wfile.write(b)
