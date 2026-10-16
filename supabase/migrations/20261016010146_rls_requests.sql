-- PLAN 1.3.e: who may read requests and the records attached to them (decision 0023).
-- Plant users see every request at their plants (the shared history, decision 0004) with
-- its photos, messages, quotes, outcomes and timeline. The AI's raw output, reviews,
-- pipeline checkpoints, case memory, the ticket chat and knowledge proposals are
-- staff-only: plant users get a filtered view of the analysis through the API (PLAN 4.3),
-- which applies the withholding rule (CLAUDE.md invariant 13).


-- A request at one of the caller's plants (for plant users' policies on child tables).
create function private.is_my_plants_request(p_request_id uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.requests r
     where r.id = p_request_id
       and r.tenant_id = private.my_tenant()
       and r.plant_id = any (private.my_plants())
  )
$$;

revoke execute on function private.is_my_plants_request(uuid) from public, anon;
grant execute on function private.is_my_plants_request(uuid) to authenticated, service_role;


-- ---------------------------------------------------------------------------------------
-- Shared with plant users: requests and their photos, messages, quotes, outcomes
-- ---------------------------------------------------------------------------------------

create policy "staff see all requests; plant users those at their plants"
  on public.requests for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or plant_id in (select unnest(private.my_plants())))
  );

create policy "staff see all photos; plant users those on their plants' requests"
  on public.request_photos for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or private.is_my_plants_request(request_id))
  );

create policy "staff see all messages; plant users those on their plants' requests"
  on public.messages for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or private.is_my_plants_request(request_id))
  );

create policy "staff see all quotes; plant users those on their plants' requests"
  on public.quotes for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or private.is_my_plants_request(request_id))
  );

create policy "staff see all outcomes; plant users those on their plants' requests"
  on public.outcomes for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or private.is_my_plants_request(request_id))
  );

-- Plant users see the timeline (creation and status changes) of their plants' requests;
-- other event types (e.g. analysis_ready with internal details) are staff-only.
create policy "staff see all events; plant users their requests' timeline"
  on public.events for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and (
      (select private.is_staff())
      or (
        type in ('request_created', 'status_changed')
        and request_id is not null
        and private.is_my_plants_request(request_id)
      )
    )
  );


-- ---------------------------------------------------------------------------------------
-- Staff only
-- ---------------------------------------------------------------------------------------

create policy "staff see pipeline checkpoints" on public.pipeline_runs
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see analyses" on public.analyses
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see reviews" on public.reviews
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see case memory" on public.cases
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see the ticket chat" on public.chat_messages
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see knowledge proposals" on public.knowledge_proposals
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));
