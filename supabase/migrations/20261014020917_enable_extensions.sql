-- PLAN 0.4: extensions the schema relies on (SPEC §5).
-- vector: pgvector, for image and text embeddings with HNSW indexes.
-- pgmq: the Postgres message queue behind `requests` and `requests_dlq`.
create extension if not exists vector with schema extensions;
create extension if not exists pgmq;
