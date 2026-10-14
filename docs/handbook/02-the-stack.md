# 2. The stack

Every tool and service we use, grouped by what it does. Each entry says what it is in plain words, why we picked it, what else we could have used, and the trade-offs. Costs are for the MVP; see [decision 0019](03-decisions.md#0019-branches-environments-and-cicd) for when we'd start paying.

## The big picture

```
 Phone app / Console (Next.js website)
        │ sends photos straight to storage (Cloudflare R2)
        │ sends the request to
        ▼
 API (Python, FastAPI) ── saves it and puts it in a queue ──▶ Database (Supabase Postgres)
                                                                 │
 Worker (Python) ◀── picks up the request from the queue ────────┘
        │ runs the 7-step analysis, calls the AI model (Anthropic)
        ▼
 Result saved ──▶ console updates live; technician sees the preliminary result
```

---

## Languages and project tools

### Python 3.12 (backend language)
- **What:** the programming language for everything behind the scenes: the API, the worker, the analysis.
- **Why:** the best ecosystem for AI, image models and PDF processing.
- **Alternatives:** TypeScript/Node (weaker AI and image libraries), Go or Java (more code for the same result).
- **Pros:** huge library choice; fast to write. **Cons:** slower than compiled languages (irrelevant here: we wait on AI calls, not on Python).

### TypeScript (frontend language)
- **What:** JavaScript with types; the language of the website.
- **Why:** catches mistakes before the code runs; the standard for modern web apps.
- **Alternatives:** plain JavaScript (more runtime bugs).

### uv (Python package manager)
- **What:** installs Python and every library at exactly the versions in `uv.lock`, so the Mac, the PC and the cloud all match.
- **Why:** very fast, and one lock file covers macOS, Linux and Windows.
- **Alternatives:** pip with requirements files (no single cross-platform lock), Poetry (slower, weaker workspace support), conda (heavy).
- **Pros:** identical environments everywhere. **Cons:** newer tool, so fewer people know it yet.

### pnpm (JavaScript package manager)
- **What:** the uv of the JavaScript world, with `pnpm-lock.yaml` as its lock file.
- **Alternatives:** npm (slower, bigger disk use), yarn (similar; pnpm is stricter about undeclared packages).

### poethepoet ("poe", the command runner)
- **What:** the short commands we type, like `uv run poe check`. Each one is defined once in `pyproject.toml`.
- **Why:** runs the same on Mac, Linux and Windows.
- **Alternatives:** Make (not on Windows), `just` (needs a Unix shell on Windows), npm scripts (Node-centric).
- **Pros:** one command list for every machine. **Cons:** one more tool to learn.

### Quality tools: ruff, pyright, eslint, prettier, pytest
- **ruff:** checks and formats Python code (style and common bugs). Replaces several older tools at once.
- **pyright:** checks Python *types*: catches "this might be empty" bugs before they run.
- **eslint and prettier:** the same two jobs for the website code.
- **pytest and Hypothesis:** run the automated tests. Hypothesis generates hundreds of random inputs to find edge cases.
- **pre-commit:** runs quick checks every time you commit, and blocks client data, secrets and commits on protected branches.

---

## Backend services

### FastAPI (the API)
- **What:** the front desk. The apps talk to it; it checks who you are, saves the request, and queues it. It never calls the AI itself, so it always answers fast.
- **Alternatives:** Django (heavier, built for server-rendered pages), Flask (fewer built-in checks).
- **Pros:** automatic input validation and API docs; fast. **Cons:** fewer batteries included than Django (we don't need them).

### The worker
- **What:** the back office. It takes requests from the queue and runs the seven-step analysis. It can scale to zero when idle.
- **Why separate from the API:** analysis takes a while and loads heavy image models; the API stays light and quick.

### MCP server
- **What:** a set of read-only "tools" the AI chat can use: look up a product, find similar past cases, read a component's history. MCP (Model Context Protocol) is a standard way to give an AI model tools.
- **Why:** the chat can only *read* through these tools, limited to our own company's data. That's a guardrail by design.
- **Alternatives:** letting the AI query the database directly (unsafe), custom tool code per model vendor (locks us in).

### Docker
- **What:** packs each service with everything it needs into a sealed box (an *image*) that runs the same anywhere.
- **Why:** the image tested in CI is the exact one that runs in production, on Google Cloud today or AWS later.
- **Alternatives:** installing directly on servers (drift, "works on my machine").

---

## Data and storage

### Supabase (database, login, live updates)
- **What:** a hosted Postgres database plus sign-in (email codes), live updates to the console, and file permissions.
- **Why:** one service does five jobs: database, vector search (pgvector), job queue (pgmq), login and real-time updates. Free tier for development.
- **Alternatives:** AWS RDS plus Cognito plus SQS (three services, more setup, costs from day one), Firebase (not a relational database; weaker for our structured product data), Neon (database only; we'd add login separately).
- **Pros:** fewer moving parts; Postgres is standard and portable. **Cons:** free projects pause after 7 days idle, and only two are free; production needs the paid plan.

### Postgres features we rely on
- **pgvector:** stores *embeddings* (lists of numbers that capture what an image or text "looks like") and finds similar ones. Used to find similar past cases.
- **pgmq:** a job queue inside the database. A request and its queue entry are saved together, so a request can never be "saved but not queued."
- **Row-level security (RLS):** the database itself refuses to show one company's rows to another, even if the code has a bug.

### Cloudflare R2 (photo and file storage)
- **What:** cloud storage for photos and quote PDFs. Phones upload directly to it.
- **Why:** free tier, and no fees when files are downloaded (most clouds charge for that).
- **Alternatives:** AWS S3 (download fees), Supabase Storage (smaller free tier).

---

## AI

### Anthropic API (Claude models)
- **What:** the AI that reads photos, ranks candidate products, writes explanations and powers the ticket chat. Called only through our *gateway* (one module), which pins the model version and logs every call.
- **Why:** paid, doesn't train on our data, handles images and structured output well.
- **Alternatives:** OpenAI, Google Gemini (also viable; the gateway is built so another provider can be added). Free-tier APIs are forbidden for client data.
- **Cons:** costs per call; we'll measure the real cost per request before reporting it.

### Open-source embedding models: open_clip and sentence-transformers
- **What:** small models that turn a photo or a text into an embedding, running on our own worker (no API call).
- **Why:** free, private, and consistent: the same photo always gives the same numbers.
- **Cons:** they need PyTorch, which makes the worker image large (about 1.5 GB).

### Langfuse (AI call tracing)
- **What:** a log of every AI call: input, output, cost, time. Lets us audit why the system said something.
- **Alternatives:** our own logging (more work), LangSmith (similar; Langfuse has a generous free tier and can be self-hosted).

---

## Website

### Next.js, Tailwind, shadcn/ui
- **Next.js:** the framework for the website. We build it as a *static site*: plain files, no server needed, so hosting is free.
- **Tailwind:** a styling system; we load the colours, fonts and spacing from the Figma designs.
- **shadcn/ui:** ready-made, accessible buttons, forms and dialogs we copy into the project and restyle.
- **Alternatives:** Vite with React (fine too; Next.js gives routing and conventions), Material UI (harder to match a custom design).

### Figma
- **What:** where screens are designed before they're built. Claude can read the designs through the Figma connector.

### Playwright
- **What:** a robot that opens the app in real browsers (Chrome-like and Safari-like, phone and desktop sizes) and clicks through flows to test them.

---

## Hosting and delivery

| Service | What it does for us | Cost now |
|---|---|---|
| **GitHub** | Stores the code; runs the automated checks (GitHub Actions); hosts the project board | Free |
| **Google Cloud Run** | Runs the API, worker and MCP containers; scales to zero when idle | Free tier (card on file) |
| **Cloud Scheduler** | Wakes the worker every minute to catch anything missed | Free tier |
| **Cloudflare Pages** | Hosts the website | Free |
| **Resend** | Sends emails (sign-in codes, ticket links) | Free tier, from task 4.9 |
| **Sentry** | Reports app errors | Free tier, from task 7.3 |

**Why Cloud Run and not AWS (yet):** it has a real free tier and runs our Docker images as-is. Because everything is a container and the queue sits behind one interface, moving to AWS (Lambda or ECS, with SQS) later is a configuration change, not a rewrite. See [decision 0009](03-decisions.md#0009-cloud-run-now-with-a-path-to-aws).
