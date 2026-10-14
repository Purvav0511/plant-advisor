# 0017: This design conversation lives in the repo

**Context:** the owner develops on this PC (WSL2) and on a Mac. Claude Code chat history stays on the machine where it ran.

**Decision:** everything decided in chat is written to `docs/decisions/`, `docs/SPEC.md`, `docs/PLAN.md` and `docs/PROGRESS.md` before the session ends (`/handoff`). A new session on either machine starts with `/pickup` and reads those, never the chat. Decisions 0002–0017 come from the 2026-10-13 design session on the PC.
