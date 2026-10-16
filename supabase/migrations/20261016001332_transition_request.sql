-- PLAN 1.2: transition_request(), the only way a request's status changes (SPEC §6,
-- CLAUDE.md invariant 3). Design: decision 0013 and its 2026-10-15 update.
--
-- Two locks keep everything else out:
--   1. Permissions: signed-in roles may not update status, attempt or claimed_by at all.
--      transition_request() runs with its owner's rights, so it's the only way through.
--   2. A trigger refuses changes to those columns unless the transaction-local flag
--      app.transition is on. Only transition_request() sets it (and turns it off again);
--      signed-in users can set the flag too, but lock 1 already stops them.
--
-- Callers: a signed-in person is identified by their login token (auth.uid()), never by a
-- parameter. Server code (the worker, schedulers) has no login token and must name itself
-- 'worker' or 'system'. Error codes: 42501 not permitted, P0001 move not allowed,
-- P0002 not found (also for other tenants' requests, so their existence isn't revealed).


-- ---------------------------------------------------------------------------------------
-- The gatekeeper
-- ---------------------------------------------------------------------------------------

create function public.transition_request(
  p_request_id uuid,
  p_to         text,
  p_actor      text default null,  -- server code only: 'worker' or 'system'
  p_reason     text default null   -- optional, kept in the event (e.g. the question asked)
) returns public.requests
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_claims  jsonb := auth.jwt();
  v_user    uuid;
  v_actor   text;
  v_tenant  uuid;
  v_roles   text[] := '{}';
  v_plants  uuid[] := '{}';
  v_request public.requests;
  v_from    text;
  v_ok      boolean;
