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
from core.data.timeutils import today_local, now_local, parse_datetime

log=logging.getLogger("ingest"); logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
SUPABASE_URL=os.environ["SUPABASE_URL"]; SUPABASE_SERVICE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase:Client=create_client(SUPABASE_URL,SUPABASE_SERVICE_KEY)
PMU_PROGRAMME_BASE_URL=os.getenv("PMU_PROGRAMME_BASE_URL","https://online.turfinfo.api.pmu.fr/rest/client/61").rstrip("/")
RESULTS_API_URL=os.getenv("RESULTS_API_URL","https://open-pmu-api.vercel.app/api/arrivees")
MAX_REUNIONS=int(os.getenv("PMU_MAX_REUNIONS","20"))
UA={"User-Agent":os.getenv("HTTP_USER_AGENT","pmupredict/1.0 (+https://pmupredict.app)")}

@dataclass
class CourseNormalisee:
    hippodrome_code:str; hippodrome_nom:str; pays_code:str; date_course:str; reunion_numero:int; course_numero:int
    libelle:str; discipline:str; distance_m:Optional[int]; allocation:Optional[float]; heure_depart:Optional[str]
    statut:str; partants:list[dict]; arrivees:list[dict]; source:str

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

def _parse_deferre(value):
    if value is None:
        return False

    value = str(value).strip().upper()

    if not value:
        return False

    # Seules les valeurs commençant réellement par DEFERRE sont considérées
    # comme déferrées. Les valeurs PROTEGE_* ne le sont pas.
    return value.startswith("DEFERRE_")

def _extract_partants(c:dict)->list[dict]:
    raw=_first(c,"partants","participants","chevaux",default=[])
    if isinstance(raw,dict): raw=list(raw.values())
    out=[]
    for p in raw or []:
        if not isinstance(p,dict):continue
        cote=_first(p,"coteActuelle","cote","rapportProbable","rapportProbableGagnant")
        if isinstance(cote,dict):cote=_first(cote,"valeur","rapport","value")
        if cote is None:
            dernier=_first(p,"dernierRapportDirect",default={})
            if isinstance(dernier,dict):
                cote=_first(dernier,"rapport","valeur","value")
        ordre=_first(p,"ordreArrivee","ordreArriveeFinal","position","place")
        out.append({
            "numero":_int(_first(p,"numPmu","numero","num","numeroPmu")),
            "cheval_nom":_first(p,"nom","nomCheval","cheval","nomChevalComplet",default="Inconnu"),
            "jockey":_first(p,"nomJockey","jockey","driver"),"entraineur":_first(p,"nomEntraineur","entraineur"),
            "musique":_first(p,"musique","musiqueCheval"),"poids_kg":_float(_first(p,"poids","poidsCheval","poidsPorte")),
            "cote_matin":_float(_first(p,"coteMatin","rapportMatin")),"cote_actuelle":_float(cote),
            "est_deferre": _parse_deferre(_first(p,"deferre","ferrure",default="")),
            "ordre_arrivee":_int(ordre),"ecart":_first(p,"ecart","distanceArrivee")
        })
    return [p for p in out if p["numero"] is not None]

