"""Entraînement LightGBM sans pagination manquante ni fuite temporelle."""
from __future__ import annotations
import os,io,pickle,logging
from datetime import datetime,timezone
import pandas as pd
import numpy as np
from lightgbm import LGBMRanker
from sklearn.model_selection import GroupKFold
from supabase import create_client,Client
from db import fetch_all
from features import enrichir_historique,build_features,rang_vers_pertinence
from model_names import model_name

log=logging.getLogger("train"); logging.basicConfig(level=logging.INFO)
SUPABASE_URL=os.environ["SUPABASE_URL"]; KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]; supabase:Client=create_client(SUPABASE_URL,KEY)
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

def _groups(d):return d.groupby("course_id",sort=False).size().tolist()
def _fit(d):
    d=d.sort_values(["heure_depart","course_id"]); X=d[_FEATURES]; y=d["pertinence"]
    m=LGBMRanker(objective="lambdarank",n_estimators=250,max_depth=5,learning_rate=.04,num_leaves=31,min_child_samples=10,random_state=42,verbosity=-1)
    m.fit(X,y,group=_groups(d)); return m

def _hit(model,d):
    if d.empty:return 0.0
    d=d.copy(); d["pred"]=model.predict(d[_FEATURES]); ok=0
    for _,g in d.groupby("course_id"):
        top=g.loc[g["pred"].idxmax()]; ok+=int(top["position"]<=5)
    return ok/max(1,d["course_id"].nunique())

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

def active(nom):
    r=supabase.table("modeles").select("*").eq("nom",nom).eq("actif",True).limit(1).execute().data
    return r[0] if r else None

def publish(nom,model,jenc,denc,metrics,n):
    version=datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path=f"{nom}/{version}.pkl"; b=io.BytesIO(); pickle.dump({"model":model,"jockey_encoder":jenc,"discipline_encoder":denc},b); b.seek(0)
    supabase.storage.from_(BUCKET).upload(path,b.read(),{"content-type":"application/octet-stream","upsert":"true"})
    supabase.table("modeles").update({"actif":False}).eq("nom",nom).eq("actif",True).execute()
    return supabase.table("modeles").insert({"nom":nom,"version":version,"chemin_storage":path,"metriques":metrics,"nb_echantillons":n,"actif":True}).execute().data[0]

def _active_feature_count(row):
    if not row:
        return None
    try:
        raw=supabase.storage.from_(BUCKET).download(row["chemin_storage"])
        artifact=pickle.loads(raw)
        model=artifact.get("model")
        return getattr(model,"n_features_in_",None)
    except Exception as e:
        log.warning("Impossible de lire la signature du modèle actif %s: %s",row.get("nom"),e)
        return None

def train_one(nom,subset,threshold):
    if len(subset)<threshold:return {"nom_modele":nom,"statut":"annule","raison":f"{len(subset)} < {threshold}"}
    model,metrics,j,d=train_and_evaluate(subset)
    old=active(nom)
    oldscore=((old or {}).get("metriques") or {}).get("top5_hit_rate",-1)
    old_features=_active_feature_count(old)
    new_features=len(_FEATURES)

    if old and old_features == new_features and metrics["top5_hit_rate"]<=oldscore:
        return {"nom_modele":nom,"statut":"conserve_ancien","metriques":metrics,"metriques_actif":old.get("metriques"),"features":new_features}

    row=publish(nom,model,j,d,metrics,len(subset))
    return {"nom_modele":nom,"statut":"publie","version":row["version"],"metriques":metrics,"features":new_features,"ancien_features":old_features}

def run_training():
    df=fetch_training_data()
    if df.empty:return {"statut":"annule","raison":"aucune donnée historique avec arrivées"}

    results=[train_one(f"{BASE}_global",df,MIN_GLOBAL)]

    groups={}
    for disc in df["discipline"].fillna("inconnu").unique():
        key=model_name(disc,BASE)
        groups.setdefault(key,[]).append(disc)

    for nom,disciplines in sorted(groups.items()):
        subset=df[df["discipline"].fillna("inconnu").isin(disciplines)]
        results.append(train_one(nom,subset,MIN_DISC))

    return {"statut":"termine","resultats":results,"nb_echantillons_total":len(df)}

if __name__=="__main__":print(run_training())
