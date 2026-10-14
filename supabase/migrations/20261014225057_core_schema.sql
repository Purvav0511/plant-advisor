-- PLAN 1.1: the core schema from SPEC §5. Conventions are in decision 0022:
--   * Every reference is a foreign key. References between tenant-owned tables include
--     tenant_id, so a child row can never point at another tenant's parent.
--   * Deletes are blocked while anything refers to a row (no cascades): rows are retired
--     through a status, never erased, so the audit trail stays intact.
--   * Status-like columns only accept their listed values.
--   * Row-level security is enabled on every table with no policies yet (PLAN 1.3 adds
--     them), so the tables are closed to every role except the server's own connection.
--   * Times are timestamptz (UTC); embeddings use pgvector with HNSW cosine indexes.
-- Never edit this file once applied to the shared dev database; add a new migration.


-- ---------------------------------------------------------------------------------------
-- Shared helper: keep updated_at current on every update.
-- ---------------------------------------------------------------------------------------

create function public.set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := pg_catalog.now();
  return new;
end;
$$;


-- ---------------------------------------------------------------------------------------
-- Tenancy and people
-- ---------------------------------------------------------------------------------------

create table public.tenants (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  created_at timestamptz not null default now()
);

create table public.customers (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id),
  name       text not null,
  created_at timestamptz not null default now(),
  unique (tenant_id, id)
);

create table public.plants (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  customer_id uuid not null,
  name        text not null,
  location    text,
  created_at  timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, customer_id) references public.customers (tenant_id, id)
);

-- One profile per signed-in user (Supabase auth.users). A user can hold several roles
-- (decision 0006). plant_ids lists the plants a plant_user may see (decision 0004).
create table public.profiles (
  user_id      uuid primary key references auth.users (id),
  tenant_id    uuid not null references public.tenants (id),
  customer_id  uuid,
  roles        text[] not null
               check (cardinality(roles) > 0
                      and roles <@ array['plant_user', 'engineer', 'sales', 'admin']::text[]),
  plant_ids    uuid[] not null default '{}',
  display_name text,
  phone        text,
  created_at   timestamptz not null default now(),
  unique (tenant_id, user_id),
  foreign key (tenant_id, customer_id) references public.customers (tenant_id, id)
);

create table public.plant_invites (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  customer_id uuid not null,
  code        text not null unique,
  plant_ids   uuid[] not null,
  roles       text[] not null default '{plant_user}',
  expires_at  timestamptz not null,
  max_uses    int not null default 1 check (max_uses > 0),
  uses        int not null default 0 check (uses >= 0),
  created_by  uuid,
  created_at  timestamptz not null default now(),
  check (uses <= max_uses),
  foreign key (tenant_id, customer_id) references public.customers (tenant_id, id),
  foreign key (tenant_id, created_by) references public.profiles (tenant_id, user_id)
);


-- ---------------------------------------------------------------------------------------
-- Knowledge (versioned; the live pipeline reads status = 'approved' only)
-- ---------------------------------------------------------------------------------------

create table public.playbooks (
  id            text not null,
  tenant_id     uuid not null references public.tenants (id),
  version       int not null check (version > 0),
  status        text not null default 'draft' check (status in ('draft', 'approved', 'retired')),
  config        jsonb not null,
  family_schema jsonb not null,
  approved_by   uuid,
  approved_at   timestamptz,
  created_at    timestamptz not null default now(),
  primary key (tenant_id, id, version),
  foreign key (tenant_id, approved_by) references public.profiles (tenant_id, user_id)
);

create table public.vocab_terms (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  playbook_id text not null,
  kind        text not null,
  code        text not null,
  label       text not null,
  description text,
  status      text not null default 'draft' check (status in ('draft', 'approved', 'retired')),
  version     int not null default 1 check (version > 0),
  created_at  timestamptz not null default now(),
  unique (tenant_id, playbook_id, kind, code, version)
);

