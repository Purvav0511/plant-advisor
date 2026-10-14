# 0014: Query-string routes for detail pages

**Context:** the web app is a static export; Next.js can't export dynamic segments like `/console/requests/[id]` whose IDs are unknown at build time.

**Decision:** detail pages use query strings (`/console/request?id=…`, `/plant/request?id=…`) and load data on the client. Email links to tickets use the same form.

**Alternatives:** server rendering (needs a Node host; loses free static hosting).
