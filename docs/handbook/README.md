# Plant Advisor handbook

The plain-language companion to the technical docs. Read this to understand the project, and to explain it to someone else: a manager, a client, a new teammate.

| Page | What it answers |
|---|---|
| [1. The product](01-the-product.md) | What are we building, for whom, and how does a request flow through it? |
| [2. The stack](02-the-stack.md) | Which tools and services do we use, what does each one do, and why that one? |
| [3. Decisions](03-decisions.md) | Every design decision: what we chose, why, what else we considered, pros and cons |
| [4. How we build and ship](04-how-we-build-and-ship.md) | Branches, environments, automated checks, and how a change reaches production |
| [5. Working with AI](05-working-with-ai.md) | How we use Claude on this project, and the habits that carry over to a professional team |
| [6. The board](06-the-board.md) | How epics, stories and cycles are tracked on the GitHub project board |
| [Glossary](glossary.md) | Short definitions of every technical term used here |

## How this handbook stays current

- The technical source of truth is still `docs/SPEC.md`, `docs/PLAN.md` and `docs/decisions/`. This handbook explains them; it never contradicts them.
- **Every new decision note gets a plain-language entry in [3. Decisions](03-decisions.md) in the same PR.** CLAUDE.md makes this a rule, and `/handoff` checks it.
- When a new tool joins the stack, it gets a row in [2. The stack](02-the-stack.md).
- Unfamiliar word? Add it to the [glossary](glossary.md).
