"""Ingestion PMU: programme, partants, cotes, statuts et arrivées.

La source programme est configurable via PMU_PROGRAMME_BASE_URL. La valeur par
 défaut pointe vers le flux turfinfo utilisé publiquement, mais l'URL peut être
remplacée si PMU change son API ou si vous disposez d'un accès contractuel.
Les résultats peuvent aussi être complétés par open-pmu-api (historique/arrivées).
"""
from __future__ import annotations
import os, re, logging, requests
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from supabase import create_client, Client
from lib.timeutils import today_local, now_local, parse_datetime
from lib.sources.manager import SourceManager

log=logging.getLogger("ingest"); logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
SUPABASE_URL=os.environ["SUPABASE_URL"]; SUPABASE_SERVICE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase:Client=create_client(SUPABASE_URL,SUPABASE_SERVICE_KEY)
PMU_PROGRAMME_BASE_URL=os.getenv("PMU_PROGRAMME_BASE_URL","https://online.turfinfo.api.pmu.fr/rest/client/61").rstrip("/")
RESULTS_API_URL=os.getenv("RESULTS_API_URL","https://open-pmu-api.vercel.app/api/arrivees")
MAX_REUNIONS=int(os.getenv("PMU_MAX_REUNIONS","20"))
UA={"User-Agent":os.getenv("HTTP_USER_AGENT","pmupredict/1.0 (+https://pmupredict.app)")}

@dataclass
class CourseNormalisee:
    hippodrome_code:str; hippodrome_nom:str; date_course:str; reunion_numero:int; course_numero:int
    libelle:str; discipline:str; distance_m:Optional[int]; allocation:Optional[float]; heure_depart:Optional[str]
    statut:str; partants:list[dict]; arrivees:list[dict]; source:str
    etat_terrain:Optional[str]=None; valeur_penetrometre:Optional[float]=None; heure_mesure_terrain:Optional[str]=None
    meteo_temperature:Optional[float]=None; meteo_force_vent:Optional[float]=None; meteo_direction_vent:Optional[str]=None; meteo_nebulosite:Optional[str]=None

def _first(d,*keys,default=None):
    for k in keys:
        if isinstance(d,dict) and d.get(k) is not None:return d[k]
    return default

def _int(v):
    try:return int(v)
    except (TypeError,ValueError):return None

