-- PMUPredict — schéma PostgreSQL idempotent.
create extension if not exists pgcrypto;

create table if not exists hippodromes (
 id uuid primary key default gen_random_uuid(), code text unique not null, nom text not null,
 pays text default 'FR', created_at timestamptz default now());
create table if not exists reunions (
 id uuid primary key default gen_random_uuid(), date date not null, numero int not null,
 hippodrome_id uuid references hippodromes(id) on delete cascade, created_at timestamptz default now(),
 unique(date,numero,hippodrome_id));
create table if not exists courses (
 id uuid primary key default gen_random_uuid(), reunion_id uuid references reunions(id) on delete cascade,
 numero int not null, libelle text, discipline text, distance_m int, allocation numeric,
 heure_depart timestamptz, etat_terrain text, statut text default 'a_venir', created_at timestamptz default now(),
 unique(reunion_id,numero));
create table if not exists partants (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 numero int not null, cheval_nom text not null, jockey text, entraineur text, musique text,
 poids_kg numeric, cote_matin numeric, cote_actuelle numeric, est_deferre boolean default false,
 created_at timestamptz default now(), unique(course_id,numero));
create table if not exists arrivees (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 position int not null, partant_id uuid references partants(id) on delete cascade, ecart text,
 created_at timestamptz default now(), unique(course_id,position));
create table if not exists predictions (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 partant_id uuid references partants(id) on delete cascade, score numeric not null, confiance numeric,
 modele text, created_at timestamptz default now());
create unique index if not exists uq_predictions_course_partant on predictions(course_id,partant_id);
create table if not exists sources (
 id uuid primary key default gen_random_uuid(), nom text unique not null, type text not null, url_base text,
 actif boolean default true, derniere_sync timestamptz, derniere_erreur text, created_at timestamptz default now());
create table if not exists source_logs (
 id uuid primary key default gen_random_uuid(), source_id uuid references sources(id) on delete cascade,
 entite text not null, entite_id uuid, statut text not null, detail text, created_at timestamptz default now());
create table if not exists modeles (
 id uuid primary key default gen_random_uuid(), nom text not null, version text not null, chemin_storage text not null,
 metriques jsonb, nb_echantillons int, actif boolean default false, created_at timestamptz default now(),
 unique(nom,version));
create unique index if not exists uq_modeles_actif_nom on modeles(nom) where actif=true;
create table if not exists pronostiqueurs (
 id uuid primary key default gen_random_uuid(), nom text not null, type text not null, site_source text,
 points numeric default 0, nb_pronostics int default 0, created_at timestamptz default now(), unique(nom,type));
create table if not exists pronostics_externes (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 pronostiqueur_id uuid references pronostiqueurs(id) on delete cascade, partant_id uuid references partants(id) on delete cascade,
 rang_propose int not null, commentaire text, source text not null, created_at timestamptz default now(),
 unique(course_id,pronostiqueur_id,partant_id));
create table if not exists pronostics_fusion (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 partant_id uuid references partants(id) on delete cascade, score_ia numeric default 0, score_presse numeric default 0,
 score_communaute numeric default 0, score_final numeric not null, rang_final int not null, poids_utilises jsonb,
 probabilite_estimee numeric, cote_estimee numeric, created_at timestamptz default now(),
 unique(course_id,partant_id));
create table if not exists opportunites (
 id uuid primary key default gen_random_uuid(), course_id uuid references courses(id) on delete cascade,
 partant_id uuid references partants(id) on delete cascade, cote_actuelle numeric not null, cote_estimee numeric not null,
 ecart_valeur numeric not null, type text not null, created_at timestamptz default now(), updated_at timestamptz default now(),
 unique(course_id,partant_id));
create table if not exists profils (
 id uuid primary key references auth.users(id) on delete cascade, pseudo text,
 preferences jsonb default '{}'::jsonb, created_at timestamptz default now());
create table if not exists bets (
 id uuid primary key default gen_random_uuid(), user_id uuid references auth.users(id) on delete cascade,
 course_id uuid references courses(id), partant_id uuid references partants(id), mise numeric not null, cote numeric not null,
 statut text default 'en_attente', created_at timestamptz default now());
create table if not exists notifications (
 id uuid primary key default gen_random_uuid(), user_id uuid references auth.users(id) on delete cascade,
 type text, message text, read boolean default false, created_at timestamptz default now());

create index if not exists idx_reunions_date on reunions(date);
create index if not exists idx_courses_reunion on courses(reunion_id);
create index if not exists idx_courses_statut on courses(statut);
create index if not exists idx_partants_course on partants(course_id);
create index if not exists idx_partants_cheval on partants(cheval_nom);
create index if not exists idx_predictions_course on predictions(course_id);
create index if not exists idx_arrivees_course on arrivees(course_id);
create index if not exists idx_fusion_course on pronostics_fusion(course_id,rang_final);
create index if not exists idx_opportunites_course on opportunites(course_id,created_at desc);
create index if not exists idx_source_logs_source on source_logs(source_id,created_at desc);

alter table courses enable row level security; alter table partants enable row level security; alter table arrivees enable row level security;
alter table predictions enable row level security; alter table sources enable row level security; alter table source_logs enable row level security;
alter table modeles enable row level security; alter table pronostiqueurs enable row level security; alter table pronostics_externes enable row level security;
alter table pronostics_fusion enable row level security; alter table opportunites enable row level security;
alter table profils enable row level security; alter table bets enable row level security; alter table notifications enable row level security;

-- Bucket privé pour les modèles IA. À créer si le projet Supabase autorise l'insertion dans storage depuis SQL.
insert into storage.buckets(id,name,public) values ('modeles','modeles',false) on conflict(id) do nothing;

-- Realtime: idempotence impossible via ADD TABLE, donc on ignore l'erreur si déjà présent via DO.
do $$ begin alter publication supabase_realtime add table partants; exception when duplicate_object then null; end $$;
do $$ begin alter publication supabase_realtime add table pronostics_fusion; exception when duplicate_object then null; end $$;
do $$ begin alter publication supabase_realtime add table opportunites; exception when duplicate_object then null; end $$;
