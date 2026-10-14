# 0001: Develop on a Mac and a Windows PC with one setup

**Context:** Development happens on a Mac and a Windows PC, with Claude Code on both, and sometimes in Claude Code cloud sessions. Production runs in Linux x86_64 containers (Cloud Run). Local Claude Code session history doesn't sync between machines.

**Decision**
- **The PC develops inside WSL2 (Ubuntu).** The repo lives in the Linux filesystem, and Claude Code runs inside WSL (from the terminal, or from the Desktop app's WSL environment).
- **One task runner that runs on every OS:** poethepoet (`uv run poe <task>`). Helper scripts are written in Python under `scripts/`, never as shell scripts.
- **Lockfiles define the environment:** `uv.lock` (universal across platforms) and `pnpm-lock.yaml`. The versions are pinned in `.python-version` (3.12) and `.node-version` (22, which matches cloud sessions).
- **LF line endings everywhere,** set by `.gitattributes`.
- **Shared dev services:** one hosted Supabase dev project and one R2 dev bucket, used by both machines and the phone. Local Supabase in Docker is used only for integration tests. Client documents sync through a private R2 prefix, never through git.
- **Pure-Python libraries where a native one would differ by OS:** ReportLab for PDFs (WeasyPrint needs GTK on Windows) and pypdfium2 for rasterizing (poppler needs separate installs).
- **Session continuity goes through the repo:** `docs/PROGRESS.md` plus the `/handoff` and `/pickup` skills. Cloud sessions and Remote Control are optional extras.

**Why:** WSL2 makes the PC match production, CI and cloud sessions (all Linux x86_64), so the Mac is the only "different" machine. It also enables Claude Code sandboxing, which native Windows doesn't support. Writing state into the repo works on every surface and survives context compaction.

**Alternatives considered**
- **Make:** not available on native Windows.
- **`just`:** needs a POSIX shell on Windows.
- **Native Windows development:** no sandboxing, and different from production.
- **Dev containers:** identical environments, but heavier; possible later.
- **A local database per machine:** data drifts between machines, and ingestion would have to be re-run on each one.
