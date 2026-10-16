-- PLAN 1.3.b: "who am I" helpers for the row-level security policies (decision 0023).
--
-- Each answers one question about the signed-in caller (auth.uid()), so every policy stays
-- one readable line. They:
--   * live in the `private` schema, which isn't exposed to the outside world;
--   * read profiles with the owner's rights (security definer), so the policy on profiles
--     itself can use them without looping back into its own check;
--   * return "nothing" (null, empty, false) for a caller without a profile.
-- Policies call them as `(select private.my_tenant())`, so Postgres runs each once per
-- query rather than once per row (Supabase's recommended pattern).

create schema private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated, service_role;

create function private.my_tenant() returns uuid
language sql stable security definer set search_path = ''
as $$
  select p.tenant_id from public.profiles p where p.user_id = auth.uid()
$$;

create function private.my_roles() returns text[]
language sql stable security definer set search_path = ''
as $$
  select coalesce((select p.roles from public.profiles p where p.user_id = auth.uid()), '{}')
$$;

create function private.my_plants() returns uuid[]
language sql stable security definer set search_path = ''
as $$
  select coalesce((select p.plant_ids from public.profiles p where p.user_id = auth.uid()), '{}')
$$;

-- Staff: anyone at the supplier who works tickets (engineer, sales or admin).
create function private.is_staff() returns boolean
language sql stable security definer set search_path = ''
as $$
  select private.my_roles() && array['engineer', 'sales', 'admin']
$$;

create function private.is_admin() returns boolean
language sql stable security definer set search_path = ''
as $$
  select 'admin' = any (private.my_roles())
$$;

revoke execute on all functions in schema private from public, anon;
grant execute on all functions in schema private to authenticated, service_role;