begin
  -- 1. Who is calling?
  if v_claims is null or v_claims ->> 'role' = 'service_role' then
    -- Server code: no login token (or the service key). It must say what it is.
    if p_actor is null or p_actor not in ('worker', 'system') then
      raise exception using errcode = '42501',
        message = 'server code must call transition_request() as ''worker'' or ''system''';
    end if;
    v_actor := p_actor;
  elsif v_claims ->> 'role' = 'authenticated' and auth.uid() is not null then
    if p_actor is not null then
      raise exception using errcode = '42501',
        message = format('a signed-in user can''t act as %L', p_actor);
    end if;
    v_user := auth.uid();
    v_actor := 'user';
    select p.tenant_id, p.roles, p.plant_ids into v_tenant, v_roles, v_plants
      from public.profiles p where p.user_id = v_user;
    if not found then
      raise exception using errcode = '42501', message = 'no profile for this user';
    end if;
  else
    raise exception using errcode = '42501', message = 'not signed in';
  end if;

  -- 2. Lock the request, so two simultaneous calls take turns (the second sees the result
  --    of the first: e.g. only one engineer's claim succeeds).
  select * into v_request from public.requests r where r.id = p_request_id for update;
  if not found or (v_user is not null and v_request.tenant_id <> v_tenant) then
    raise exception using errcode = 'P0002', message = format('request %s not found', p_request_id);
  end if;
  v_from := v_request.status;

  -- 3. Is the move in SPEC §6's table?
  if (v_from, p_to) not in (
       ('submitted', 'analyzing'),
       ('analyzing', 'needs_info'),
       ('needs_info', 'analyzing'),
       ('analyzing', 'ready_for_review'),
       ('analyzing', 'failed'),
       ('failed', 'ready_for_review'),
       ('ready_for_review', 'in_review'),
       ('in_review', 'ready_for_review'),
       ('in_review', 'quote_sent'),
       ('in_review', 'closed'),
       ('quote_sent', 'closed')) then
    raise exception using errcode = 'P0001',
      message = format('transition %s -> %s is not allowed', v_from, p_to);
  end if;

  -- 4. May this caller make it? Admins may do anything engineers and sales may.
  v_ok := case
    when v_from = 'submitted' and p_to = 'analyzing' then v_actor = 'worker'
    when v_from = 'analyzing' then v_actor = 'worker'
    when v_from = 'needs_info' and p_to = 'analyzing' then
      -- The technician's answers arrive: only a plant user with access to this plant.
      'plant_user' = any (v_roles) and v_request.plant_id = any (v_plants)
    when v_from = 'failed' and p_to = 'ready_for_review' then
      v_roles && array['engineer', 'admin']
    when v_from = 'ready_for_review' and p_to = 'in_review' then
      v_roles && array['engineer', 'admin']
    when v_from = 'in_review' and p_to = 'ready_for_review' then
      -- Release: only whoever claimed it, or an admin.
      v_request.claimed_by = v_user or 'admin' = any (v_roles)
    when v_from = 'in_review' and p_to = 'quote_sent' then
      v_roles && array['sales', 'admin']
    when v_from = 'in_review' and p_to = 'closed' then
      v_roles && array['engineer', 'sales', 'admin']
    when v_from = 'quote_sent' and p_to = 'closed' then
      v_actor = 'system' or v_roles && array['sales', 'admin']
    else false
  end;
  if not coalesce(v_ok, false) then
    raise exception using errcode = '42501',
      message = format('%s may not move a request %s -> %s',
                       coalesce(v_user::text, v_actor), v_from, p_to);
  end if;

  -- 5. Preconditions: a quote needs an engineer's approved or edited review (decision 0006).
  if p_to = 'quote_sent' and not exists (
       select 1 from public.reviews rv
        where rv.request_id = p_request_id and rv.decision in ('approved', 'edited')) then
    raise exception using errcode = 'P0001',
      message = 'a quote needs an approved or edited review first';
  end if;

  -- 6. Make the change. Entering analyzing starts a new attempt (decision 0013);
  --    a claim records the engineer, a release clears it.
  perform pg_catalog.set_config('app.transition', 'on', true);
  update public.requests r
     set status     = p_to,
         attempt    = case when p_to = 'analyzing' then r.attempt + 1 else r.attempt end,
         claimed_by = case
                        when v_from = 'ready_for_review' and p_to = 'in_review' then v_user
                        when v_from = 'in_review' and p_to = 'ready_for_review' then null
                        else r.claimed_by
                      end
   where r.id = p_request_id
   returning r.* into v_request;
  perform pg_catalog.set_config('app.transition', 'off', true);

  -- 7. Log it.
  insert into public.events (tenant_id, request_id, type, payload)
  values (v_request.tenant_id, p_request_id, 'status_changed',
          jsonb_build_object('from', v_from, 'to', p_to, 'actor', v_actor,
                             'actor_id', v_user, 'reason', p_reason));

  return v_request;
end;
$$;

-- Only signed-in users and server code may call it; never anonymous visitors.
revoke execute on function public.transition_request(uuid, text, text, text) from public, anon;
grant execute on function public.transition_request(uuid, text, text, text)
  to authenticated, service_role;


-- ---------------------------------------------------------------------------------------
-- Lock 1: signed-in roles can't touch the lifecycle columns
-- ---------------------------------------------------------------------------------------

-- Supabase grants table-wide UPDATE by default. Replace it with the columns people may
-- edit; status, attempt and claimed_by aren't among them. (Which rows they may edit is
-- PLAN 1.3's row-level security.)
revoke update on public.requests from anon, authenticated, service_role;
grant update (priority, answers, note, contact_user_id) on public.requests
  to authenticated, service_role;


-- ---------------------------------------------------------------------------------------
-- Lock 2: the trigger, which also catches mistakes in trusted server code
-- ---------------------------------------------------------------------------------------

create function public.guard_request_lifecycle() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.status <> 'submitted' or new.attempt <> 0 or new.claimed_by is not null then
      raise exception using errcode = 'P0001',
        message = 'a new request must start as submitted, unclaimed, at attempt 0';
    end if;
  elsif (new.status, new.attempt, new.claimed_by)
          is distinct from (old.status, old.attempt, old.claimed_by)
        and coalesce(pg_catalog.current_setting('app.transition', true), '') <> 'on' then
    raise exception using errcode = 'P0001',
      message = 'status, attempt and claimed_by change only through transition_request()';
  end if;
  return new;
end;
$$;

create trigger requests_guard_lifecycle before insert or update on public.requests
  for each row execute function public.guard_request_lifecycle();


-- ---------------------------------------------------------------------------------------
-- Every request's timeline starts with its creation
-- ---------------------------------------------------------------------------------------

-- Runs with its owner's rights so the event is written whoever creates the request
-- (the events table is closed to signed-in roles).
create function public.log_request_created() returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.events (tenant_id, request_id, type, payload)
  values (new.tenant_id, new.id, 'request_created',
          jsonb_build_object('created_by', new.created_by, 'status', new.status));
  return new;
end;
$$;

create trigger requests_log_created after insert on public.requests
  for each row execute function public.log_request_created();
