# 0004: Plant onboarding by invite; request history lives on the server

**Context:** plant staff shouldn't retype plant details, several people at a plant may use the app, and phones on a plant floor have weak signal.

**Decision**
- Our company preloads customers, plants and components. Plant staff join through an **invite link or plant code** (`plant_invites` table: code, plant_ids, role, expiry, max uses) plus their own email one-time code. Their profile is bound to those plants.
- One account per person, never a shared plant login (we need to know who submitted what).
- Request history is server-side and visible to every user of that plant (RLS on `plant_ids`). Empty state when none.
- The device only caches for speed (TanStack Query persistence) and keeps **unsent drafts** (photos and answers) in IndexedDB so nothing is lost offline.

**Alternatives:** device-only history (breaks with several users or a new phone); shared plant credentials (no audit trail, hard to revoke).
