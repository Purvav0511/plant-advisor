---
name: pickup
description: Start a work session on this machine. Syncs with GitHub, refreshes dependencies, runs the doctor and the checks, and summarizes where the work stands from docs/PROGRESS.md before any code is written.
disable-model-invocation: true
---

# Pickup

1. **Check local state first.**
   - Get the machine label with `uv run poe machine` (or the OS name if that task doesn't exist yet).
   - Run `git status` and `git branch --show-current`.
   - If there are uncommitted changes, **stop and ask** what to do with them. They may be unfinished work from this machine's last session.

2. **Find the latest work.**
   - Run `git fetch --prune`.
   - List the most recently updated branches: `git for-each-ref --sort=-committerdate refs/remotes/origin --count=5 --format="%(refname:short) | %(committerdate:relative) | %(subject)"`.
   - The newest `task/*` branch, or `dev`, is usually where the last `/handoff` pushed. If it isn't obvious, ask.

3. **Sync.**
   - Check out that branch (tracking the remote) and run `git pull --ff-only`.
   - If the fast-forward fails because both machines have commits, **stop and explain**. Don't merge, rebase or reset without approval.

4. **Refresh dependencies.** These are quick no-ops when nothing changed:
   - `uv sync`
   - `pnpm install`
   - If the last log entry says new raw files were added, run `uv run poe raw-pull`.

5. **Read the context.**
   - The story for the current PLAN task on the board (`gh issue list --label story --state open`), and move it to *In progress* when work starts.
   - Its subtasks (`gh api repos/{owner}/{repo}/issues/<story>/sub_issues`). If it has none yet, propose a split into subtasks of 1–3 files each and create them once the owner agrees (CLAUDE.md "Tracking work").
   - The **Current state** block and the newest **Log** entry in `docs/PROGRESS.md`.
   - The current task in `docs/PLAN.md`, and the SPEC sections that task needs.

6. **Run the checks.**
   - `uv run poe doctor`: it checks tools, env var names against `.env.example`, database reachability, migration drift and line endings.
   - `uv run poe check`.
   - Before PLAN task 0.2 exists, skip the `poe` steps and say so.

7. **Handle "On the other machine".**
   - Do the steps from the log entry that you can do, such as applying a migration that the doctor reports as missing.
   - List the steps that need the human, such as filling in values for new env vars in `.env` from the password manager.

8. **Report** in at most eight lines, then wait for a go-ahead before writing code:
   - the machine and branch
   - where the task stands
   - the doctor and check results
   - manual steps that are still open
   - the proposed next step
