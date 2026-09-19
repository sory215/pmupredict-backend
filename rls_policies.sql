-- PMUPredict — policies idempotentes.
do $$ declare t text; begin
  foreach t in array array['courses','partants','arrivees','predictions','sources','source_logs','modeles','pronostiqueurs','pronostics_externes','pronostics_fusion','opportunites'] loop
    execute format('drop policy if exists "public_read_%s" on %I',t,t);
    execute format('drop policy if exists "service_all_%s" on %I',t,t);
  end loop;
end $$;
create policy "public_read_courses" on courses for select using (true);
create policy "public_read_partants" on partants for select using (true);
create policy "public_read_arrivees" on arrivees for select using (true);
create policy "public_read_predictions" on predictions for select using (true);
create policy "public_read_pronostiqueurs" on pronostiqueurs for select using (true);
create policy "public_read_pronostics_externes" on pronostics_externes for select using (true);
create policy "public_read_pronostics_fusion" on pronostics_fusion for select using (true);
create policy "public_read_opportunites" on opportunites for select using (true);
create policy "service_all_courses" on courses for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_partants" on partants for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_arrivees" on arrivees for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_predictions" on predictions for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_sources" on sources for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_source_logs" on source_logs for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_modeles" on modeles for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_pronostiqueurs" on pronostiqueurs for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_pronostics_externes" on pronostics_externes for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_pronostics_fusion" on pronostics_fusion for all using(auth.role()='service_role') with check(auth.role()='service_role');
create policy "service_all_opportunites" on opportunites for all using(auth.role()='service_role') with check(auth.role()='service_role');

drop policy if exists "profil_lecture_soi_meme" on profils; drop policy if exists "profil_maj_soi_meme" on profils; drop policy if exists "profil_creation_soi_meme" on profils;
create policy "profil_lecture_soi_meme" on profils for select using(auth.uid()=id);
create policy "profil_maj_soi_meme" on profils for update using(auth.uid()=id) with check(auth.uid()=id);
create policy "profil_creation_soi_meme" on profils for insert with check(auth.uid()=id);
drop policy if exists "bets_lecture_soi_meme" on bets; drop policy if exists "bets_creation_soi_meme" on bets; drop policy if exists "bets_maj_soi_meme" on bets;
create policy "bets_lecture_soi_meme" on bets for select using(auth.uid()=user_id); create policy "bets_creation_soi_meme" on bets for insert with check(auth.uid()=user_id); create policy "bets_maj_soi_meme" on bets for update using(auth.uid()=user_id) with check(auth.uid()=user_id);
drop policy if exists "notifications_lecture_soi_meme" on notifications; drop policy if exists "notifications_maj_soi_meme" on notifications; drop policy if exists "notifications_ecriture_service" on notifications;
create policy "notifications_lecture_soi_meme" on notifications for select using(auth.uid()=user_id); create policy "notifications_maj_soi_meme" on notifications for update using(auth.uid()=user_id) with check(auth.uid()=user_id); create policy "notifications_ecriture_service" on notifications for insert with check(auth.role()='service_role');