-- code is the stable identity across versions and databases (decision 0003).
create table public.products (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references public.tenants (id),
  code           text not null,
  family         text not null,
  name           text not null,
  description    text,
  applications   text[] not null default '{}',
  attributes     jsonb not null default '{}',
  source_doc     text,
  status         text not null default 'draft' check (status in ('draft', 'approved', 'retired')),
  version        int not null default 1 check (version > 0),
  text_embedding extensions.vector(384),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (tenant_id, id),
  unique (tenant_id, code, version)
);

create table public.product_images (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id),
  product_id      uuid not null,
  r2_key          text not null,
  kind            text not null check (kind in ('catalog', 'used', 'field')),
  image_embedding extensions.vector(512),
  created_at      timestamptz not null default now(),
  foreign key (tenant_id, product_id) references public.products (tenant_id, id)
);

create table public.rules (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  playbook_id text not null,
  kind        text not null check (kind in ('remedy', 'check', 'compatibility')),
  name        text not null,
  condition   jsonb not null,
  action      jsonb not null,
  rationale   text,
  status      text not null default 'draft' check (status in ('draft', 'approved', 'retired')),
  version     int not null default 1 check (version > 0),
  approved_by uuid,
  approved_at timestamptz,
  created_at  timestamptz not null default now(),
  foreign key (tenant_id, approved_by) references public.profiles (tenant_id, user_id)
);

create table public.ingestion_issues (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references public.tenants (id),
  source_doc   text not null,
  product_name text,
  field        text,
  issue        text not null,
  severity     text not null check (severity in ('info', 'warning', 'error')),
  status       text not null default 'open' check (status in ('open', 'resolved')),
  created_at   timestamptz not null default now()
);


-- ---------------------------------------------------------------------------------------
-- Assets
-- ---------------------------------------------------------------------------------------

-- playbook_id names a playbook without a version, so it isn't a foreign key: the playbooks
-- table is keyed by (tenant_id, id, version). The pipeline resolves the approved version.
create table public.components (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references public.tenants (id),
  plant_id       uuid not null,
  playbook_id    text not null,
  component_type text not null,
  name           text not null,
  attributes     jsonb not null default '{}',
  qr_code        text unique,
  created_at     timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, plant_id) references public.plants (tenant_id, id)
);

create table public.installations (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references public.tenants (id),
  component_id uuid not null,
  product_id   uuid,
  description  text,
  installed_on date,
  removed_on   date,
  notes        text,
  created_at   timestamptz not null default now(),
  check (removed_on is null or installed_on is null or removed_on >= installed_on),
  foreign key (tenant_id, component_id) references public.components (tenant_id, id),
  foreign key (tenant_id, product_id) references public.products (tenant_id, id)
);


-- ---------------------------------------------------------------------------------------
-- Requests
-- ---------------------------------------------------------------------------------------

-- status changes only through transition_request() (PLAN 1.2, SPEC §6, invariant 3).
create table public.requests (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id),
  customer_id     uuid not null,
  plant_id        uuid not null,
  component_id    uuid not null,
  playbook_id     text not null,
  status          text not null default 'submitted'
                  check (status in ('submitted', 'analyzing', 'needs_info', 'ready_for_review',
                                    'in_review', 'quote_sent', 'closed', 'failed')),
  priority        text not null default 'normal' check (priority in ('low', 'normal', 'high')),
  answers         jsonb not null default '{}',
  note            text,
  created_by      uuid not null,
  claimed_by      uuid,
  contact_user_id uuid,
  attempt         int not null default 0 check (attempt >= 0),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (tenant_id, id),
  foreign key (tenant_id, customer_id) references public.customers (tenant_id, id),
  foreign key (tenant_id, plant_id) references public.plants (tenant_id, id),
  foreign key (tenant_id, component_id) references public.components (tenant_id, id),
  foreign key (tenant_id, created_by) references public.profiles (tenant_id, user_id),
  foreign key (tenant_id, claimed_by) references public.profiles (tenant_id, user_id),
  foreign key (tenant_id, contact_user_id) references public.profiles (tenant_id, user_id)
);

