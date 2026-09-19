# pmupredict — Récapitulatif du pipeline complet

Ce document liste, en un seul endroit, tous les modules construits jusqu'ici :
tables Supabase, jobs planifiés, endpoints serverless et dépendances entre eux.

## Vue d'ensemble — ordre d'exécution quotidien

| Heure   | Cron                          | Rôle                                                    |
|---------|-------------------------------|----------------------------------------------------------|
| 03h00   | `/api/cron/train`              | Ré-entraîne le modèle IA sur l'historique, publie si meilleur |
| Continu | `/api/cron/ingest` (30 min)    | Récupère partants, cotes, arrivées (API + scraping)      |
| 07h00   | `/api/cron/pronostics`         | Collecte les pronostics presse + communauté du jour      |
| 07h35   | `/api/cron/fusion`             | Calcule le score final (IA + presse + communauté)        |
| 23h00   | `/api/cron/performance_tipsters` | Ajuste la fiabilité des tipsters selon les résultats du jour |

## Modules et fichiers

| # | Module | Table(s) Supabase | Fichier logique | Endpoint | Fréquence |
|---|--------|--------------------|--------------------|----------------|-----------|
| 1 | Ingestion données de course | `hippodromes`, `reunions`, `courses`, `partants`, `arrivees`, `sources`, `source_logs` | `lib/ingest.py` | `api/cron/ingest.py` | */30 min |
| 2 | Pronostics presse & communauté | `pronostiqueurs`, `pronostics_externes` | `lib/pronostics.py` | `api/cron/pronostics.py` | 1×/jour (7h) |
| 3 | Fusion des scores | `pronostics_fusion` | `lib/fusion.py` (calcul) | `api/cron/fusion.py` | 1×/jour (7h35) |
| 4 | Feedback fiabilité tipsters | `pronostiqueurs.points` (mise à jour) | `lib/fusion.py` (update_pronostiqueur_performance) | `api/cron/performance_tipsters.py` | 1×/jour (23h) |
| 5 | Ré-entraînement IA | `modeles`, `predictions` | `lib/train.py` | `api/cron/train.py` | 1×/jour (3h) |
| 6 | API lecture — analyse course | `pronostics_fusion`, `partants`, `courses` | — (lecture directe) | `api/analyse/[course_id].py` | à la demande (public, cache 60s) |
| 7 | API lecture — classement tipsters | `pronostiqueurs` | — (lecture directe) | `api/tipsters.py` | à la demande (public, cache 5min) |
| 8 | API lecture — programme du jour | `courses`, `reunions`, `hippodromes` | — (lecture directe) | `api/courses.py` | à la demande (public, cache 60s) |
| 9 | Recommandations personnalisées | `profils`, `pronostics_fusion` | `api/recommendations.py` | `api/recommendations.py` | à la demande (authentifié) |
| 10 | Détection d'opportunités (value bets) | `opportunites` | `lib/live_opportunities.py` | `api/cron/opportunites.py` | */5 min |
| 11 | Sécurité RLS | toutes les tables | `rls_policies.sql` | — | à exécuter une fois |
| 12 | Frontend Next.js | — | `pmupredict-frontend/` | déployé sur Vercel | — |

## Dépendances entre modules

```
ingest ──────────────┐
                      ▼
pronostics ────► fusion ────► (consommé par le frontend / API publique)
                      ▲
train ────► predictions
                      │
performance_tipsters ◄── arrivees (résultats du jour, via ingest)
```

- `fusion` a besoin que `ingest` (partants) et `pronostics` (presse/communauté) soient déjà passés dans la journée — d'où l'ordre 07h00 → 07h35.
- `train` tourne indépendamment la nuit ; ses `predictions` sont relues par `fusion` le matin suivant.
- `performance_tipsters` a besoin des `arrivees` du jour (mises à jour par `ingest` en continu) — d'où son exécution tardive à 23h.

## Fichiers livrés

**Backend (`pmupredict-backend/`)**

| Fichier | Contenu |
|---------|---------|
| `schema_complet.sql` | Toutes les tables (courses, sources, pronostics, fusion, modèles) |
| `rls_policies.sql` | Politiques de sécurité complètes (lecture publique / écriture service_role / privé par utilisateur) + tables `profils`, `bets`, `notifications` |
| `opportunites_schema.sql` | Table des opportunités de paris détectées en direct |
| `vercel.json` | 6 crons + toutes les fonctions serverless |
| `lib/*.py` | Logique métier de chaque module |
| `api/cron/*.py` | Endpoints cron protégés par `CRON_SECRET` |
| `api/analyse/[course_id].py`, `api/tipsters.py`, `api/courses.py`, `api/recommendations.py` | Endpoints de lecture publics/authentifiés |

**Frontend (`pmupredict-frontend/`)**

| Fichier | Contenu |
|---------|---------|
| `app/page.tsx` | Programme du jour (racecard) |
| `app/course/[id]/page.tsx` | Analyse fusionnée + cotes en direct (Supabase Realtime) |
| `app/tipsters/page.tsx` | Classement des tipsters |
| `components/SaddleBadge.tsx`, `HorseRow.tsx` | Composants du racecard |
| `lib/api.ts`, `lib/supabaseClient.ts` | Appels API et abonnement temps réel |

## Notes sur le live betting

Pas de WebSocket custom à maintenir : la table `partants` (et `opportunites`)
est répliquée via **Supabase Realtime**. Le frontend s'abonne directement
depuis le navigateur (`lib/supabaseClient.ts`) et reçoit les mises à jour
de cote dès que `ingest.py` écrit en base — le cron `opportunites` (*/5 min)
vient ensuite alerter sur les écarts de valeur significatifs.

## Variables d'environnement nécessaires (rappel)

```
# Backend
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=      # jobs cron (écriture)
SUPABASE_ANON_KEY=              # endpoints de lecture publics
CRON_SECRET=
PMU_PROGRAMME_BASE_URL=https://online.turfinfo.api.pmu.fr/rest/client/61
RESULTS_API_URL=https://open-pmu-api.vercel.app/api/arrivees

# Frontend
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE=
```

## Prochaines étapes possibles

- `/api/pronostics/{course_id}` et `/api/community/{course_id}` (vues filtrées, PRD 5.2)
- Page de profil / préférences utilisateur (pour alimenter `/api/recommendations`)
- Système de notifications (email/push) sur les opportunités détectées
- Tests automatisés et CI/CD (GitHub Actions)


