# 6. The board

We track work on a free **GitHub Project** linked to the repo, which works like a lightweight Jira.

## How the work is organized

| Jira term | Here | Example |
|---|---|---|
| **Epic** | An issue labelled `epic`, one per PLAN phase | *Epic: Phase 1: Data model and knowledge* |
| **Story** | An issue labelled `story`, one per PLAN task, attached to its epic as a sub-issue | *1.6 Rule evaluator* |
| **Sprint / cycle** | The project's **Cycle** field: two-week iterations | *Cycle 1 (Oct 13 – Oct 26)* |
| **Blocker** | Label `blocked-client` (waiting on the client) or `needs-human` (needs you) | *Client data: missing composition values* |

Other labels: `tests-first` (write tests before code), `phase-0` … `phase-7`.

## Statuses

**Backlog** → **Ready** (planned for this cycle) → **In progress** → **In review** (PR open, waiting for your reading and merge) → **Done** (PR merged; the story closes automatically).

## Views

- **Board:** columns by status, for the current cycle. "What's happening now?"
- **Backlog:** a table of everything not done, grouped by epic. "What's left?"
- **Roadmap:** a timeline by cycle. "What's coming in the next weeks?"

## The routine

- **Start of a cycle (every two weeks):** pick the next stories in PLAN order, set their Cycle, move them to *Ready*. Check `blocked-client` and `needs-human` items first, since they take the longest.
- **Each session:** `/pickup` moves the story to *In progress*; `/handoff` moves it to *In review* when the PR is open.
- **After merging:** the PR's `Closes #N` closes the story; the epic's progress bar updates.
- **New work that isn't in PLAN** (a bug, an idea): open an issue, label it, attach it to the right epic, and leave it in *Backlog* until it's planned.

## Why GitHub Projects and not Jira

| Option | Pros | Cons |
|---|---|---|
| **GitHub Projects (chosen)** | Free; lives next to the code; PRs close stories automatically; Claude can update it with the `gh` command | Fewer reporting features than Jira |
| Jira (free plan, up to 10 users) | Industry standard; rich reports | Separate tool; linking to GitHub needs setup; Claude can't update it from here |
| Notion or Trello boards | Flexible | Manual linking to code; drifts from reality |

If your company uses Jira, the same structure (epics, stories, cycles, statuses) carries over directly.