create table public.request_photos (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id),
  request_id      uuid not null,
  r2_key          text not null,
  kind            text not null check (kind in ('overview', 'closeup', 'nameplate', 'other')),
  client_quality  jsonb,
  image_embedding extensions.vector(512),
  created_at      timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);

-- One row per stage per attempt: the checkpoint that makes retries resume (invariant 4).
create table public.pipeline_runs (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  request_id  uuid not null,
  attempt     int not null check (attempt > 0),
  stage       text not null
              check (stage in ('context', 'evidence', 'diagnosis', 'remedy', 'checks', 'confidence')),
  status      text not null check (status in ('running', 'succeeded', 'failed')),
  input_hash  text,
  output      jsonb,
  versions    jsonb,
  error       text,
  started_at  timestamptz,
  finished_at timestamptz,
  created_at  timestamptz not null default now(),
  unique (request_id, attempt, stage),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);

-- One analysis per attempt: re-analysis (e.g. after a needs_info answer) adds a row and
-- never replaces one, so every result stays explainable. The current analysis is the one
-- whose attempt equals requests.attempt. unique (request_id, attempt) means running the same
-- attempt twice can never create a second analysis (invariant 4).
create table public.analyses (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id),
  request_id      uuid not null,
  attempt         int not null check (attempt > 0),
  evidence        jsonb,
  diagnosis       jsonb,
  recommendations jsonb,
  checks          jsonb,
  confidence      numeric check (confidence between 0 and 1),
  explanation     text,
  flags           text[] not null default '{}',
  versions        jsonb,
  cache_key       text,
  created_at      timestamptz not null default now(),
  unique (request_id, attempt),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);

create table public.reviews (
  id                    uuid primary key default gen_random_uuid(),
  tenant_id             uuid not null references public.tenants (id),
  request_id            uuid not null,
  engineer_id           uuid not null,
  decision              text not null check (decision in ('approved', 'edited', 'rejected')),
  final_diagnosis       jsonb,
  final_recommendations jsonb,
  notes                 text,
  created_at            timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id),
  foreign key (tenant_id, engineer_id) references public.profiles (tenant_id, user_id)
);

create table public.messages (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id),
  request_id uuid not null,
  author_id  uuid not null,
  body       text not null,
  created_at timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id),
  foreign key (tenant_id, author_id) references public.profiles (tenant_id, user_id)
);

create table public.quotes (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id),
  request_id uuid not null,
  items      jsonb not null,
  pdf_r2_key text,
  sent_at    timestamptz,
  created_at timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);

create table public.outcomes (
  id                 uuid primary key default gen_random_uuid(),
  tenant_id          uuid not null references public.tenants (id),
  request_id         uuid not null,
  component_id       uuid not null,
  reported_life_days int check (reported_life_days >= 0),
  resolved           boolean,
  notes              text,
  created_at         timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id),
  foreign key (tenant_id, component_id) references public.components (tenant_id, id)
);

-- Case memory: created only from engineer reviews (SPEC §11). Embeddings are filled in by
-- the worker afterwards (decision 0010), so they start empty.
create table public.cases (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id),
  request_id      uuid not null,
  playbook_id     text not null,
  summary         text,
  diagnosis       jsonb,
  product_ids     uuid[] not null default '{}',
  verified        boolean not null default false,
  flagged         boolean not null default false,
  image_embedding extensions.vector(512),
  text_embedding  extensions.vector(384),
  created_at      timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);

-- Ticket chat (SPEC §12). author_id is null for the assistant's turns.
create table public.chat_messages (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id),
  request_id uuid not null,
  author_id  uuid,
  role       text not null check (role in ('user', 'assistant', 'tool')),
  body       text not null,
  sources    jsonb,
  blocked    boolean not null default false,
  created_at timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id),
  foreign key (tenant_id, author_id) references public.profiles (tenant_id, user_id)
);

