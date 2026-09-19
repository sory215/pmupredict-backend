import os,re,json
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler
from supabase import create_client
supabase=create_client(os.environ["SUPABASE_URL"],os.environ["SUPABASE_ANON_KEY"])
class handler(BaseHTTPRequestHandler):
 def do_GET(self):
  m=re.search(r"/api/analyse/([^/]+)/?$",urlparse(self.path).path)
  if not m:return self.send(400,{"error":"course_id invalide"})
  cid=m.group(1)
  try:
   c=supabase.table("courses").select("id,numero,libelle,discipline,heure_depart,statut").eq("id",cid).limit(1).execute().data
   if not c:return self.send(404,{"error":"course introuvable"})
   rows=supabase.table("pronostics_fusion").select("score_ia,score_presse,score_communaute,score_final,rang_final,probabilite_estimee,cote_estimee,partants(numero,cheval_nom,jockey,cote_actuelle)").eq("course_id",cid).order("rang_final").execute().data
   return self.send(200,{"course":c[0],"partants":[{**(r.get("partants") or {}),**{k:r.get(k) for k in ("score_ia","score_presse","score_communaute","score_final","rang_final","probabilite_estimee","cote_estimee")}} for r in rows]})
  except Exception as e:return self.send(500,{"error":str(e)})
 def send(self,status,payload):
  b=json.dumps(payload,ensure_ascii=False,default=str).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Access-Control-Allow-Origin","*");self.end_headers();self.wfile.write(b)
