# 5. Working with AI

How we use Claude on this project, and habits that carry over to a professional team. The core idea: **the AI does a lot of the typing; you stay the decision-maker and the one accountable for what ships.**

## "Threads": what people usually mean

In most teams, a *thread* is **one AI conversation dedicated to one piece of work**: one ticket, one bug, one question. Some teams run several threads in parallel, each on its own task. It can also mean a chat thread in Slack or Teams where people @-mention an AI assistant, which then answers with the whole thread as context. (We don't know any specific company's internal setup; these are the common patterns.)

Why it matters: an AI conversation has a limited memory, and mixing topics makes it worse. One task per thread keeps it focused, and makes the work easy to review, resume or hand over.

### How to do threads here

| What you want | How |
|---|---|
| **One thread per task** | Start a new Claude Code session for each board story. In the desktop app, open a new session; in a terminal, run `claude` in the repo. Begin with `/pickup` and the story number. |
| **Come back to a thread later** | Pick it from the desktop app's session list, or run `claude --continue` (the last one) or `claude --resume` (choose one) in the terminal. |
| **Several threads in parallel** | Give each thread its own copy of the repo (a git *worktree*), so they never edit the same files: `claude --worktree task-0.5` starts a session in a fresh worktree. Use this only for tasks that don't touch the same code. |
| **Continue on the other machine** | `/handoff` here, `/pickup` there. The thread's *outcome* moves through the repo (`docs/PROGRESS.md`). |
| **A long job you don't want to babysit** | A cloud session (desktop app → *Cloud*), visible from your phone and both machines. |
| **Ask about a PR or issue** | Comment on GitHub and work through it in a session; optionally, the Claude GitHub app can respond to `@claude` mentions (it uses API credits). |

## Habits that make AI work professionally

### 1. Start from a written task
Every thread starts from a board story with a clear "Done when." The AI does far better with a precise target, and you can tell when it's finished.

### 2. Plan before code
For anything non-trivial, ask for a plan first and read it before any code is written. In Claude Code, *plan mode* does this. Most expensive mistakes are wrong plans, not wrong code.

### 3. Keep each change small
One story, one branch, one PR. Small PRs are easy to review; huge AI-generated PRs hide mistakes.

### 4. Make it prove things
Ask for tests first, then code. Accept "it works" only with evidence: a passing check, a command's output, a screenshot. Our rule: `uv run poe check` must be green before any commit.

### 5. Read every file before it merges
You're the author of record, even when AI typed it. On this project that's enforced:
- Every PR has a **reading guide**: each changed file in reading order, what it is, why it exists, and what to look at closely.
- **You review before anything is committed.** When Claude finishes a task, it stops with the changes uncommitted and gives you a reading order. Open the project in VS Code (`code ~/code/plant-advisor`), press Ctrl+Shift+G for *Source Control*, and click each file for a side-by-side diff. Say "commit" when you're satisfied.
- `/walkthrough <pr>` takes you through it one file at a time in plain words, and stops after each file for your questions.
- Challenge anything: "why this way?", "what if this is empty?", "what's the alternative?" If the answer isn't good enough, the code changes.
- `uv run poe merge` refuses until you tick **I read every changed file** in the PR. If you can't explain a change to a colleague, it isn't ready to merge.

### 6. Write the project's memory down
AI sessions forget; repos don't. Our memory is `CLAUDE.md` (rules), `docs/decisions/` (why), this handbook (plain words) and `docs/PROGRESS.md` (where we are). Any decision made in chat goes into one of these before the session ends.

### 7. Protect data
- Never paste passwords, keys or client documents into an AI tool your company hasn't approved.
- Use company-approved accounts. Know whether the tool keeps or trains on your data.
- Here, `.env` is blocked from Claude, hooks refuse to commit client data, and only paid AI APIs touch client data.

### 8. Verify facts
AI knowledge has a cutoff date and can be confidently wrong. For versions, prices, limits and laws, have it check the live source (it did this for GitHub's plan limits) or check yourself.

### 9. Use AI as a reviewer too
Ask a fresh session to review a PR (`/code-review`, `/security-review`). A second pass with clean context often catches what the first missed.

### 10. Reset instead of arguing
If a thread goes in circles, stop. Start a new session with a short, clear brief that includes what you learned. Long, confused threads get worse, not better.

### 11. Be open about AI use
Follow your team's policy. Our commits carry a `Co-Authored-By: Claude` line, so it's always clear AI contributed.

### 12. Automate the routine
Repeated instructions become skills or commands (`/pickup`, `/handoff`); repeated checks become hooks and CI. Then the AI follows the process every time without being reminded.

## Our session routine

1. Pick a story on the board; move it to *In progress*.
2. New session → `/pickup` → "Work on story #N (PLAN x.y)."
3. Approve the plan, then let it work; review as it goes.
4. `/handoff` at the end, or when switching machines. It opens the PR with a reading guide.
5. `/walkthrough <pr>`: read every file, ask and challenge until it's clear.
6. Tick **I read every changed file** in the PR, then `uv run poe merge <pr>`.

## How companies commonly use AI (to recognize it at work)

- **Coding assistants** in the editor or terminal (like Claude Code) working from tickets.
- **AI code review** on every pull request, as a second reviewer next to a human.
- **Chat assistants in Slack or Teams threads**, answering with the thread's context.
- **Internal knowledge search** over documents and wikis.
- **Agents** handling routine, well-defined tasks end to end, with a human approving the result.
- **Guardrails and governance:** approved tools only, data classification, logging, and human sign-off for anything customer-facing. Same idea as our ticket chat's guardrails.