def _extract_arrivees(c:dict, partants:list[dict])->list[dict]:
    raw = _first(
        c,
        "arrivee",
        "arrivees",
        "ordreArrivee",
        "resultats",
        default=[]
    )

    if isinstance(raw, dict):
        vals = []

        for k, v in raw.items():
            if (
                isinstance(v, (int, float, str))
                and _int(k) is not None
                and _int(v) is not None
            ):
                vals.append((_int(v), _int(k), None))

        raw = vals

    out = []

    if isinstance(raw, list):
        for i, x in enumerate(raw, 1):

            if isinstance(x, dict):
                pos = _int(
                    _first(
                        x,
                        "position",
                        "rang",
                        "ordre",
                        default=i
                    )
                )

                num = _int(
                    _first(
                        x,
                        "numero",
                        "numPmu",
                        "num"
                    )
                )

                if num is not None and pos is not None:
                    out.append({
                        "position": pos,
                        "numero": num,
                        "ecart": _first(x, "ecart")
                    })

            elif _int(x) is not None:
                out.append({
                    "position": i,
                    "numero": _int(x)
                })

            elif isinstance(x, (tuple, list)):

                # Format PMU observé :
                # [[5], [3], [2], [4], [1]]
                if len(x) == 1 and _int(x[0]) is not None:
                    out.append({
                        "position": i,
                        "numero": _int(x[0])
                    })

                # Autres formats :
                # [(1, 5), (2, 3), ...]
                elif len(x) >= 2:
                    pos = _int(x[0])
                    num = _int(x[1])

                    if pos is not None and num is not None:
                        out.append({
                            "position": pos,
                            "numero": num,
                            "ecart": x[2] if len(x) > 2 else None
                        })

    # Fallback : arrivée directement présente sur les partants.
    if not out:
        for p in partants:
            position = _int(p.get("ordre_arrivee"))
            numero = _int(p.get("numero"))

            if (
                position is not None
                and position > 0
                and numero is not None
            ):
                out.append({
                    "position": position,
                    "numero": numero,
                    "ecart": p.get("ecart")
                })

    # Nettoyage final : une seule arrivée par position.
    unique = {}

    for item in out:
        pos = _int(item.get("position"))
        num = _int(item.get("numero"))

        if pos is None or num is None:
            continue

        unique[pos] = {
            "position": pos,
            "numero": num,
            "ecart": item.get("ecart")
        }

    return [
        unique[pos]
        for pos in sorted(unique)
    ]

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

        # L'endpoint renvoie {"participants": [...]}
        if isinstance(payload, dict):
            participants = payload.get("participants", [])
        else:
            participants = payload

        if not isinstance(participants, list):
            return []

        # On injecte les participants dans une structure compatible
        # avec _extract_partants().
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
    r=requests.get(
        url,
        params={"specialisation":"INTERNET"},
        headers=UA,
        timeout=20
    )
    r.raise_for_status()
    payload=r.json()

    courses=[]

    pays = _first(payload, "pays", default={}) or {}
    pays_code = _first(pays, "code", default="UNK")

    for c in _extract_races(payload):
        num=_int(_first(c,"numeroCourse","numCourse","course","numOrdre"))
        if not num:
            continue

        hip = _first(c, "hippodrome", default={}) or {}

        code = _first(
            hip,
            "code",
            "codeHippodrome",
            default=_first(
                c,
                "codeHippodrome",
                default=f"R{rn}"
            )
        )

        nom = _first(
            hip,
            "nom",
            "nomHippodrome",
            "libelleLong",
            "libelleCourt",
            default=_first(
                c,
                "nomHippodrome",
                "libelleLong",
                "libelleCourt",
                default="Inconnu"
            )
        )

        partants = _fetch_participants(jour, rn, num)

        # Sécurité : certains flux pourraient éventuellement contenir
        # directement les participants dans la course.
        if not partants:
            partants = _extract_partants(c)

        arr = _extract_arrivees(c, partants)

        heure=_norm_dt(
            _first(
                c,
                "heureDepart",
                "heure_depart",
                "dateHeureDepart"
            ),
            datetime.strptime(jour,"%Y-%m-%d").date()
        )

        courses.append(
            CourseNormalisee(
                str(code),
                str(nom),
                str(pays_code),
                jour,
                rn,
                num,
                _first(c,"libelle","nomPrix","prix",default=""),
                _norm_disc(
                    _first(c,"discipline","typeCourse")
                ),
                _int(
                    _first(c,"distance","distanceCourse")
                ),
                _float(
                    _first(c,"allocation","montant")
                ),
                heure,
                _status(c,heure,arr),
                partants,
                arr,
                "pmu_programme"
            )
        )

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
        r=requests.get(RESULTS_API_URL,params={"date":d},headers=UA,timeout=20); r.raise_for_status(); data=r.json()
        result={}
        for item in data.get("message",[]) if isinstance(data,dict) else []:
            rc=str(item.get("r/c","")).upper().replace(" ","")
            m=re.match(r"R(\d+)/C(\d+)",rc)
            if not m:continue
            nums=item.get("arrivee") or []
            result[(int(m.group(1)),int(m.group(2)))]=[{"position":i,"numero":_int(n)} for i,n in enumerate(nums,1) if _int(n) is not None]
        return result
    except Exception as e:
        log.warning("Fallback résultats indisponible: %s",e); return {}

def log_source_status(nom,typ,statut,detail=""):
    try:
        row=supabase.table("sources").upsert({"nom":nom,"type":typ,"url_base":PMU_PROGRAMME_BASE_URL if typ=="api" else RESULTS_API_URL,"actif":statut!="error","derniere_sync":now_local().isoformat(),"derniere_erreur":detail or None},on_conflict="nom").execute().data[0]
        if statut in ("success","fallback"):
            # La trace détaillée est écrite lors de l'upsert de chaque entité.
            return row["id"]
        return row["id"]
    except Exception: return None

def upsert_course(c:CourseNormalisee, results_override=None):
    hip=supabase.table("hippodromes").upsert({"code":c.hippodrome_code,"nom":c.hippodrome_nom,"pays":c.pays_code},on_conflict="code").execute().data[0]
    reunion=supabase.table("reunions").upsert({"date":c.date_course,"numero":c.reunion_numero,"hippodrome_id":hip["id"]},on_conflict="date,numero,hippodrome_id").execute().data[0]
    row=supabase.table("courses").upsert({"reunion_id":reunion["id"],"numero":c.course_numero,"libelle":c.libelle,"discipline":c.discipline,"distance_m":c.distance_m,"allocation":c.allocation,"heure_depart":c.heure_depart,"statut":c.statut},on_conflict="reunion_id,numero").execute().data[0]
    bynum={p["numero"]:p for p in c.partants}
    for p in c.partants:
        supabase.table("partants").upsert({"course_id":row["id"],"numero":p["numero"],"cheval_nom":p["cheval_nom"],"jockey":p.get("jockey"),"entraineur":p.get("entraineur"),"musique":p.get("musique"),"poids_kg":p.get("poids_kg"),"cote_matin":p.get("cote_matin"),"cote_actuelle":p.get("cote_actuelle"),"est_deferre":p.get("est_deferre",False)},on_conflict="course_id,numero").execute()
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
    jour=jour or today_local().isoformat(); courses=fetch_from_api(jour)
    fallback=fetch_results_fallback(jour)
    if not courses:
        log_source_status("pmu_programme","api","error","Aucune course récupérée")
        return {"statut":"erreur","date":jour,"courses_recuperees":0,"courses_ecrites":0}
    ecrites=0; erreurs=[]
    for c in courses:
        try:
            override=fallback.get((c.reunion_numero,c.course_numero))
            upsert_course(c,override); ecrites+=1
        except Exception as e:erreurs.append(f"R{c.reunion_numero}C{c.course_numero}: {e}")
    log_source_status("pmu_programme","api","success")
    if fallback:log_source_status("open_pmu_results","api","success")
    return {"statut":"ok" if ecrites else "erreur","date":jour,"courses_recuperees":len(courses),"courses_ecrites":ecrites,"erreurs":erreurs[:20]}

if __name__=="__main__": print(run_ingestion())
