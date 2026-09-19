-- Migration idempotente pour installations existantes.
alter table partants add column if not exists est_deferre boolean default false;
alter table courses add column if not exists allocation numeric;
alter table predictions add column if not exists confiance numeric;
alter table pronostics_fusion add column if not exists probabilite_estimee numeric;
alter table pronostics_fusion add column if not exists cote_estimee numeric;
create unique index if not exists uq_predictions_course_partant on predictions(course_id,partant_id);
create unique index if not exists uq_modeles_actif_nom on modeles(nom) where actif=true;
