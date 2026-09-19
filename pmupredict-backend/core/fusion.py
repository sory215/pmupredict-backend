"""Fusion IA + presse + communauté avec score final et probabilité normalisée."""
from __future__ import annotations
import os,logging
import numpy as np
from supabase import create_client,Client
from core.data.db import fetch_all
from core.data.timeutils import today_local
log=logging.getLogger("fusion");logging.basicConfig(level=logging.INFO)
URL=os.environ["SUPABASE_URL"];KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"];supabase:Client=create_client(URL,KEY)
WEIGHTS={"ia":float(os.getenv("WEIGHT_IA","0.5")),"presse":float(os.getenv("WEIGHT_PRESSE","0.3")),"communaute":float(os.getenv("WEIGHT_COMMUNAUTE","0.2"))}

def rank_score(rank,n):return max(0.0,(n-rank+1)/n) if n>1 else 1.0

def ia(course_id):
    rows=supabase.table("predictions").select("partant_id,score,confiance").eq("course_id",course_id).execute().data
    return {r["partant_id"]:r for r in rows}

def external(course_id,source,ids,n):
    rows=supabase.table("pronostics_externes").select("partant_id,rang_propose,pronostiqueur_id,pronostiqueurs(points)").eq("course_id",course_id).eq("source",source).execute().data
    sums={i:0.0 for i in ids}; weights={i:0.0 for i in ids}
    for r in rows:
        pid=r["partant_id"]; w=1.0
        if source=="communaute":w=1+max(0,float((r.get("pronostiqueurs") or {}).get("points",0) or 0))/100
        sums[pid]=sums.get(pid,0)+rank_score(int(r["rang_propose"]),n)*w;weights[pid]=weights.get(pid,0)+w
    return {i:(sums[i]/weights[i] if weights[i] else 0.0) for i in ids}

def _softmax(x):
    a=np.asarray(x,float);a-=np.max(a);e=np.exp(np.clip(a,-50,50));return e/e.sum() if e.sum() else np.ones(len(a))/len(a)

def calculer_fusion_course(course_id):
    ids=[r["id"] for r in supabase.table("partants").select("id").eq("course_id",course_id).execute().data];n=len(ids)
    if not n:return []
    s_ia=ia(course_id);s_p=external(course_id,"presse",ids,n);s_c=external(course_id,"communaute",ids,n)
    rows=[]
    for pid in ids:
        # Si IA absente, son poids est redistribué entre les sources réellement présentes.
        raw={"ia":float(s_ia.get(pid,{}).get("score",0)),"presse":s_p.get(pid,0),"communaute":s_c.get(pid,0)}
        active=[k for k,v in raw.items() if v>0 or (k=="ia" and pid in s_ia)]
        den=sum(WEIGHTS[k] for k in active) or 1
        final=sum(WEIGHTS[k]*raw[k] for k in active)/den
        rows.append({"partant_id":pid,"score_ia":raw["ia"],"score_presse":raw["presse"],"score_communaute":raw["communaute"],"score_final":float(final),"poids_utilises":{k:WEIGHTS[k]/den if k in active else 0 for k in WEIGHTS}})
    # Convertit le score de fusion en probabilité cohérente qui somme à 1 dans la course.
    probs=_softmax([r["score_final"] for r in rows])
    for i,r in enumerate(sorted(rows,key=lambda x:x["score_final"],reverse=True),1):r["rang_final"]=i;r["probabilite_estimee"]=float(probs[rows.index(r)])
    return rows

def sauvegarder_fusion(course_id,rows):
    for r in rows:
        p=r["probabilite_estimee"];fair=round(1/p,2) if p>0 else None
        supabase.table("pronostics_fusion").upsert({"course_id":course_id,"partant_id":r["partant_id"],"score_ia":r["score_ia"],"score_presse":r["score_presse"],"score_communaute":r["score_communaute"],"score_final":r["score_final"],"rang_final":r["rang_final"],"poids_utilises":r["poids_utilises"],"probabilite_estimee":p,"cote_estimee":fair},on_conflict="course_id,partant_id").execute()

def update_pronostiqueur_performance(jour):
    courses=fetch_all("courses","id,reunion_id,statut",page_size=1000); reunions=fetch_all("reunions","id,date",page_size=1000); rd={r["id"]:r["date"] for r in reunions}
    done=[c for c in courses if c["statut"]=="terminee" and rd.get(c["reunion_id"])==jour]; updates=0
    for c in done:
        arr=fetch_all("arrivees","partant_id,position",course_id__eq=c["id"]);pos={a["partant_id"]:a["position"] for a in arr}
        tips=fetch_all("pronostics_externes","pronostiqueur_id,partant_id,rang_propose",course_id__eq=c["id"])
        by={}
        for t in tips:
            by.setdefault(t["pronostiqueur_id"],[]).append(t)
        for tid,rows in by.items():
            score=0
            for t in rows:
                p=pos.get(t["partant_id"]);r=t["rang_propose"]
                if p is None:continue
                score += 5 if (r==1 and p<=3) else 2 if p<=5 else 0
            old=supabase.table("pronostiqueurs").select("points,nb_pronostics").eq("id",tid).limit(1).execute().data
            if old:
                supabase.table("pronostiqueurs").update({"points":max(0,float(old[0].get("points",0))+score-1),"nb_pronostics":int(old[0].get("nb_pronostics",0))+1}).eq("id",tid).execute();updates+=1
    return {"date":jour,"tipsters_mis_a_jour":updates,"courses_analysees":len(done)}

def run_fusion_du_jour(jour=None):
    jour=jour or today_local().isoformat(); reunions=fetch_all("reunions","id,date",page_size=1000); ids=[r["id"] for r in reunions if r["date"]==jour]
    courses=[c for c in fetch_all("courses","id,reunion_id",page_size=1000) if c["reunion_id"] in ids];done=0
    for c in courses:
        rows=calculer_fusion_course(c["id"])
        if rows:sauvegarder_fusion(c["id"],rows);done+=1
    return {"date":jour,"courses_traitees":done,"courses_du_jour":len(courses)}

if __name__=="__main__":print(run_fusion_du_jour())
