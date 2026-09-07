"""Entraînement LightGBM sans pagination manquante ni fuite temporelle."""
from __future__ import annotations
import os,io,pickle,logging
import json
import urllib.parse
import urllib.request
from datetime import datetime,timezone
import pandas as pd
import numpy as np
import lightgbm
from core.data.db import fetch_all
from core.data.features.legacy_features import enrichir_historique,build_features,rang_vers_pertinence

log=logging.getLogger("train"); logging.basicConfig(level=logging.INFO)
SUPABASE_URL=os.environ["SUPABASE_URL"]
KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Le nouveau format sb_secret_* n'est pas un JWT.
# Le client supabase-py actuel le refuse, alors que l'API REST l'accepte.
# Pour les opérations de lecture nécessaires à l'entraînement, on utilise
# directement l'API REST.
BASE="lgbm_ranker"; BUCKET=os.getenv("MODEL_STORAGE_BUCKET","modeles"); MIN_GLOBAL=int(os.getenv("MIN_ECHANTILLONS_GLOBAL","100")); MIN_DISC=int(os.getenv("MIN_ECHANTILLONS_DISCIPLINE","60")); FOLDS=5

def fetch_training_data():
    ps=fetch_all("partants","id,course_id,numero,cheval_nom,cote_matin,cote_actuelle,poids_kg,musique,jockey,est_deferre")
    ar=fetch_all("arrivees","course_id,position,partant_id")
    co=fetch_all("courses","id,discipline,allocation,heure_depart,distance_m,statut")
    if not ps or not ar or not co:return pd.DataFrame()
    df=pd.DataFrame(ps).merge(pd.DataFrame(ar),left_on="id",right_on="partant_id",how="inner",suffixes=("","_arr"))
    df=df.merge(pd.DataFrame(co),left_on="course_id",right_on="id",how="left",suffixes=("","_course"))
    df=df[df["position"].notna()].copy(); df["position"]=pd.to_numeric(df["position"],errors="coerce"); df=df[df["position"].notna()]
    return df

def _groups(d):
    return d.groupby("course_id", sort=False).size().tolist()


def _fit(d):
    d = d.sort_values(["heure_depart", "course_id"])

    X = d[_FEATURES]
    y = d["pertinence"]

    train_set = lightgbm.Dataset(
        X,
        label=y,
        group=_groups(d),
        feature_name=list(_FEATURES),
        free_raw_data=False,
    )

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "learning_rate": 0.04,
        "num_leaves": 31,
        "max_depth": 5,
        "min_child_samples": 10,
        "seed": 42,
        "verbosity": -1,
        "num_threads": 2,
    }

    model = lightgbm.train(
        params,
        train_set,
        num_boost_round=250,
    )

    return model


def _hit(model, d):
    if d.empty:
        return 0.0

    d = d.copy()
    d["pred"] = model.predict(d[_FEATURES])

    ok = 0

    for _, g in d.groupby("course_id"):
        top = g.loc[g["pred"].idxmax()]
        ok += int(top["position"] <= 5)

    return ok / max(1, d["course_id"].nunique())


def train_and_evaluate(df):
    df=enrichir_historique(df); df["pertinence"]=df["position"].apply(rang_vers_pertinence)
    features,jenc,denc=build_features(df); df=df.copy()
    for c in features.columns:df[c]=features[c]
    global _FEATURES; _FEATURES=list(features.columns)
    n_courses=df["course_id"].nunique(); n_splits=min(FOLDS,max(2,n_courses//20))
    # Validation temporelle: les folds sont des fenêtres chronologiques, pas un mélange passé/futur.
    df=df.sort_values(["heure_depart","course_id"]).reset_index(drop=True)
    groups=df["course_id"].drop_duplicates().tolist(); chunks=[set(x.tolist()) for x in np.array_split(np.array(groups,dtype=object),n_splits)]
    scores=[]
    for i in range(1,len(chunks)):
        test_ids=chunks[i]; train_ids=set().union(*chunks[:i])
        tr=df[df.course_id.isin(train_ids)]; te=df[df.course_id.isin(test_ids)]
        if tr.course_id.nunique()<2 or te.empty:continue
        scores.append(_hit(_fit(tr),te))
    model=_fit(df)
    return model,{"top5_hit_rate":round(sum(scores)/len(scores),4) if scores else 0.0,"nb_folds_cv":len(scores),"nb_courses":int(n_courses),"nb_lignes":len(df)},jenc,denc

def _rest_request(method, table, payload=None, params=None, prefer=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
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


def _storage_upload(path, data):
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


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
    return r[0] if r else None


def publish(nom,model,jenc,denc,metrics,n):
    version=datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path=f"{nom}/{version}.pkl"

    b=io.BytesIO()
    pickle.dump(
        {
            "model":model,
            "jockey_encoder":jenc,
            "discipline_encoder":denc
        },
        b
    )

    _storage_upload(path,b.getvalue())

    _rest_request(
        "PATCH",
        "modeles",
        payload={"actif":False},
        params={
            "nom":f"eq.{nom}",
            "actif":"eq.true"
        },
        prefer="return=minimal",
    )

    rows=_rest_request(
        "POST",
        "modeles",
        payload={
            "nom":nom,
            "version":version,
            "chemin_storage":path,
            "metriques":metrics,
            "nb_echantillons":n,
            "actif":True
        },
        prefer="return=representation",
    )

    if not rows:
        raise RuntimeError("Supabase n'a pas retourné le modèle publié.")

    return rows[0]

def train_one(nom,subset,threshold):
    if len(subset)<threshold:return {"nom_modele":nom,"statut":"annule","raison":f"{len(subset)} < {threshold}"}
    model,metrics,j,d=train_and_evaluate(subset); old=active(nom); oldscore=((old or {}).get("metriques") or {}).get("top5_hit_rate",-1)
    if old and metrics["top5_hit_rate"]<=oldscore:return {"nom_modele":nom,"statut":"conserve_ancien","metriques":metrics,"metriques_actif":old.get("metriques")}
    row=publish(nom,model,j,d,metrics,len(subset)); return {"nom_modele":nom,"statut":"publie","version":row["version"],"metriques":metrics}

def run_training():
    df=fetch_training_data()
    if df.empty:return {"statut":"annule","raison":"aucune donnée historique avec arrivées"}
    results=[train_one(f"{BASE}_global",df,MIN_GLOBAL)]
    for disc in sorted(df["discipline"].fillna("inconnu").unique()):results.append(train_one(f"{BASE}_{disc}",df[df.discipline==disc],MIN_DISC))
    return {"statut":"termine","resultats":results,"nb_echantillons_total":len(df)}

if __name__=="__main__":print(run_training())
