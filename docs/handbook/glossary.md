# Glossary

| Term | Meaning |
|---|---|
| **API** | The "front desk" program the apps talk to. Ours is built with FastAPI. |
| **Branch** | A separate line of work in git. We use `task/*` for work, `dev` for testing, `main` for production. |
| **CI / CD** | Continuous integration (automatic checks on every change) / continuous delivery (automatic deployment of checked builds). |
| **Container / Docker image** | A sealed box holding a program and everything it needs, so it runs the same everywhere. |
| **Constraint** | A rule the database enforces on its own, like "status must be one of these values". Bad data is refused at the door. |
| **Embedding** | A list of numbers that captures what a photo or text is "like." Similar things have similar numbers, which is how we find similar past cases. |
| **Environment** | A running copy of the whole system: test, dev, uat, prodtest, prod. |
| **Epic / story / cycle** | Planning terms: an epic is a big goal (a PLAN phase), a story is one deliverable piece (a PLAN task), a cycle is a fixed period of work (two weeks). |
| **Eval** | An automated accuracy test: run the system on known cases and score its answers. |
| **Foreign key** | A link from one table to another (a photo points to its request). The database refuses links to rows that don't exist. A *composite* key also checks the company matches. |
| **Gateway** | Our single module through which every AI call passes; it pins versions and logs everything. |
| **Guardrail** | A restriction that keeps an AI on task and safe (topic limits, read-only tools, output checks). |
| **Hallucination** | When an AI states something false or made up with confidence. |
| **Hook (git)** | A small script git runs automatically, for example before a commit or push. |
| **Index** | A lookup structure that makes searches fast, like a book's index. *HNSW* indexes do this for "find similar" searches on embeddings. |
| **Lock file** | A file (`uv.lock`, `pnpm-lock.yaml`) listing the exact version of every library, so every machine installs the same thing. |
| **MCP** | Model Context Protocol: a standard way to give an AI model tools, like "look up a product." |
| **Merge** | Combining a branch's changes into another branch, through a PR. |
| **Migration** | A versioned script that changes the database's structure. Every database replays the same migrations, so they all match. Once applied to a shared database, it's never edited. |
| **MVP** | Minimum viable product: the smallest version worth piloting with real users. |
| **Pipeline (analysis)** | The worker's seven-step analysis of a request. |
| **Pipeline (CI/CD)** | The chain of automatic checks and deployments. |
| **Playbook** | A file holding everything specific to one product family: vocabulary, questions, weights, rules, checks. |
| **PR (pull request)** | A proposed change, reviewed and checked before it merges. |
| **Queue** | A waiting line of jobs; the worker takes requests from it one at a time. |
| **RAG** | Retrieval-augmented generation: search documents, then let an AI answer from them. Our *baseline*, not our method. |
| **Replay** | Using recorded AI responses in tests, so they're free and identical on every run. |
| **Repo (repository)** | The project's folder of code and history, stored on GitHub. |
| **RLS** | Row-level security: database rules that hide rows from users who shouldn't see them. |
| **Scale to zero** | A service that shuts down when idle and starts on demand, so it costs nothing while unused. |
| **Static site** | A website made of plain files, with no server program running; free to host. |
| **Tenant** | A supplier company using the system. Each tenant's data is isolated. |
| **Vector database** | A database that stores embeddings and finds similar ones; we use Postgres with pgvector. |
| **WSL2** | Windows Subsystem for Linux: a real Linux system running inside Windows. |
