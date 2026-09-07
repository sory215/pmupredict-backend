"""Prédiction du jour avec filtrage date et historique paginé."""
from __future__ import annotations
import os,io,pickle,logging
import json
import urllib.parse
import urllib.request
import pandas as pd, numpy as np
from core.data.db import fetch_all
from core.data.timeutils import today_local
from lib.features import enrichir_historique, build_features
log=logging.getLogger("predict"); logging.basicConfig(level=logging.INFO)
URL=os.environ["SUPABASE_URL"]
KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE="lgbm_ranker"
BUCKET=os.getenv("MODEL_STORAGE_BUCKET","modeles")


def _rest_request(method, table, payload=None, params=None, prefer=None):
    url = f"{URL}/rest/v1/{table}"

    if params:
        url += "?" + urllib.parse.urlencode(params, safe="(),")

    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else []


def _storage_download(path):
    encoded_path = "/".join(
        urllib.parse.quote(part, safe="")
        for part in path.split("/")
    )

    url = f"{URL}/storage/v1/object/{BUCKET}/{encoded_path}"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
        },
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def active(nom):
    r = _rest_request(
        "GET",
        "modeles",
        params={
            "select": "*",
            "nom": f"eq.{nom}",
            "actif": "eq.true",
            "limit": "1",
        },
    )

    if not r:
        return None, None

    row = r[0]
    raw = _storage_download(row["chemin_storage"])

    return pickle.loads(raw), row

def model_for(discipline):
    a,r=active(f"{BASE}_{discipline}")
    return (a,r) if a else active(f"{BASE}_global")

def fetch_donnees_du_jour(jour=None):
    jour=jour or today_local().isoformat()
    courses=fetch_all("courses","id,reunion_id,discipline,allocation,heure_depart,statut,distance_m,etat_terrain,valeur_penetrometre",page_size=1000)
    reunions=fetch_all("reunions","id,date,meteo_temperature,meteo_force_vent,meteo_nebulosite",page_size=1000)
    rd={r["id"]:r["date"] for r in reunions}
    courses=[c for c in courses if rd.get(c.get("reunion_id"))==jour and c.get("statut") in ("a_venir","en_cours")]
    if not courses:return pd.DataFrame()
    ids=[c["id"] for c in courses]; ps=fetch_all("partants","id,course_id,cheval_nom,cote_matin,cote_actuelle,poids_kg,musique,jockey,est_deferre,gains_participant",course_id__in=ids)
    if not ps:return pd.DataFrame()
    names=list({p["cheval_nom"] for p in ps}); hist_ps=fetch_all("partants","id,course_id,cheval_nom,cote_matin,cote_actuelle,poids_kg,musique,jockey,est_deferre,gains_participant",cheval_nom__in=names)
    all_courses=fetch_all("courses","id,reunion_id,discipline,allocation,heure_depart,statut,distance_m,etat_terrain,valeur_penetrometre",page_size=1000)
    arr=fetch_all("arrivees","course_id,position,partant_id",page_size=1000)
    d1=pd.DataFrame(hist_ps); d2=pd.DataFrame(ps); d1["est_du_jour"]=False; d2["est_du_jour"]=True
    d=pd.concat([d1,d2],ignore_index=True).drop_duplicates("id",keep="last")
    d=d.merge(pd.DataFrame(all_courses),left_on="course_id",right_on="id",how="left",suffixes=("","_course"))
    d=d.merge(pd.DataFrame(reunions),left_on="reunion_id",right_on="id",how="left",suffixes=("","_reunion"))
    if arr:d=d.merge(pd.DataFrame(arr),left_on="id",right_on="partant_id",how="left",suffixes=("","_arr"))
    else:d["position"]=pd.NA
    return d

def _softmax(values):
    a=np.asarray(values,dtype=float); a=a-np.max(a); e=np.exp(np.clip(a,-50,50)); return e/e.sum() if e.sum()>0 else np.ones(len(a))/len(a)

def run_prediction():
    df=fetch_donnees_du_jour()
    if df.empty:return {"statut":"annule","raison":"aucune course à venir/en cours aujourd'hui"}
    df=enrichir_historique(df); today=df[df.est_du_jour].copy(); written=0; details=[]
    for discipline,g in today.groupby(today["discipline"].fillna("inconnu")):
        artefact,row=model_for(discipline)
        if not artefact:details.append({"discipline":discipline,"statut":"annule","raison":"aucun modèle actif"});continue
        X, _, _, _, _ = build_features(
    g,
    jockey_encoder=artefact["jockey_encoder"],
    discipline_encoder=artefact["discipline_encoder"],
    etat_terrain_encoder=artefact.get("etat_terrain_encoder"),
    meteo_nebulosite_encoder=artefact.get("meteo_nebulosite_encoder"),
)
        raw=artefact["model"].predict(X); g=g.copy(); g["raw_score"]=raw
        for cid,cg in g.groupby("course_id"):
            probs=_softmax(cg["raw_score"].to_numpy())
            for (_,r),p in zip(cg.iterrows(),probs):
                _rest_request(
                    "POST",
                    "predictions",
                    payload={
                        "course_id": r.course_id,
                        "partant_id": r.id,
                        "score": float(r.raw_score),
                        "confiance": float(p),
                        "modele": row["version"],
                    },
                    params={
                        "on_conflict": "course_id,partant_id",
                    },
                    prefer="resolution=merge-duplicates,return=minimal",
                )
                written += 1
        details.append({"discipline":discipline,"statut":"ok","modele_utilise":row["nom"],"modele_version":row["version"],"nb_partants_notes":len(g)})
    return {"statut":"ok" if written else "annule","predictions_ecrites":written,"nb_courses":int(today.course_id.nunique()),"par_discipline":details}

if __name__=="__main__":print(run_prediction())
