---
name: walkthrough
description: Guided reading of a pull request, file by file, in plain language, so the owner understands and can challenge every change before merging. Use when the owner says "/walkthrough <pr>" or asks to understand a PR.
disable-model-invocation: true
---

# Walkthrough

Goal: the owner reads **every changed file** of a PR, understands what it does and why, and can explain it to someone else. They are the decision-maker; you are the guide. Don't merge anything.

1. **Load the PR.** `gh pr view <pr> --json title,body,files,baseRefName,headRefName` and `gh pr diff <pr>`. If no number is given, use the PR for the current branch.

2. **Give the map first** (at most 8 lines): what the PR does in plain words, which PLAN task and decision note it belongs to, and the reading order. Start with what the rest depends on (configs, shared modules), then the code that uses them, then tests, then generated files (lockfiles: one line on how they were produced, no line-by-line reading).

3. **One file at a time.** For each file:
   - **What it is and why it exists:** one or two sentences, linked to SPEC, PLAN or a decision note.
   - **How it works:** walk through it in the order it runs, a block at a time. Show the real code (short excerpts with `path:line`) and explain each part in plain words. Define any term the owner might not know, and add new ones to `docs/handbook/glossary.md` in the PR.
   - **Choices made here:** why this approach, what the alternative was.
   - **What could go wrong:** edge cases, and which test covers them (or that none does).
   - Then **stop and ask** whether they have questions or want to challenge anything before moving on. Wait for the answer.

4. **When the owner challenges something,** answer honestly. If they're right, or the code is unclear, say so, fix it on the PR branch (tests and `uv run poe check` first), and note the change in the PR's reading guide. Don't defend code just because it exists.

5. **Finish** with a short recap: what they've read, any open questions, and any changes made during the walkthrough. Remind them that ticking `I read every changed file` in the PR description unlocks `uv run poe merge <pr>`. Never tick it for them.
