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
   c=supabase.table("courses").select(
    "id,numero,libelle,distance_m,discipline,heure_depart,statut,"
    "reunion_id,reunions(numero,date,hippodromes(nom,code))"
   ).eq("id",cid).limit(1).execute().data
   if not c:return self.send(404,{"error":"course introuvable"})

   rows=supabase.table("pronostics_fusion").select(
    "score_ia,score_presse,score_communaute,score_final,rang_final,"
    "probabilite_estimee,cote_estimee,partants(numero,cheval_nom,jockey,cote_actuelle)"
   ).eq("course_id",cid).order("rang_final").execute().data

   if rows:
    partants=[{**(r.get("partants") or {}),**{k:r.get(k) for k in (
      "score_ia","score_presse","score_communaute","score_final",
      "rang_final","probabilite_estimee","cote_estimee")}} for r in rows]
    return self.send(200,{"course":c[0],"partants":partants,"mode":"pronostics"})

   # Pas de pronostics disponibles : bascule sur les resultats historiques reels.
   partants_raw=supabase.table("partants").select(
    "id,numero,cheval_nom,jockey,entraineur,proprietaire,poids_kg,sexe,robe,age,place_corde"
   ).eq("course_id",cid).order("numero").execute().data or []

   arrivees=supabase.table("arrivees").select(
    "position,partant_id,ecart"
   ).eq("course_id",cid).order("position").execute().data or []

   arrivee_by_partant={a["partant_id"]:a for a in arrivees}

   partants=[]
   for p in partants_raw:
    a=arrivee_by_partant.get(p["id"])
    partants.append({**p,"position":a["position"] if a else None,"ecart":a.get("ecart") if a else None})

   partants.sort(key=lambda x:(x["position"] is None,x["position"]))

   return self.send(200,{"course":c[0],"partants":partants,"mode":"resultats"})
  except Exception as e:return self.send(500,{"error":str(e)})

 def send(self,status,payload):
  b=json.dumps(payload,ensure_ascii=False,default=str).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Access-Control-Allow-Origin","*");self.end_headers();self.wfile.write(b)
