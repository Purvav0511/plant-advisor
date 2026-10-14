# 0019: Branches, environments and CI/CD

**Context:** the owner wants feature branches, lower environments and a production branch, with real CI/CD practice, but no paid plans until after the MVP. On a free GitHub account, a private repo gets no branch protection, environment secrets or required reviewers, and Supabase's free plan allows two active projects.

**Decision**
- **Branches:** `task/*` and `fix/*` → PR → `dev` (integration, the default branch) → release PR → `main` (production). `hotfix/*` → PR → `main`, then a back-merge PR `main` → `dev`. Feature PRs are squashed; releases and back-merges use merge commits.
- **Environments:** `dev` (hosted, deployed from `dev`) and `prod` (hosted, deployed from `main`) use the two free Supabase projects. `test` is CI: a throwaway Supabase and the full suite on every PR. `uat` and `prodtest` are added before the pilot as deploy targets, not branches.
- **Build once, promote:** images are tagged by the git **tree hash**. A release merge into `main` has the same tree as the tested `dev` commit, so prod deploys the build `dev` already tested; if no build exists for main's tree, the deploy refuses (PLAN 7.3). The web app reads a per-environment `config.json` at runtime so one build serves every environment.
- **Free stand-ins for paid protection:** a `pre-commit` hook refuses commits on `main`/`dev`; a `pre-push` hook refuses pushes to them; `uv run poe merge <pr>` merges only allowed, green PRs; the `guard` workflow checks every commit on `main`/`dev` came from such a PR and opens an issue if not. Rules live in `scripts/branch_rules.py`.
- **CI:** `ci.yml` (lint, unit, web build, secret scan, image builds with smoke tests; integration, eval and e2e switch on when their files exist), `cross-os.yml` weekly on Windows and macOS, `security.yml` weekly audits, Dependabot into `dev`. Actions are pinned by commit SHA.
- **Switch to paid** when a second developer joins or before real plant users touch a shared environment: GitHub Pro (branch protection, environment secrets) and Supabase Pro (uat, prodtest, prod). The stand-ins then become redundant; the pipeline stays the same.

**Why:** what reaches production is exactly what was tested, at no cost during the MVP.

**Alternatives:** a branch per environment (drifts, and "what's live" becomes unclear); Jenkins (free software, but a paid always-on server and maintenance, and it still can't block merges on GitHub); making the repo public (exposes the client's catalog-derived logic).