def _float(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def _norm_disc(v):
    s=str(v or "").lower()
    if "obstacle" in s:return "obstacle"
    if "plat" in s:return "plat"
    if "trot" in s or "attelé" in s or "monte" in s:return "trot"
    return s or "inconnu"

def _norm_dt(v, jour):
    if not v:return None
    if isinstance(v,(int,float)):
        # PMU peut exposer un timestamp ms.
        try:return datetime.fromtimestamp(v/1000 if v>10_000_000_000 else v).astimezone().isoformat()
        except Exception:return None
    s=str(v)
    dt=parse_datetime(s)
    if dt:return dt.isoformat()
    m=re.match(r"^(\d{1,2}):(\d{2})",s)
    if m:
        return datetime.combine(jour,datetime.min.time()).replace(hour=int(m.group(1)),minute=int(m.group(2)),tzinfo=now_local().tzinfo).isoformat()
    return None

def _extract_races(payload:Any)->list[dict]:
    if isinstance(payload,list):
        return [x for x in payload if isinstance(x,dict)]
    if not isinstance(payload,dict):return []
    for key in ("courses","course","races","coursesPartants","programme","reunions"):
        val=payload.get(key)
        if isinstance(val,list):
            if key=="reunions":
                out=[]
                for r in val:
                    if isinstance(r,dict):out.extend(_extract_races(r))
                if out:return out
            elif val and any(isinstance(x,dict) and (_first(x,"numeroCourse","numCourse","course","numOrdre") is not None) for x in val):return val
    # Certains flux imbriquent une réunion dans un objet unique.
    for val in payload.values():
        got=_extract_races(val)
        if got:return got
    return []

def _extract_partants(c:dict)->list[dict]:
    raw=_first(c,"partants","participants","chevaux",default=[])
    if isinstance(raw,dict):
        raw=list(raw.values())

    out=[]
    for p in raw or []:
        if not isinstance(p,dict):
            continue

        # PMU participants : la cote actuelle est portée par
        # dernierRapportDirect.rapport.
        direct=p.get("dernierRapportDirect") or {}
        reference=p.get("dernierRapportReference") or {}

        if not isinstance(direct,dict):
            direct={}
        if not isinstance(reference,dict):
            reference={}

        cote_actuelle=_first(
            p,
            "coteActuelle",
            "cote",
            "rapportProbable",
            "rapportProbableGagnant"
        )

        if cote_actuelle is None:
            cote_actuelle=_first(
                direct,
                "rapport",
                "valeur",
                "value"
            )

        cote_reference=_first(
            p,
            "coteMatin",
            "rapportMatin"
        )

        if cote_reference is None:
            cote_reference=_first(
                reference,
                "rapport",
                "valeur",
                "value"
            )

        # handicapPoids est exprimé en dixièmes de kg :
        # 560 = 56.0 kg.
        poids_raw=_first(
            p,
            "poids",
            "poidsCheval",
            "poidsPorte",
            "handicapPoids"
        )

        poids_kg=None
        try:
            if poids_raw is not None:
                poids_kg=float(poids_raw)
                if poids_kg > 100:
                    poids_kg /= 10.0
        except (TypeError,ValueError):
            poids_kg=None

        ordre=_first(
            p,
            "ordreArrivee",
            "ordreArriveeFinal",
            "position",
            "place"
        )

        driver=_first(p,"nomJockey","jockey","driver")
        entraineur=_first(p,"nomEntraineur","entraineur")

        gains = _first(p,"gainsParticipant",default={})
        if not isinstance(gains,dict):
            gains = {}

        robe = _first(p,"robe",default={})
        if not isinstance(robe,dict):
            robe = {}

        out.append({
            # Champs historiques / identité PMU
            "id_cheval":_first(p,"idCheval"),
            "age":_int(_first(p,"age")),
            "allure":_first(p,"allure"),
            "driver":driver,
            "driver_change":_first(p,"driverChange"),
            "eleveur":_first(p,"eleveur"),
            "engagement":_first(p,"engagement"),
            "gains_participant":gains,
            "handicap_poids":_int(_first(p,"handicapPoids")),
            "handicap_valeur":_float(_first(p,"handicapValeur")),
            "nom_mere":_first(p,"nomMere"),
            "nom_pere":_first(p,"nomPere"),
            "nom_pere_mere":_first(p,"nomPereMere"),
            "nombre_courses":_int(_first(p,"nombreCourses")),
            "nombre_places":_int(_first(p,"nombrePlaces")),
            "nombre_places_second":_int(_first(p,"nombrePlacesSecond")),
            "nombre_places_troisieme":_int(_first(p,"nombrePlacesTroisieme")),
            "nombre_victoires":_int(_first(p,"nombreVictoires")),
            "oeilleres":_first(p,"oeilleres"),
            "pays":_first(p,"pays"),
            "pays_entrainement":_first(p,"paysEntrainement"),
            "place_corde":_int(_first(p,"placeCorde")),
            "poids_condition_monte_change":_first(p,"poidsConditionMonteChange"),
            "proprietaire":_first(p,"proprietaire"),
            "race":_first(p,"race"),
            "robe":robe,
            "sexe":_first(p,"sexe"),
            "supplement":_int(_first(p,"supplement")),
            "url_casaque":_first(p,"urlCasaque"),
            "dernier_rapport_direct":direct if direct else None,
            "dernier_rapport_reference":reference if reference else None,

            # Champs actuellement disponibles dans le schéma mais
            # non présents dans cet endpoint PMU.
            "avis_entraineur":_first(p,"avisEntraineur"),
            "deferre_detail":_first(p,"deferreDetail"),
            "incident":_first(p,"incident"),
            "handicap_distance":_int(_first(p,"handicapDistance")),
            "reduction_kilometrique":_int(_first(p,"reductionKilometrique")),
            "taux_reclamation":_int(_first(p,"tauxReclamation")),
            "temps_obtenu":_int(_first(p,"tempsObtenu")),
            "distance_cheval_precedent":_first(p,"distanceChevalPrecedent"),

            # Donnée brute PMU : permet de conserver les futurs champs.
            "pmu_data":p,

            # Champs déjà utilisés par PMUPredict
            "numero":_int(_first(p,"numPmu","numero","num","numeroPmu")),
            "cheval_nom":_first(
                p,
                "nom",
                "nomCheval",
                "cheval",
                "nomChevalComplet",
                default="Inconnu"
            ),
            "jockey":driver,
            "entraineur":entraineur,
            "musique":_first(p,"musique","musiqueCheval"),
            "poids_kg":poids_kg,
            "cote_matin":_float(cote_reference),
            "cote_actuelle":_float(cote_actuelle),
            "est_deferre":str(
                _first(p,"deferre","ferrure",default="")
            ).upper().startswith("D"),
            "ordre_arrivee":_int(ordre),
            "ecart":_first(p,"ecart","distanceArrivee")
        })

    return [p for p in out if p["numero"] is not None]


def _extract_arrivees(c:dict, partants:list[dict])->list[dict]:
    raw=_first(c,"arrivee","arrivees","ordreArrivee","resultats",default=[])
    if isinstance(raw,dict):
        # ordreArrivee peut être {numero: position} ou un objet de détails.
        vals=[]
        for k,v in raw.items():
            if isinstance(v,(int,float,str)) and _int(k) is not None and _int(v) is not None: vals.append((_int(v),_int(k),None))
        raw=vals
    out=[]
    if isinstance(raw,list):
        for i,x in enumerate(raw,1):
            if isinstance(x,dict):
                pos=_int(_first(x,"position","rang","ordre",default=i)); num=_int(_first(x,"numero","numPmu","num"))
                if num is not None and pos is not None: out.append({"position":pos,"numero":num,"ecart":_first(x,"ecart")})
            elif _int(x) is not None: out.append({"position":i,"numero":_int(x)})
            elif isinstance(x,(tuple,list)) and len(x)>=2: out.append({"position":int(x[0]),"numero":int(x[1]),"ecart":x[2] if len(x)>2 else None})
    # Fallback: ordreArrivee directement sur les partants.
    if not out:
        for p in partants:
            if p.get("ordre_arrivee") and p["ordre_arrivee"]>0: out.append({"position":p["ordre_arrivee"],"numero":p["numero"],"ecart":p.get("ecart")})
    return sorted(out,key=lambda x:x["position"])

def _status(c:dict, heure:str|None, arrivees:list[dict])->str:
    raw=str(_first(c,"statut","etat","status",default="")).lower()
    if arrivees or any(x in raw for x in ("termine","terminée","arrivee","result")):return "terminee"
    dt=parse_datetime(heure)
    if dt:
        n=now_local()
        if n>=dt and n<=dt+timedelta(minutes=15):return "en_cours"
        if n>dt+timedelta(minutes=15):return "terminee" if arrivees else "en_cours"
    return "a_venir"

def _fetch_participants(jour:str, rn:int, course_num:int) -> list[dict]:
    """Récupère les participants depuis l'endpoint PMU /C{num}/participants."""
    date_pmu = datetime.strptime(jour, "%Y-%m-%d").strftime("%d%m%Y")
    url = f"{PMU_PROGRAMME_BASE_URL}/programme/{date_pmu}/R{rn}/C{course_num}/participants"

    try:
        r = requests.get(
            url,
            params={"specialisation": "INTERNET"},
            headers=UA,
            timeout=20,
        )

        if r.status_code != 200:
            log.warning(
                "Participants PMU indisponibles R%s C%s: HTTP %s",
                rn, course_num, r.status_code
            )
            return []

        payload = r.json()

        if isinstance(payload, dict):
            participants = payload.get("participants", [])
        else:
            participants = payload

        if not isinstance(participants, list):
            return []

        return _extract_partants({"participants": participants})

    except Exception as e:
        log.warning(
            "Erreur récupération participants R%s C%s: %s",
            rn, course_num, e
        )
        return []


def fetch_reunion(jour:str,rn:int)->list[CourseNormalisee]:
    date_pmu=datetime.strptime(jour,"%Y-%m-%d").strftime("%d%m%Y")
    url=f"{PMU_PROGRAMME_BASE_URL}/programme/{date_pmu}/R{rn}"
    r=requests.get(url,params={"specialisation":"INTERNET"},headers=UA,timeout=20); r.raise_for_status(); payload=r.json()
    meteo=payload.get("meteo") or {}
    meteo_temperature=meteo.get("temperature")
    meteo_force_vent=meteo.get("forceVent")
    meteo_direction_vent=meteo.get("directionVent")
    meteo_nebulosite=meteo.get("nebulositeLibelleCourt")
    courses=[]
    for c in _extract_races(payload):
        num=_int(_first(c,"numeroCourse","numCourse","course","numOrdre"))
        if not num:continue
        hip=_first(c,"hippodrome",default={}) or {}
        code=_first(hip,"code","codeHippodrome",default=_first(c,"codeHippodrome",default=f"R{rn}"))
        nom=_first(hip,"libelleLong","libelleCourt","nom","nomHippodrome",default=_first(c,"nomHippodrome",default="Inconnu"))
        partants=_fetch_participants(jour,rn,num)
        if not partants:
            partants=_extract_partants(c)
        arr=_extract_arrivees(c,partants)
        heure=_norm_dt(_first(c,"heureDepart","heure_depart","dateHeureDepart"),datetime.strptime(jour,"%Y-%m-%d").date())
        penetro=c.get("penetrometre") or {}
        etat_terrain=penetro.get("intitule")
        valeur_penetro_raw=penetro.get("valeurMesure")
        valeur_penetrometre=None
        if valeur_penetro_raw:
            try:valeur_penetrometre=float(str(valeur_penetro_raw).replace(",","."))
            except (TypeError,ValueError):pass
        heure_mesure_terrain=penetro.get("heureMesure")
        courses.append(CourseNormalisee(str(code),str(nom),jour,rn,num,_first(c,"libelle","nomPrix","prix",default=""),_norm_disc(_first(c,"discipline","typeCourse")),_int(_first(c,"distance","distanceCourse")),_float(_first(c,"allocation","montant")),heure,_status(c,heure,arr),partants,arr,"pmu_programme",etat_terrain,valeur_penetrometre,heure_mesure_terrain,meteo_temperature,meteo_force_vent,meteo_direction_vent,meteo_nebulosite))
    return courses

def fetch_from_api(jour:str)->list[CourseNormalisee]:
    out=[]
    for rn in range(1,MAX_REUNIONS+1):
        try:
            got=fetch_reunion(jour,rn)
            if got:out.extend(got)
        except requests.HTTPError as e:
            if getattr(e.response,"status_code",0) in (404,400):continue
            log.warning("R%d: %s",rn,e)
        except Exception as e:log.warning("R%d indisponible: %s",rn,e)
    return out

def fetch_results_fallback(jour:str)->dict[tuple[int,int],list[dict]]:
    try:
        d=datetime.strptime(jour,"%Y-%m-%d").strftime("%d/%m/%Y")
        r=requests.get(
            RESULTS_API_URL,
            params={"date":d},
            headers=UA,
            timeout=20
        )
        r.raise_for_status()
        data=r.json()

        result={}

        if not isinstance(data,dict):
            return result

        message=data.get("message",[])

        if isinstance(message,dict):
            message=list(message.values())
        elif not isinstance(message,list):
            return result

        for item in message:
            if not isinstance(item,dict):
                continue

            rc=str(item.get("r/c","")).upper().replace(" ","")
            m=re.match(r"R(\d+)/C(\d+)",rc)

            if not m:
                continue

            nums=item.get("arrivee") or []

            if not isinstance(nums,(list,tuple)):
                continue

            result[(int(m.group(1)),int(m.group(2)))]=[
                {
                    "position":i,
                    "numero":_int(n)
                }
                for i,n in enumerate(nums,1)
                if _int(n) is not None
            ]

        return result

    except Exception as e:
        log.warning("Fallback résultats indisponible: %s",e)
        return {}

def log_source_status(nom,typ,statut,detail=""):
    try:
        row=supabase.table("sources").upsert({"nom":nom,"type":typ,"url_base":PMU_PROGRAMME_BASE_URL if typ=="api" else RESULTS_API_URL,"actif":statut!="error","derniere_sync":now_local().isoformat(),"derniere_erreur":detail or None},on_conflict="nom").execute().data[0]
        if statut in ("success","fallback"):
            # La trace détaillée est écrite lors de l'upsert de chaque entité.
            return row["id"]
        return row["id"]
    except Exception: return None

def upsert_course(c:CourseNormalisee, results_override=None):
    hip=supabase.table("hippodromes").upsert({"code":c.hippodrome_code,"nom":c.hippodrome_nom,"pays":"FR"},on_conflict="code").execute().data[0]
    reunion=supabase.table("reunions").upsert({"date":c.date_course,"numero":c.reunion_numero,"hippodrome_id":hip["id"],"meteo_temperature":c.meteo_temperature,"meteo_force_vent":c.meteo_force_vent,"meteo_direction_vent":c.meteo_direction_vent,"meteo_nebulosite":c.meteo_nebulosite},on_conflict="date,numero,hippodrome_id").execute().data[0]
    row=supabase.table("courses").upsert({"reunion_id":reunion["id"],"numero":c.course_numero,"libelle":c.libelle,"discipline":c.discipline,"distance_m":c.distance_m,"allocation":c.allocation,"heure_depart":c.heure_depart,"statut":c.statut,"etat_terrain":c.etat_terrain,"valeur_penetrometre":c.valeur_penetrometre,"heure_mesure_terrain":c.heure_mesure_terrain},on_conflict="reunion_id,numero").execute().data[0]
    bynum={p["numero"]:p for p in c.partants}
    for p in c.partants:
        supabase.table("partants").upsert({
            "course_id":row["id"],
            "numero":p["numero"],
            "cheval_nom":p["cheval_nom"],
            "jockey":p.get("jockey"),
            "entraineur":p.get("entraineur"),
            "musique":p.get("musique"),
            "poids_kg":p.get("poids_kg"),
            "cote_matin":p.get("cote_matin"),
            "cote_actuelle":p.get("cote_actuelle"),
            "est_deferre":p.get("est_deferre",False),

            "id_cheval":p.get("id_cheval"),
            "age":p.get("age"),
            "allure":p.get("allure"),
            "avis_entraineur":p.get("avis_entraineur"),
            "deferre_detail":p.get("deferre_detail"),
            "driver":p.get("driver"),
            "driver_change":p.get("driver_change"),
            "eleveur":p.get("eleveur"),
            "engagement":p.get("engagement"),
            "gains_participant":p.get("gains_participant"),
            "handicap_distance":p.get("handicap_distance"),
            "handicap_poids":p.get("handicap_poids"),
            "handicap_valeur":p.get("handicap_valeur"),
            "incident":p.get("incident"),
            "indicateur_inedit":_first(p,"indicateur_inedit"),
            "jument_pleine":_first(p,"jument_pleine"),
            "nom_mere":p.get("nom_mere"),
            "nom_pere":p.get("nom_pere"),
            "nom_pere_mere":p.get("nom_pere_mere"),
            "nombre_courses":p.get("nombre_courses"),
            "nombre_places":p.get("nombre_places"),
            "nombre_places_second":p.get("nombre_places_second"),
            "nombre_places_troisieme":p.get("nombre_places_troisieme"),
            "nombre_victoires":p.get("nombre_victoires"),
            "oeilleres":p.get("oeilleres"),
            "pays":p.get("pays"),
            "pays_entrainement":p.get("pays_entrainement"),
            "place_corde":p.get("place_corde"),
            "poids_condition_monte":p.get("poids_condition_monte"),
            "poids_condition_monte_change":p.get("poids_condition_monte_change"),
            "proprietaire":p.get("proprietaire"),
            "race":p.get("race"),
            "reduction_kilometrique":p.get("reduction_kilometrique"),
            "robe":p.get("robe"),
            "sexe":p.get("sexe"),
            "supplement":p.get("supplement"),
            "taux_reclamation":p.get("taux_reclamation"),
            "temps_obtenu":p.get("temps_obtenu"),
            "url_casaque":p.get("url_casaque"),
            "dernier_rapport_direct":p.get("dernier_rapport_direct"),
            "dernier_rapport_reference":p.get("dernier_rapport_reference"),
            "distance_cheval_precedent":p.get("distance_cheval_precedent"),
            "pmu_data":p.get("pmu_data")
        },on_conflict="course_id,numero").execute()
    arr=results_override if results_override else c.arrivees
    if arr:
        # Résoudre les IDs après upsert.
        for a in arr:
            if not a.get("numero") or not a.get("position"):continue
            p=supabase.table("partants").select("id").eq("course_id",row["id"]).eq("numero",a["numero"]).limit(1).execute().data
            if not p:continue
            supabase.table("arrivees").upsert({"course_id":row["id"],"position":a["position"],"partant_id":p[0]["id"],"ecart":a.get("ecart")},on_conflict="course_id,position").execute()
        supabase.table("courses").update({"statut":"terminee"}).eq("id",row["id"]).execute()
    return row["id"]

def run_ingestion(jour=None)->dict:
    jour = jour or today_local().isoformat()

    # 1. Programme officiel PMU : courses + partants.
    courses = fetch_from_api(jour)

    # 2. Nouvelle architecture multi-source pour les arrivées.
    try:
        multi_results = SourceManager().merge_results(jour)
    except Exception as e:
        log.warning("Multi-source résultats indisponible: %s", e)
        multi_results = {}

    # 3. Ancien fallback conservé comme sécurité.
    try:
        legacy_results = fetch_results_fallback(jour)
    except Exception as e:
        log.warning("Fallback historique indisponible: %s", e)
        legacy_results = {}

    # 4. Fusion : multi-source prioritaire,
    # fallback historique uniquement pour les courses absentes.
    results = dict(legacy_results)
    results.update(multi_results)

    if not courses:
        log_source_status(
            "pmu_programme",
            "api",
            "error",
            "Aucune course récupérée",
        )
        return {
            "statut": "erreur",
            "date": jour,
            "courses_recuperees": 0,
            "courses_ecrites": 0,
        }

    ecrites = 0
    erreurs = []

    for c in courses:
        try:
            override = results.get(
                (c.reunion_numero, c.course_numero)
            )

            upsert_course(c, override)
            ecrites += 1

        except Exception as e:
            erreurs.append(
                f"R{c.reunion_numero}C{c.course_numero}: {e}"
            )

    log_source_status(
        "pmu_programme",
        "api",
        "success",
    )

    if multi_results:
        log_source_status(
            "multi_source_results",
            "api",
            "success",
        )

    if legacy_results:
        log_source_status(
            "open_pmu_results",
            "api",
            "fallback",
        )

    return {
        "statut": "ok" if ecrites else "erreur",
        "date": jour,
        "courses_recuperees": len(courses),
        "courses_ecrites": ecrites,
        "resultats_multi_source": len(multi_results),
        "resultats_fallback": len(legacy_results),
        "erreurs": erreurs[:20],
    }


if __name__=="__main__":
    print(run_ingestion())
