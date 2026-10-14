# 4. How we build and ship

## Branches: where work happens

```
task/0.4-local-supabase ──PR──▶ dev ──release PR──▶ main
                                 │                    │
                          dev environment      production (live)

hotfix/urgent-fix ──PR──▶ main, then main ──PR──▶ dev
```

- **`main` is production.** What's on `main` is what's live.
- **`dev` is the testing ground** where finished tasks come together. It's the default branch.
- **Every task gets its own branch** off `dev`, named after the PLAN task, like `task/0.4-local-supabase`.
- **Changes arrive only through pull requests (PRs).** A PR is a proposal: "here's my change, please check it." Nobody commits directly to `dev` or `main`.

## Environments: where the app runs

| Environment | What it is | Fed by | Exists now? |
|---|---|---|---|
| **test** | Throwaway copy built for each PR inside CI, with a temporary database | Every PR | Yes (as CI) |
| **dev** | Hosted app and database for development and demos | `dev` branch | From task 0.5 |
| **uat** | For people (our team, the client) to try things out | Promoted builds | Before the pilot |
| **prodtest** | A rehearsal copy of production | Release tags | Before the pilot |
| **prod** | The live system | `main` branch | Task 7.3 |

## CI/CD: the automatic checks and deliveries

- **CI (continuous integration):** every time a PR is opened or updated, GitHub runs all the checks. If any fail, it doesn't merge.
- **CD (continuous delivery):** once merged, the build is delivered to the next environment automatically, or with a button press for production.

### What CI checks on every PR

| Check | Catches |
|---|---|
| Lint and unit tests | Style problems, type mistakes, broken logic |
| Embedding libraries import | Mismatched AI library versions (a real bug we hit) |
| Web build | A website that wouldn't build |
| Secret scan (gitleaks) | Passwords or keys accidentally committed |
| Images (api, worker, mcp) | Services that wouldn't package or start |
| Integration tests | Code that breaks against a real database (a throwaway local Supabase, reset before every run) |
| Eval gate *(from 2.2)* | Changes that make recommendations less accurate |
| End-to-end *(from 5.10)* | Broken user flows in real browsers |
| Windows and macOS *(weekly, and on dependency changes)* | Code that only works on Linux |

**Build once, promote:** each build is labelled with a fingerprint of the exact files in it. Production reuses the build that already passed on `dev`; if the files differ, deployment refuses. So nothing untested reaches production.

### The free guards (instead of paid GitHub protection)

| Guard | Where | What it does |
|---|---|---|
| Commit hook | Your machine | Refuses commits while you're on `dev` or `main` |
| Push hook | Your machine | Refuses pushes to `dev` or `main` |
| `uv run poe merge <pr>` | Your machine | Merges only allowed PRs whose checks all passed and whose code you've confirmed reading |
| `guard` workflow | GitHub | After every change to `dev` or `main`, verifies it came from a green PR; otherwise opens an issue |
| Dependabot | GitHub | Opens PRs to update libraries, so security fixes arrive |
| Weekly audit | GitHub | Reports known vulnerabilities in our libraries |

## A change from start to finish

1. Pick the next story on the [board](06-the-board.md) and move it to *In progress*.
2. Start a session with `/pickup`; Claude syncs and checks the machine.
3. Branch: `git switch -c task/<id>-<slug>` from `dev`.
4. Build it: tests first for core logic, then code until `uv run poe check` is green.
5. `/handoff` (or open the PR): checks, notes in `docs/PROGRESS.md`, push, PR into `dev`.
6. CI runs. Meanwhile, read the PR: `/walkthrough <pr>` goes through every file with you.
7. Tick **I read every changed file** in the PR description.
8. `uv run poe merge <pr>`: it refuses unless the checks are green and the box is ticked. The story closes automatically.
9. When `dev` has a set of tested changes worth shipping: a release PR from `dev` into `main`.

## Daily commands

| Command | What it does |
|---|---|
| `uv run poe doctor` | Is this machine set up correctly? |
| `uv run poe check` | Run all quality checks and tests, as CI will |
| `uv run poe dev` | Run the API, worker and website locally |
| `uv run poe merge <pr>` | Merge a PR safely |
| `uv run poe --help` | List every command |
