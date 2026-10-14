# 0021: R2 token can't change the bucket; CORS is pasted once and tested; how raw sync behaves

**Context:** PLAN 0.5 needs CORS on the R2 dev bucket (browsers upload photos with presigned URLs) and a way to move client documents between machines without git. The app's R2 token was created with "Object Read & Write" on one bucket only. Reading or changing bucket CORS needs admin rights, so R2 answered "Access Denied".

**Decision**
- **Keep the token least-privileged.** The app and the dev tools can read and write objects, nothing more. A leaked key can't loosen the bucket's rules.
- **CORS lives in `config/r2-cors.json`**, is pasted into the dashboard once per bucket, and is **verified by behaviour**: `uv run poe r2-cors` sends the same preflight a browser sends, against a presigned upload URL, and checks that our origins (`localhost:3000`, `*.trycloudflare.com` for phone tunnels) are allowed and a foreign origin is refused.
- **Raw sync never destroys data without a flag:** files compare by SHA-256 (stored as object metadata on upload); identical files are skipped; a file that differs on the two sides is a conflict and is skipped unless `--overwrite`; push deletes remote-only files only with `--prune`; pull never deletes local files; downloads are checksum-verified before replacing anything; remote keys outside the synced folders (or containing `..`) are refused.

**Why:** least privilege limits the damage of a leaked key, and testing CORS the way a browser does checks what actually matters. Raw documents are never edited, so a difference between two copies needs a human decision, not "last write wins".

**Alternatives:** an admin-scoped token so a script can set CORS (more power than the app ever needs); `wrangler` with a Cloudflare login (a second tool and credential); "last write wins" sync like a shared drive (silently loses a copy); syncing through git LFS (client data would sit in GitHub).
