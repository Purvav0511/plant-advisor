# 0011: Own eval photos are committed; recordings are keyed by content hashes

**Context:** CI must run the eval without private files, but Stage 2 needs photo bytes for embeddings and the cache key.

**Decision**
- The owner's own photos of worn parts are committed under `assets/eval-photos/` (JPEG, long side ≤ 1600 px). Client photos stay in `evals/photos/private/` (gitignored, synced via R2) and their cases run locally only.
- Replay recordings are keyed by `sha256(task, model, prompt_version, rendered prompt, photo sha256s)`. A missing recording fails with "re-record with `uv run poe eval --live`"; it never silently calls a model.
- Unit tests use a fake embedder, so `poe check` never loads PyTorch.

**Alternatives:** keep all photos private (CI can't run the eval gate).
