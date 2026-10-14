# 0020: Dependency update policy

**Context:** Dependabot's first grouped npm PR (#75) jumped TypeScript 5→7, ESLint 9→10 and `@types/node` 20→26 at once, and included releases a few days old. CI caught it (typescript-eslint doesn't support TS 7), but a policy shouldn't depend on a lucky failure.

**Decision**
- **14-day minimum age** for any dependency version: Dependabot `cooldown: { default-days: 14 }` for uv, npm, GitHub Actions and Docker, and pnpm `minimumReleaseAge: 20160` (minutes), which pnpm also enforces when verifying the lockfile on every install.
- **No automatic major updates:** Dependabot ignores `version-update:semver-major`. A major upgrade becomes a board story, done by hand with a read of the changelog.
- **Match the runtime:** `@types/node` stays on 22 (`.node-version`); the Docker base image stays on Python 3.12 (`.python-version`).
- The lockfile was re-resolved under the rule (patch-level step-backs for 26 packages; no direct dependency changed except `@types/node` 20→22).

**Why:** brand-new releases are where broken and malicious versions appear; majors change behaviour and deserve a deliberate decision.

**Alternatives:** accept everything CI passes (CI can't catch behaviour changes it doesn't test); turn Dependabot off (we'd miss security fixes); shorter cooldowns (less protection; 14 days matches our pinning rule). Security advisories aren't subject to the cooldown, so urgent fixes still arrive.
