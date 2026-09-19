# Déploiement PMUPredict corrigé

## Architecture
- Vercel: frontend + API uniquement. Aucun Vercel Cron haute fréquence.
- GitHub Actions: planification des jobs.
- Supabase: base, RLS, Realtime et Storage des modèles.

## Secrets GitHub Actions
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PMU_PROGRAMME_BASE_URL` (optionnel), `RESULTS_API_URL` (optionnel), `PRONOSTICS_SOURCES_JSON`.

La valeur par défaut du programme PMU est le flux turfinfo public. Vérifier les conditions d'utilisation et remplacer `PMU_PROGRAMME_BASE_URL` si vous avez une API contractuelle.

## Variables Vercel backend
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `CRON_SECRET` (uniquement si vous déclenchez manuellement les endpoints cron), `MODEL_STORAGE_BUCKET`.

## Variables Vercel frontend
`NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
