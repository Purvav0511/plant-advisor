# Developing on the Mac and the PC

This page covers setting up both machines, moving work between them with Claude, and testing on both. The rules Claude Code follows are in `CLAUDE.md`. The decision behind this setup is in `docs/decisions/0001-cross-platform-dev.md`.

---

## 1. How the pieces fit together

**Git is the only thing that syncs code.** Each machine has its own clone, its own Python and Node environments, and its own `.env`. Everything else is either rebuilt from the repo or lives in a shared cloud service.

| What | Where it lives | How the other machine gets it |
|---|---|---|
| Code, docs, `docs/PROGRESS.md`, playbooks, migrations | GitHub (private repo) | `git pull` (`/pickup` does it) |
| Python packages (`.venv`) and Node packages (`node_modules`) | Each machine | Rebuilt from `uv.lock` and `pnpm-lock.yaml` with `uv sync` and `pnpm install` |
| Secrets (`.env`) | Each machine | Copied from your password manager. Never git |
| Client data sheets (`data/raw/`), private eval photos, ingestion reports | A private prefix in the R2 dev bucket | `uv run poe raw-pull`. Never git |
| Dev database, uploaded photos | Hosted Supabase dev project and R2 dev bucket | Already shared: both machines and your phone see the same data |
| This design conversation and the design doc | Your claude.ai account | Open the Claude desktop app on the PC; they're there |
| Claude Code session history | The machine where the session ran | **It doesn't move.** Use `/handoff` and `/pickup`, or a cloud session (§6) |

> **Never** put the repo in a synced folder (iCloud Desktop & Documents, OneDrive, Dropbox). They corrupt `.venv`, `node_modules` and git's index.
>
> - **Mac:** use `~/code`.
> - **PC:** use `~/code` *inside* Ubuntu.

---

## 2. The machines

| | Mac | PC | Claude Code cloud sessions | CI (GitHub Actions) |
|---|---|---|---|---|
| Where the code runs | macOS (arm64 on an M-series chip) | Ubuntu inside **WSL2** (x86_64) | Ubuntu 24.04 (x86_64) | Ubuntu on every push; Windows and macOS weekly |
| Browsers for manual testing | Safari, Chrome | Edge, Chrome (they open `localhost` served from WSL) | – | Playwright: Chromium and WebKit |

**Why WSL2 on the PC:**
- Production (Cloud Run), CI and cloud sessions all run Linux x86_64. With WSL2 the PC matches them, so the Mac is the only "different" machine.
- Docker Desktop uses WSL2 anyway.
- Claude Code's sandboxing works on WSL2 but not on native Windows.
- The desktop app's Code tab can run sessions directly in a WSL distribution.
- Hot reload is fast when the repo sits in the Linux filesystem.

---

## 3. One-time accounts (not per machine)

