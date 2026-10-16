-- PLAN 1.3.a: lock the database's rights down (decision 0023).
--
-- Supabase grants every right on every table, sequence and function to anon (signed out)
-- and authenticated (signed in), and row-level security doesn't apply to some of them
-- (TRUNCATE, REFERENCES, TRIGGER, and Postgres 17's MAINTAIN, which allows LOCK TABLE).
-- After this migration:
--   anon           no rights at all
--   authenticated  read only; RLS policies (1.3.c-e) decide which rows. Each API task adds
--                  the writes its endpoint needs, with tests.
--   service_role   read and write rows (worker, MCP); no TRUNCATE, REFERENCES, TRIGGER
--                  or MAINTAIN
-- and tables, sequences and functions created by later migrations start the same way.


-- ---------------------------------------------------------------------------------------
-- Existing tables and sequences
-- ---------------------------------------------------------------------------------------

revoke all on all tables in schema public from anon;
revoke insert, update, delete, truncate, references, trigger, maintain
  on all tables in schema public from authenticated;
revoke truncate, references, trigger, maintain on all tables in schema public from service_role;

-- A table-level revoke also removes column-level grants, including 1.2's
-- "update (priority, answers, note, contact_user_id) on requests". Task 4.x grants back
-- exactly what each endpoint needs.

revoke all on all sequences in schema public from anon, authenticated;


-- ---------------------------------------------------------------------------------------
-- Existing functions: nobody but the owner runs them, except the gatekeeper
-- ---------------------------------------------------------------------------------------

revoke execute on all functions in schema public from public, anon, authenticated;
grant execute on function public.transition_request(uuid, text, text, text)
  to authenticated, service_role;


-- ---------------------------------------------------------------------------------------
-- Defaults for objects created later by migrations (which run as postgres)
-- ---------------------------------------------------------------------------------------

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke truncate, references, trigger, maintain on tables from service_role;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated;
-- PUBLIC's default right to run new functions can only be removed globally, not per schema.
alter default privileges for role postgres
  revoke execute on functions from public;