create table public.knowledge_proposals (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id),
  request_id  uuid,
  kind        text not null check (kind in ('product_value', 'rule', 'weight', 'vocab')),
  target      jsonb not null,
  change      jsonb not null,
  rationale   text,
  proposed_by text not null,
  status      text not null default 'open' check (status in ('open', 'approved', 'rejected')),
  eval_report text,
  decided_by  uuid,
  decided_at  timestamptz,
  created_at  timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id),
  foreign key (tenant_id, decided_by) references public.profiles (tenant_id, user_id)
);

-- The audit trail and event bus (SPEC §3, §6). transition_request() writes here (PLAN 1.2).
create table public.events (
  id         bigint generated always as identity primary key,
  tenant_id  uuid not null references public.tenants (id),
  request_id uuid,
  type       text not null,
  payload    jsonb not null default '{}',
  created_at timestamptz not null default now(),
  foreign key (tenant_id, request_id) references public.requests (tenant_id, id)
);


-- ---------------------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------------------

create trigger requests_set_updated_at before update on public.requests
  for each row execute function public.set_updated_at();
create trigger products_set_updated_at before update on public.products
  for each row execute function public.set_updated_at();


-- ---------------------------------------------------------------------------------------
-- Indexes: the lookups from SPEC §5, plus the "rows for this request" lookups
-- ---------------------------------------------------------------------------------------

create index requests_tenant_status_idx on public.requests (tenant_id, status);
create index products_tenant_family_status_idx on public.products (tenant_id, family, status);
create index rules_tenant_playbook_status_idx on public.rules (tenant_id, playbook_id, status);

create index requests_component_idx on public.requests (component_id);
create index request_photos_request_idx on public.request_photos (request_id);
create index messages_request_idx on public.messages (request_id);
create index chat_messages_request_idx on public.chat_messages (request_id);
create index events_request_idx on public.events (request_id);
create index installations_component_idx on public.installations (component_id);

-- Similarity search: HNSW with cosine distance on every embedding column.
create index products_text_embedding_idx on public.products
  using hnsw (text_embedding extensions.vector_cosine_ops);
create index product_images_image_embedding_idx on public.product_images
  using hnsw (image_embedding extensions.vector_cosine_ops);
create index request_photos_image_embedding_idx on public.request_photos
  using hnsw (image_embedding extensions.vector_cosine_ops);
create index cases_image_embedding_idx on public.cases
  using hnsw (image_embedding extensions.vector_cosine_ops);
create index cases_text_embedding_idx on public.cases
  using hnsw (text_embedding extensions.vector_cosine_ops);


-- ---------------------------------------------------------------------------------------
-- Row-level security: on everywhere, no policies yet (PLAN 1.3), so closed by default.
-- ---------------------------------------------------------------------------------------

alter table public.tenants             enable row level security;
alter table public.customers           enable row level security;
alter table public.plants              enable row level security;
alter table public.profiles            enable row level security;
alter table public.plant_invites       enable row level security;
alter table public.playbooks           enable row level security;
alter table public.vocab_terms         enable row level security;
alter table public.products            enable row level security;
alter table public.product_images      enable row level security;
alter table public.rules               enable row level security;
alter table public.ingestion_issues    enable row level security;
alter table public.components          enable row level security;
alter table public.installations       enable row level security;
alter table public.requests            enable row level security;
alter table public.request_photos      enable row level security;
alter table public.pipeline_runs       enable row level security;
alter table public.analyses            enable row level security;
alter table public.reviews             enable row level security;
alter table public.messages            enable row level security;
alter table public.quotes              enable row level security;
alter table public.outcomes            enable row level security;
alter table public.cases               enable row level security;
alter table public.chat_messages       enable row level security;
alter table public.knowledge_proposals enable row level security;
alter table public.events              enable row level security;


-- ---------------------------------------------------------------------------------------
-- Queues (SPEC §5, §9): requests to analyze, and the dead-letter queue after 3 failures.
-- ---------------------------------------------------------------------------------------

select pgmq.create('requests');
select pgmq.create('requests_dlq');