- A **private** GitHub repository. Install the Claude GitHub App on it if you want cloud sessions (§6).
- A Claude plan that includes Claude Code (Pro or Max), signed in on both machines with the **same account**.
- **Supabase:** one hosted **dev** project, shared by both machines. Add a prod project at PLAN 7.3 (the free tier allows two active projects).
- **Cloudflare R2:** one **dev** bucket, private. Create an **Account API token** with *Object Read & Write* on that bucket only. Paste `config/r2-cors.json` into the bucket's *Settings → CORS Policy* (`uv run poe r2-cors --rules` prints it), then check with `uv run poe r2-cors`.
- **A paid model API key.** Never use a free tier with client data.
- **A password manager** (Bitwarden's free plan is fine). It holds the master copy of `.env` as a secure note.

---

## 4. Machine setup

### 4a. Mac

1. **Command-line tools and Homebrew:**
   ```bash
   xcode-select --install
   # Homebrew: follow the one-line installer at brew.sh
   ```
2. **Tools:**
   ```bash
   brew install git gh uv fnm cloudflared
   brew install --cask libreoffice        # only needed for .doc conversion (PLAN 1.7)
   ```
3. **Docker Desktop:** download it from docker.com and start it once.
4. **Node 22 and pnpm:**
   ```bash
   echo 'eval "$(fnm env --use-on-cd --shell zsh)"' >> ~/.zshrc && exec zsh
   fnm install 22 && corepack enable   # pnpm then follows the version pinned in package.json
   ```
5. **Claude Code**, using the native installer (it auto-updates):
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude doctor
   ```
   Also install the **Claude desktop app** from claude.com/download.
6. **Git and GitHub:**
   ```bash
   gh auth login && gh auth setup-git
   git config --global user.name "Your Name"
   git config --global user.email "<your GitHub email or no-reply address>"
   mkdir -p ~/code
   ```

Note: macOS uses ports 5000 and 7000 for AirPlay Receiver. The project avoids them (§8).

### 4b. PC (Windows with WSL2)

1. **WSL2 with Ubuntu.** In PowerShell, run as administrator, then reboot and create your Linux user:
   ```powershell
   wsl --install -d Ubuntu-24.04
   ```
2. **Optional:** cap WSL's memory if the PC has 16 GB or less. Create `%UserProfile%\.wslconfig`:
   ```ini
   [wsl2]
   memory=8GB
   ```
3. **Docker Desktop for Windows:**
   - Install it with `winget install Docker.DockerDesktop`.
   - In Settings → Resources → **WSL integration**, enable **Ubuntu-24.04**.
4. **Tools: run everything below inside the Ubuntu terminal**, not PowerShell.
   ```bash
   sudo apt update && sudo apt install -y build-essential git curl unzip gh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   curl -fsSL https://fnm.vercel.app/install | bash && exec bash
   fnm install 22 && corepack enable
   # nvm works too (the repo has .nvmrc): nvm install 22 && corepack enable
   sudo apt install -y --no-install-recommends libreoffice-writer   # only for .doc conversion (PLAN 1.7)
   ```
   - **cloudflared:** install the Linux package from Cloudflare's downloads page or their apt repository.
5. **Claude Code inside WSL:**
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   claude doctor
   ```
   - Install the **Claude desktop app for Windows** too.
   - In its **Code** tab, choose the **Ubuntu (WSL)** environment and the folder `~/code/plant-advisor`. Sessions then run inside Linux, exactly like the terminal.
6. **Git and GitHub, inside Ubuntu:** run the same commands as the Mac's step 6. WSL has its own git config and credentials, separate from Windows.
7. **Editor:** VS Code with the **WSL** extension. Run `code .` from the repo inside Ubuntu.

**Native Windows fallback** (only if WSL isn't possible):
- **Install:**
  - Git for Windows (gives Claude Code its Bash tool)
  - Claude Code: `irm https://claude.ai/install.ps1 | iex`
  - Everything else: `winget install astral-sh.uv Schniz.fnm Docker.DockerDesktop GitHub.cli Cloudflare.cloudflared`
- **What works the same:** the poe tasks are cross-platform, so they run unchanged.
- **Differences:**
  - Sandboxing isn't available.
  - If Claude Code can't find Git Bash, set `CLAUDE_CODE_GIT_BASH_PATH` in `.claude/settings.local.json`.
  - MCP servers that start with `npx` need a `cmd /c npx …` wrapper, configured in local scope.

---

## 5. First run (same on both machines)

```bash
cd ~/code
git clone https://github.com/<you>/plant-advisor.git
cd plant-advisor
uv sync                 # installs Python 3.12 if needed, plus every package from uv.lock
pnpm install            # web app, Playwright and the Supabase CLI, from pnpm-lock.yaml
cp .env.example .env    # paste the values from your password manager; set DEV_MACHINE (mac / pc-wsl)
uv run pre-commit install   # installs the pre-commit and pre-push hooks (client data, secrets, protected branches, ruff)
uv run poe raw-pull     # client data sheets and private eval photos from R2 (after PLAN 0.5)
uv run poe doctor       # checks tools, env var names, database, migrations, line endings
uv run poe check        # lint and unit tests
```

Before PLAN task 0.2 exists, only the clone and `.env` steps apply. Then start Claude Code in the repo and run `/pickup`.

**Figma (once per machine):**
- The project's `.claude/settings.json` enables the official Figma plugin. Accept it when Claude Code asks, or run `claude plugin install figma@claude-plugins-official`.
- Run `/mcp`, choose **figma**, and authenticate.
- Manual fallback: `claude mcp add --transport http figma https://mcp.figma.com/mcp`.

**Secrets:**
- There's one `.env` per machine, never committed. The master copy is in your password manager.
- When you add a variable:
  - add its **name** to `.env.example` in the same commit
  - update the password-manager note
  - list it under "On the other machine" in `docs/PROGRESS.md` (`/handoff` does this)
- Only dev keys go on laptops. Prod keys live only in Cloud Run and Cloudflare settings.
- `.claude/settings.json` blocks Claude Code from reading `.env` files.

**The shared dev database:**
- `DATABASE_URL` must be the **Session pooler** string from Supabase. The direct host is IPv6-only, and WSL2 and many home networks can't reach it.
- `uv run poe migrate` applies migrations to the shared dev project. Always pull first.
- **Turn off the Data API** on every hosted project (dev now, prod later): in the Supabase dashboard, open the **Data API** integration overview and switch **Enable Data API** off. Browsers then only sign in and get live updates; every read and write goes through our API (decision 0023). `uv run poe doctor` warns while it's still on.
- Never edit a migration that's already been applied. Add a new one instead. `poe doctor` flags drift between the repo and the database.
- `uv run poe test-int` uses a **local** Supabase in Docker that it resets each run, so tests never touch the shared data.
- Free-tier dev projects pause after 7 days without activity. If yours does, resume it in the Supabase dashboard.

---

## 6. Moving between machines with Claude

| Option | What moves | Use it when |
|---|---|---|
| **A. Handoff through the repo** (default) | The work and the notes. A fresh session reads them | Every switch. It always works |
| **B. Cloud session** | The whole conversation, running on Anthropic's machines | You want one conversation to follow you across devices |
| **C. Remote Control** | Nothing. You steer the Mac's session from the PC or your phone | Watching or nudging a long run on the Mac |

### A. Handoff through the repo

1. **On the machine you're leaving:** type `/handoff`. It:
   - runs the checks
   - updates `docs/PROGRESS.md` (state, next step, what the other machine must do)
   - commits to the task branch and pushes
2. **On the next machine:** open Claude Code in the repo (in the terminal, or the desktop app's Code tab with the Ubuntu environment on the PC) and type `/pickup`. It:
   - pulls
   - refreshes dependencies
   - runs the doctor and the checks
   - tells you where things stand before writing any code

This works because Claude Code reads `CLAUDE.md` automatically, and `PROGRESS.md`, `PLAN.md` and the git log hold everything else. Long sessions get compacted anyway, so written state is more reliable than chat history.

### B. Cloud session

- **Start one** from the desktop app (choose **Cloud**), from claude.ai/code, or from a terminal: `claude --cloud "Continue PLAN task 3.4"`.
- **Move a desktop local session** with **Open in → Cloud**. The conversation carries over as a summary.
- **Where it appears:** the desktop app on both machines, the browser and your phone.
- **Bringing it back to a machine:** run `claude --teleport` in the repo. This needs a clean git state, the session's branch pushed, and the same account. It checks out the branch and loads the conversation. From then on, the local copy and the cloud copy are separate.
- **What the VM has:** Ubuntu with uv, Node 22, pnpm, Docker and Postgres, so code, unit tests and recorded evals work there.
- **Limits:**
  - Plugins such as Figma don't load in cloud sessions.
  - Network access defaults to package registries and GitHub. To reach the dev Supabase or R2, add their domains under **Custom** network access.
  - Any env vars you give a cloud environment should be **dev keys only**.

### C. Remote Control

- **On the Mac:** type `/remote-control` inside a running session, or start one with `claude --remote-control`.
- **From the PC or phone:** open that session from claude.ai/code or the Claude app.
- The code keeps running on the Mac, so the Mac has to stay awake.

### Git habits for two machines

- **One branch per PLAN task,** from `dev`, for example `task/3.4-diagnosis-scoring`. Merge it into `dev` through a pull request with `uv run poe merge <pr>` once CI is green. `main` is production and only takes release PRs from `dev` and hotfixes (decision 0019).
- **Pull before you start and push before you leave.** `/pickup` and `/handoff` do this for you.
- **Don't work on the same branch on both machines at once.** If both machines have unpushed commits, `/pickup` stops instead of merging.

---

## 7. Testing on both machines

| What | Command | Mac | PC (WSL2) | CI |
|---|---|---|---|---|
| Lint and unit tests | `uv run poe check` | ✓ | ✓ | Ubuntu on every push; Windows and macOS weekly |
| Integration tests (local Supabase in Docker) | `uv run poe test-int` | ✓ | ✓ | Ubuntu on every push |
| Eval on recorded model responses | `uv run poe eval` | ✓ | ✓ | Ubuntu on every push |
| End-to-end (Playwright: Chromium, WebKit ≈ Safari, phone viewports) | `uv run poe e2e` | ✓ | ✓ | Ubuntu on every push |
| Real desktop browsers | open `http://localhost:3000` | Safari | Edge | – |
| Real phone (camera, PWA install) | `uv run poe phone` | ✓ | ✓ | – |

- **Results are identical on both machines.** Tests and e2e use recorded model responses (`MODEL_PROVIDER=replay`), so they don't depend on a live model and cost nothing. Only `uv run poe eval --live` calls a real model.
- **Testing on your phone:** `poe phone` opens HTTPS tunnels to the web app and the API with `cloudflared` and prints a URL to open on your phone. The camera and service worker only work over HTTPS, which is why plain `http://<laptop-ip>:3000` isn't enough.
- **Weekly Windows and macOS CI runs** catch code that would only break on another OS. Those runner minutes cost roughly 2× (Windows) and 10× (macOS) a Linux minute, so they don't run on every push. Your Mac covers macOS day to day.
- **Production images** are built in CI for `linux/amd64` (Cloud Run). Never deploy an image built on an M-series Mac: it's arm64.
- **Claude can test the UI on either machine.** The project's `.mcp.json` adds the Playwright MCP server, so Claude Code can open the local app, click through a flow and take screenshots. Run `pnpm exec playwright install chromium` once per machine.

---

## 8. Cross-platform rules for code

Claude Code follows these through CLAUDE.md invariant 15.

- **Paths:** use `pathlib` everywhere, and `tempfile` instead of `/tmp`. Never use string paths with `/` or `\`.
- **Encoding:** open text files with `encoding="utf-8"`, because Windows doesn't default to UTF-8 on Python 3.12. Use `newline=""` for CSV files.
- **Subprocesses:** pass argument lists and never use `shell=True`. Find external tools with `shutil.which` or an env var (such as `SOFFICE_PATH`), never a hardcoded path.
- **Tasks and scripts:** poe tasks use `cmd`, `script` or `sequence`, never `shell`. Helper scripts are Python in `scripts/`, not `.sh` or `.ps1`.
- **Shell syntax:** pass options as flags, not inline env vars (`poe eval --live`, not `LIVE=1 poe eval`, which fails in PowerShell).
- **Line endings:** LF, enforced by `.gitattributes`.
- **File names:** no two files may differ only by case, and imports must match the file's case exactly. macOS and Windows ignore case; Linux CI doesn't.
- **Dependencies:** avoid OS-specific native ones. Use ReportLab rather than WeasyPrint, pypdfium2 rather than poppler, and `psycopg[binary]`.
- **Ports:** web 3000, API 8000, worker 8001, MCP 8002, local Supabase 54321–54324.

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| WSL: installs are slow or hot reload doesn't fire | The repo is under `/mnt/c/...`. Clone it again into `~/code` inside Ubuntu |
| WSL: `docker: command not found` | Docker Desktop → Settings → Resources → WSL integration → enable Ubuntu |
| WSL: out of memory during `test-int` | Raise `memory` in `.wslconfig`, or exclude unused local Supabase services (`supabase start -x studio,imgproxy`) |
| Database connection times out from WSL | `DATABASE_URL` points at the direct host. Use the Session pooler string |
| Every file shows as modified after cloning on the PC | Line endings: confirm `.gitattributes` is committed, then run `git add --renormalize .` and commit |
| `poe doctor` reports missing env vars | Copy the new names from `.env.example` and the values from your password manager |
| `poe doctor` reports migration drift | Pull first. If the other machine applied a migration you don't have, your branch is behind |
| Figma tools missing in Claude Code | Accept the Figma plugin, or install it, then `/mcp` → figma → Authenticate (once per machine) |
| Playwright can't find a browser | `pnpm exec playwright install --with-deps chromium webkit` (on WSL, `--with-deps` installs system libraries) |
| `claude --teleport` refuses to run | Commit or stash local changes, make sure the session's branch is pushed, and check you're signed in to the same account |
| Mac: port 5000 or 7000 is busy | That's AirPlay Receiver. The project doesn't use those ports |
| `corepack` fails with "Cannot find matching keyid" | The Node 22 build is too old for npm's current signing keys. Install the latest Node 22 (`fnm install 22` or `nvm install 22`) |
