"""Collecte de pronostics externes.
Les URLs sont obligatoirement configurées via variables d'environnement JSON;
aucune URL fictive n'est utilisée. Exemple de format:
PRONOSTICS_SOURCES_JSON=[{"nom":"Source","type":"presse","url":"https://..."}]
Chaque source doit retourner {"courses":[{"hippodrome_code":"...","reunion":1,"course":1,"pronostic":[4,7]}]}.
"""
from __future__ import annotations
import os,json,logging,requests
from dataclasses import dataclass
from supabase import create_client,Client
from core.data.timeutils import today_local
log=logging.getLogger("pronostics");logging.basicConfig(level=logging.INFO)
URL=os.environ["SUPABASE_URL"];KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"];supabase:Client=create_client(URL,KEY)
UA={"User-Agent":os.getenv("HTTP_USER_AGENT","pmupredict/1.0")}
@dataclass
class P:hippodrome_code:str;reunion_numero:int;course_numero:int;nom:str;type:str;site:str;classement:list[int];commentaire:str=""

def sources():
    raw=os.getenv("PRONOSTICS_SOURCES_JSON","[]")
    try:return json.loads(raw)
    except json.JSONDecodeError:raise RuntimeError("PRONOSTICS_SOURCES_JSON doit être un JSON valide")

def collect_source(src,jour):
    r=requests.get(src["url"],params={"date":jour},headers=UA,timeout=20);r.raise_for_status();data=r.json();out=[]
    for c in data.get("courses",[]):
        out.append(P(str(c.get("hippodrome_code","")),int(c.get("reunion",0)),int(c.get("course",0)),src["nom"],src.get("type","presse"),src["url"],list(map(int,c.get("pronostic",c.get("classement",[])))),c.get("commentaire","") or ""))
    return out

def course_id(p):
    h=supabase.table("hippodromes").select("id").eq("code",p.hippodrome_code).limit(1).execute().data
    if not h:return None
    r=supabase.table("reunions").select("id").eq("hippodrome_id",h[0]["id"]).eq("numero",p.reunion_numero).eq("date",today_local().isoformat()).limit(1).execute().data
    if not r:return None
    c=supabase.table("courses").select("id").eq("reunion_id",r[0]["id"]).eq("numero",p.course_numero).limit(1).execute().data
    return c[0]["id"] if c else None

def save(p):
    cid=course_id(p)
    if not cid:return False
    tip=supabase.table("pronostiqueurs").upsert({"nom":p.nom,"type":p.type,"site_source":p.site},on_conflict="nom,type").execute().data[0]
    for rank,num in enumerate(p.classement,1):
        q=supabase.table("partants").select("id").eq("course_id",cid).eq("numero",num).limit(1).execute().data
        if q:supabase.table("pronostics_externes").upsert({"course_id":cid,"pronostiqueur_id":tip["id"],"partant_id":q[0]["id"],"rang_propose":rank,"commentaire":p.commentaire,"source":p.type},on_conflict="course_id,pronostiqueur_id,partant_id").execute()
    return True

def run_pronostics_collection():
    jour=today_local().isoformat();items=[];errors=[]
    for src in sources():
        if not src.get("url"):continue
        try:items.extend(collect_source(src,jour))
        except Exception as e:errors.append(f"{src.get('nom','source')}: {e}")
    saved=sum(save(x) for x in items)
    return {"date":jour,"pronostics_recuperes":len(items),"pronostics_enregistres":saved,"erreurs":errors[:20]}
if __name__=="__main__":print(run_pronostics_collection())
