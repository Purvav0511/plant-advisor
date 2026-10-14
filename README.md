# Plant Advisor: Claude Code handoff

This folder is the starting point for the repository. It's set up for development on both a **Mac** and a **Windows PC (WSL2)**, with Claude Code on each.

```
CLAUDE.md                                 rules Claude Code follows in every session
docs/SPEC.md                              full technical spec (source of truth)
docs/PLAN.md                              phased build plan; each task has a "Done when" check
docs/DEV_SETUP.md                         Mac and PC setup, moving work between machines, testing on both
docs/PROGRESS.md                          shared session memory: /handoff writes it, /pickup reads it
docs/decisions/0001-cross-platform-dev.md why the setup looks like this
playbooks/wear_protection/playbook.yaml   first playbook: vocabulary, questions, schema, draft weights and rules
.claude/settings.json                     shared Claude Code permissions (blocks reading .env) + Figma plugin
.claude/skills/handoff, pickup            /handoff and /pickup commands
.mcp.json                                 Playwright MCP, so Claude can click through the app locally
.gitignore .gitattributes .editorconfig   client-data protection, LF line endings, editor defaults
.python-version .node-version .env.example  pinned versions and env var names
```

## Setup

1. Set up your first machine with `docs/DEV_SETUP.md` §4. On the PC, everything happens inside WSL2 Ubuntu.
2. Create a new **private** GitHub repository. Copy this whole folder into it, including the dot-files, and make it the first commit. The included `.gitignore` already keeps `data/raw/` and `.env` out of git.
3. Put the client's data sheets in `data/raw/wear_protection/`. They stay local until PLAN 0.5 syncs them through R2.
4. Open the repository in Claude Code, either from the terminal or from the desktop app's Code tab (choose the Ubuntu environment on the PC).

## First prompt to give Claude Code

> Read CLAUDE.md, docs/SPEC.md, docs/PLAN.md, docs/DEV_SETUP.md and playbooks/wear_protection/playbook.yaml. Don't write code yet. Then:
> 1. Summarize the architecture in 10 lines so I can confirm you understood it.
> 2. List anything in SPEC, PLAN or DEV_SETUP that is ambiguous, contradictory or risky, with your proposed resolution.
> 3. Produce a detailed implementation plan for Phase 0 and Phase 1 only: files to create, the order, tests to write first, and commands to verify each task's "Done when", on both macOS and WSL2.
> 4. Tell me exactly which accounts, keys and manual steps you need from me (tasks 0.1, 0.5, 0.6).
> Wait for my approval before starting task 0.2. When we stop, run /handoff.

## Every later session, on either machine

> /pickup

Then:

> Continue with PLAN task <ID>. Read the relevant SPEC sections first, write the tests marked 🧪 before the code, run `uv run poe check`, and stop when the task's "Done when" check passes. Summarize what changed and what's next.

Before you close the laptop or switch machines:

> /handoff

## Reminders

- The weights and rules in the playbook are **drafts** until the client's engineers approve them.
- Do task 2.1 (your own photos of worn parts) early, because the eval and the benchmark depend on it.
- Never use free-tier model APIs with client documents or photos.
- Git is the only thing that syncs code. Don't put the repo in iCloud, OneDrive or Dropbox.
