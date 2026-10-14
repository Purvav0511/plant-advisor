# 3. Decisions, in plain words

Each entry explains one decision note from `docs/decisions/`: what we decided, why, what else we considered, and the trade-offs. The technical note (linked in each heading's first line) has the exact details.

Three priorities shaped almost every choice:
1. **Precision and consistency first.** The same input should always give the same answer, and every answer should be traceable.
2. **Free during the MVP**, with a clear path to paid services later.
3. **Easy to grow:** more product families, more clients, possibly AWS, without rewrites.

---

## 0001: One setup for the Mac and the Windows PC
*Technical note: [0001](../decisions/0001-cross-platform-dev.md)*

**Decision:** the PC develops inside WSL2 (a Linux system that runs inside Windows). Both machines use the same tools, the same lock files and the same commands. Everything that must move between machines goes through GitHub.

**Why:** production runs on Linux, so developing on Linux (WSL) means fewer "works here, breaks there" surprises.

| Option | Pros | Cons |
|---|---|---|
| **WSL2 on the PC (chosen)** | Matches production; fast; supports Claude Code's sandbox | A Linux layer to learn |
| Develop directly on Windows | Familiar | Differs from production; no sandbox |
| Dev containers | Identical everywhere | Heavier; slower to start |

---

## 0002: Recommendations from rules, not vector search
*Technical note: [0002](../decisions/0002-recommendations-from-rules-not-rag.md)*

**Decision:** the AI *describes* what it sees, then code scores the wear causes with fixed weights, rules decide which products qualify, and the AI only ranks those qualified products, citing data-sheet values.

**Why:** the popular shortcut, "search the documents and let the AI pick" (called RAG), can return a different answer each time, and can recommend a product that doesn't fit or doesn't exist. Our way gives the same answer for the same input, and every recommendation can be explained line by line.

| Option | Pros | Cons |
|---|---|---|
| **Scoring + rules + AI ranking (chosen)** | Repeatable; explainable; new products qualify automatically once approved | More upfront work: weights and rules need engineers' approval |
| Plain RAG (search + AI picks) | Quick to build | Inconsistent; can hallucinate products; hard to audit |
| AI decides everything | Least code | Least predictable; impossible to guarantee |

We still build plain RAG as a **baseline** and measure both, so "ours is better" is a measured fact, not a claim.

---

## 0003: Every product has a stable code
*Technical note: [0003](../decisions/0003-product-codes.md)*

**Decision:** each product gets a short permanent code (like `wp-xyz-plate`) besides its database ID.

**Why:** database IDs change when a product's data is corrected (a new version) and differ between test and real databases. Tests and history need a name that never changes.

**Alternatives:** use the product name (names get corrected); remap IDs everywhere (fragile).

---

## 0004: Plants join by invite; history is shared and stored on the server
*Technical note: [0004](../decisions/0004-plant-onboarding-and-history.md)*

**Decision:** we pre-load customers, plants and machines. A technician joins with an invite link or plant code plus their own email, and sees every request from their plant, whichever phone sent it. Unsent drafts stay on the phone so a weak signal doesn't lose photos.

| Option | Pros | Cons |
|---|---|---|
| **Personal accounts + invite (chosen)** | Know who did what; revoke one person; history shared across the plant | One extra step to join |
| One shared plant login | Simplest | No accountability; can't revoke one person |
| History only on the phone | No server storage | Lost with the phone; invisible to coworkers |

---

## 0005: The technician sees the recommendation early, marked "preliminary"
*Technical note: [0005](../decisions/0005-plant-sees-preliminary-recommendation.md)*

**Decision:** results appear right away as *Preliminary*, then *Confirmed* after an engineer approves. If confidence is low or a check failed, products are hidden until an engineer reviews. Call, text and message buttons connect the technician to their contact.

| Option | Pros | Cons |
|---|---|---|
| **Show early with safeguards (chosen)** | Fast for the technician; weak results never shown as advice | Technician may act before confirmation (mitigated by the label) |
| Hide until reviewed | Safest | Slower; the owner rejected it |
| Show everything immediately | Fastest | Weak or wrong output looks like advice |

---

## 0006: Separate engineer and sales permissions
*Technical note: [0006](../decisions/0006-engineer-and-sales-roles.md)*

**Decision:** engineers approve diagnoses; sales sends quotes and updates status. One person can hold both roles.

**Why:** keeps the guarantee that "an engineer approved this" even when sales moves fast. Small teams just give one person both roles.

---

## 0007: The ticket chat has guardrails and can't change knowledge
*Technical note: [0007](../decisions/0007-ticket-chat-guardrails-learning.md)*

**Decision:** staff can chat with an AI about each ticket. It's restricted in layers: it refuses off-topic questions, treats photos and messages as data (not instructions), can only read our own company's data, has its answers checked by code, and has limits on cost and steps. When it spots an error, it writes a **proposal**; an admin approves it only if the test suite shows accuracy didn't drop.

**Why:** if a chat could change product data or rules, one wrong conversation could quietly corrupt every future recommendation.

| Option | Pros | Cons |
|---|---|---|
| **Learn only from reviews and approved proposals (chosen)** | Every change is reviewed, versioned, reversible | Learning is slower |
| Learn automatically from chats | Fast | One bad chat corrupts the system |
| Retrain (fine-tune) the AI model | Could improve the model itself | Needs lots of data; costly; hard to audit |

---

## 0008: "Do we need more photos?" is a fixed step, not a free-roaming AI agent
*Technical note: [0008](../decisions/0008-photo-quality-gate.md)*

**Decision:** the phone checks blur and brightness instantly; then the analysis reports whether photos are usable and which view is missing, and asks the technician for exactly that.

**Why:** same result as an "agent," but predictable, cheap and testable.

---

## 0009: Cloud Run now, with a path to AWS
*Technical note: [0009](../decisions/0009-worker-trigger-and-hosting.md)*

**Decision:** host on Google Cloud Run for the MVP. Everything is a Docker container and the queue is swappable, so moving to AWS (Lambda or ECS with SQS) later is a configuration change. We decide at deployment time with measured numbers.

**Why volume doesn't decide it yet:** at hundreds or even a few thousand requests a day, Cloud Run and AWS both handle the load easily. The AI model calls cost far more than hosting. Choose AWS if the company's infrastructure or compliance requires it, not for capacity.

| Option | Pros | Cons |
|---|---|---|
| **Cloud Run now (chosen)** | Real free tier; runs our containers as-is; scales to zero | Not AWS, if the company standardizes on AWS |
| AWS Lambda + SQS | AWS-native; free tier | Heavy image models start slowly; 15-minute limit per run |
| AWS ECS Fargate | Good fit for the worker | No free tier |

---

## 0010: The worker computes case "fingerprints"
*Technical note: [0010](../decisions/0010-case-embeddings-in-worker.md)*

**Decision:** when an engineer approves a ticket, it becomes a "case." The fingerprints (embeddings) used to find similar cases are computed by the worker, not the API.

**Why:** only the worker loads the heavy image models; keeping them out of the API keeps it fast and small.

---

## 0011: Our own test photos are stored in the repo
*Technical note: [0011](../decisions/0011-eval-photos-and-replay.md)*

**Decision:** your own photos of worn parts live in `assets/eval-photos/`. Client photos never enter the repo. Tests replay recorded AI responses, so they're free and give identical results on every machine.

**Why:** the automated accuracy test needs real photos, and running it on every change protects accuracy.

---

## 0012: The database enforces who sees what
*Technical note: [0012](../decisions/0012-api-rls-context.md)*

**Decision:** the API runs every database query "as the user," so the database's own security rules (RLS) apply.

**Why:** if a bug in our code forgot a filter, the database would still refuse to show another company's data. Two locks instead of one.

---

## 0013: How request status changes work
*Technical note: [0013](../decisions/0013-transitions-and-attempts.md)*

**Decision:** a request's status (submitted, analyzing, ready for review, …) can only change through one database function that checks the move is allowed and records it. If two engineers click "claim" at the same moment, exactly one wins.

**Why:** a clean, auditable timeline for every request, and no impossible states.

---

## 0014: Website detail pages use `?id=` links
*Technical note: [0014](../decisions/0014-static-export-routing.md)*

**Decision:** pages like a ticket use links such as `/console/request?id=123`.

**Why:** the website is built as plain static files (free hosting). Static sites can't have a page for every possible ticket ID, so the page reads the ID from the link and loads the data.

**Trade-off:** slightly less pretty links, in exchange for free, fast hosting.

---

## 0015: Anthropic is the first AI provider
*Technical note: [0015](../decisions/0015-model-provider.md)*

**Decision:** use Anthropic's paid API first, behind our gateway so others can be added.

**Why:** paid and doesn't train on our data, which the client-data rule requires; strong with images and structured answers.

**Alternatives:** OpenAI or Google (viable later through the same gateway); free AI APIs (forbidden for client data).

---

## 0016: Screens are designed in Figma first
*Technical note: [0016](../decisions/0016-figma-first-ui.md)*

**Decision:** every screen is designed in Figma, then built to match, with colours and fonts shared across the app.

**Why:** consistent design, fewer rebuilds, and designs others can review before code exists.

---

## 0017: The conversation's decisions live in the repo
*Technical note: [0017](../decisions/0017-context-across-mac-and-pc.md)*

**Decision:** anything decided in a Claude chat is written into the repo before the session ends. `/handoff` saves; `/pickup` reads.

**Why:** chat history stays on the machine where it happened; the repo goes everywhere, including to future teammates.

---

## 0018: How the Python code is organized
*Technical note: [0018](../decisions/0018-python-package-layout.md)*

**Decision:** six Python packages (core, api, worker, mcp, ingestion, evals) in one workspace, each named `advisor_…`.

**Why:** each service installs only what it needs (the API never loads image models), and names can't clash with outside libraries.

---

## 0019: Branches, environments and CI/CD
*Technical note: [0019](../decisions/0019-branches-environments-cicd.md)*

**Decision:**
- Work happens on task branches → merged into `dev` (testing ground) → released into `main` (production).
- Every change is checked automatically (CI) before it can be merged.
- The exact build that passed testing is the one that goes live; nothing is rebuilt for production.
- GitHub's paid branch protection is replaced for now by free guards: hooks on your machine, a safe-merge command, and a watchdog workflow.

| Option | Pros | Cons |
|---|---|---|
| **dev → main with build-once promotion (chosen)** | What's live is exactly what was tested; free | Free guards can be bypassed by someone determined |
| One branch per environment (dev, qa, uat, prod…) | Familiar | Branches drift; unclear what's actually live |
| Jenkins | Free software; approval buttons | Paid always-on server and upkeep; still can't block GitHub merges |
| Pay for GitHub Pro now | Real enforcement | About $4/month; deferred until after the MVP |

**When we start paying:** when a second developer joins, or before real plant users use a shared environment (the pilot).

---

## 0020: How library updates are allowed in
*Technical note: [0020](../decisions/0020-dependency-update-policy.md)*

**Decision:** a new version of any library must be **at least 14 days old** before we use it, and **major versions** (like TypeScript 5 → 7) are never updated automatically. They become a planned board story instead.

**Why:** Dependabot's first big update tried to jump several tools a whole major version, using releases only days old. CI stopped it, but we don't want safety to depend on luck. Very new releases are where broken or even malicious versions show up, and major versions can quietly change behaviour.

| Option | Pros | Cons |
|---|---|---|
| **14-day wait, no automatic majors (chosen)** | Avoids fresh broken releases; big changes are deliberate | Updates arrive two weeks later |
| Accept anything that passes CI | Always up to date | CI can't catch every behaviour change |
| Turn off automatic updates | No noise | We'd miss security fixes |

Urgent **security** fixes skip the waiting period, so they still arrive quickly.
