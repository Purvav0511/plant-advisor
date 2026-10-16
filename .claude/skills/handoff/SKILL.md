---
name: handoff
description: End a work session so it can continue on the other machine or in a fresh session. Runs the checks, updates docs/PROGRESS.md, commits to the task branch and pushes it.
disable-model-invocation: true
---

# Handoff

Goal: someone who opens this repo on the other machine, with no access to this conversation, can continue in under five minutes. Local Claude Code history does not travel between machines; the repo does.

1. **Look at the state.** Run `git status`, `git branch --show-current` and `git log --oneline -5`. Get the machine label with `uv run poe machine` (if that task doesn't exist yet, use the OS name).
   - If you're on `dev` or `main` with changes, create a branch from `dev` first: `task/<plan-id>-<short-slug>`, for example `task/3.4-diagnosis-scoring`. Never commit on `dev` or `main` (the hooks refuse it).

2. **Run the checks.** Run `uv run poe check`. Don't start fixing unrelated failures now. Record the result honestly, including which tests fail.

3. **Update `docs/PROGRESS.md`.**
   - Replace the **Current state** block: branch, PLAN task and status (done / in progress / blocked), the concrete next step, blockers, the check result, and the "On the other machine" list.
   - Add a new entry at the **top** of **Log**, headed `### <YYYY-MM-DD> · <machine> · <plan-id>`, with:
     - **Changed:** 3–6 bullets naming files or areas.
     - **Decisions:** one line each, linking `docs/decisions/NNNN-*.md` if you wrote one.
     - **Next:** the first concrete step for the next session.
     - **On the other machine:** manual steps the other machine needs, such as new env var *names* (never values), new tools, migrations to apply, or new raw files to pull with `uv run poe raw-pull`. Write "nothing" if there are none.

4. **Run a safety check before committing.** Nothing under `data/raw/`, `evals/photos/private/` or `ingestion/reports/`, and no `.env` file, may be staged. Check with `git status --porcelain` after staging. If any of these is staged, unstage it and stop.
   - If new client documents or private photos were added on this machine, run `uv run poe raw-push` so the other machine can pull them.

5. **Commit** the task's files and `docs/PROGRESS.md`, but only after the owner has reviewed the uncommitted diff in VS Code and said "commit" (CLAUDE.md "Review before committing"). If they haven't yet, update `docs/PROGRESS.md`, list the changed files in reading order, and stop here.
   - Commit **one subtask at a time, 1–3 files each**, titled `<plan-id>.<letter>: <summary>` (CLAUDE.md "Tracking work"). Split further rather than exceed 3 files.
   - If you wrote a decision note this session, its plain-language entry in `docs/handbook/03-decisions.md` must be in the same PR.
   - If the task's "Done when" check passes, use the message `<plan-id>: <summary>`.
   - Otherwise use `<plan-id>: WIP - <what's left>`.
   - Never use `--no-verify`.

6. **Push** with `git push -u origin <branch>`. Never force-push. If the push fails (network or auth), say so plainly: the handoff isn't finished until the branch is on GitHub.
   - If the task's "Done when" passes and no PR exists yet, open one into `dev` from `.github/pull_request_template.md`, with `Closes #<story>`, `Closes #<subtask>` for each subtask, and a complete **Reading guide** organized by subtask. Leave the owner's sign-off box unticked.
   - Move the story on the board: *In review* when a PR is open, otherwise *In progress*.

7. **Report** in at most six lines:
   - the branch you pushed and the check result
   - the next step
   - anything the other machine needs, and the fact that you run `/pickup` there
