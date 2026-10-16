-- PLAN 1.3.c: who may read suppliers, customers, plants, people and invites (decision 0023).
-- Read-only: signed-in users have no write rights (1.3.a); each API task adds its own.
-- Every policy is limited to the caller's own supplier first, so nobody ever sees
-- another supplier's rows.


-- Staff a plant user may see: whoever is the contact or the claimer on, or wrote a message
-- on, a request at one of their plants (the owner's choice; decision 0023). Security
-- definer so it doesn't depend on the request policies (1.3.e).
create function private.staff_on_my_requests() returns setof uuid
language sql stable security definer set search_path = ''
as $$
  select r.contact_user_id from public.requests r
   where r.tenant_id = private.my_tenant() and r.plant_id = any (private.my_plants())
     and r.contact_user_id is not null
  union
  select r.claimed_by from public.requests r
   where r.tenant_id = private.my_tenant() and r.plant_id = any (private.my_plants())
     and r.claimed_by is not null
  union
  select m.author_id from public.messages m
    join public.requests r on r.id = m.request_id
   where r.tenant_id = private.my_tenant() and r.plant_id = any (private.my_plants())
$$;

revoke execute on function private.staff_on_my_requests() from public, anon;
grant execute on function private.staff_on_my_requests() to authenticated, service_role;


create policy "members see their own supplier" on public.tenants
  for select to authenticated
  using (id = (select private.my_tenant()));

create policy "staff see all customers; plant users the one owning their plants"
  on public.customers for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and (
      (select private.is_staff())
      or exists (
        select 1 from public.plants p
         where p.customer_id = customers.id and p.id in (select unnest(private.my_plants()))
      )
    )
  );

create policy "staff see all plants; plant users their own" on public.plants
  for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or id in (select unnest(private.my_plants())))
  );

create policy "everyone sees themselves; staff see their supplier; plant users the staff on their requests"
  on public.profiles for select to authenticated
  using (
    user_id = (select auth.uid())
    or (
      tenant_id = (select private.my_tenant())
      and (
        (select private.is_staff())
        or user_id in (select private.staff_on_my_requests())
      )
    )
  );

create policy "admins see their supplier's invites" on public.plant_invites
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_admin()));
