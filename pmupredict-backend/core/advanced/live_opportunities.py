"""Détection de value bets basée sur la probabilité normalisée de la fusion."""
from __future__ import annotations
import os,logging
from supabase import create_client,Client
from core.data.db import fetch_all
log=logging.getLogger("opportunites");logging.basicConfig(level=logging.INFO)
URL=os.environ["SUPABASE_URL"];KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"];supabase:Client=create_client(URL,KEY)
MIN_EDGE=float(os.getenv("MIN_VALUE_EDGE","0.05")); MIN_ODDS=float(os.getenv("MIN_ODDS","1.20")); MAX_ODDS=float(os.getenv("MAX_ODDS","100"))

def detecter_opportunites_course(course_id):
    rows=supabase.table("pronostics_fusion").select("partant_id,score_final,probabilite_estimee,partants(cote_actuelle)").eq("course_id",course_id).execute().data;found=0
    for r in rows:
        p=r.get("partants") or {};odds=p.get("cote_actuelle");prob=r.get("probabilite_estimee")
        if odds is None or prob is None:continue
        odds=float(odds);prob=float(prob)
        if not MIN_ODDS<=odds<=MAX_ODDS or prob<=0:continue
        implied=1/odds;edge=prob-implied;fair=1/prob
        if edge>=MIN_EDGE:
            supabase.table("opportunites").upsert({"course_id":course_id,"partant_id":r["partant_id"],"cote_actuelle":odds,"cote_estimee":round(fair,2),"ecart_valeur":round(edge,4),"type":"value_bet" if edge<0.15 else "forte_value"},on_conflict="course_id,partant_id").execute();found+=1
        else:
            supabase.table("opportunites").delete().eq("course_id",course_id).eq("partant_id",r["partant_id"]).execute()
    return found

def run_detection_opportunites():
    courses=fetch_all("courses","id,statut",page_size=1000);total=0
    for c in courses:
        if c["statut"]!="terminee":total+=detecter_opportunites_course(c["id"])
    return {"courses_analysees":len(courses),"opportunites_detectees":total}
if __name__=="__main__":print(run_detection_opportunites())
