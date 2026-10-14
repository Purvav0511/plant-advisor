# 0008: The "do we need more photos?" check is a pipeline step, not a free agent

**Decision**
- On the phone: guided shots (overview, close-up, coin for scale) and instant blur and brightness checks, so most retakes happen before sending.
- On the server, Stage 2 returns `photo_quality.usable`, `issues[]` and `missing_views[]`. If unusable or a required view is missing, the request goes to `needs_info` with a specific ask ("close-up of the worn edge").

**Why:** same behaviour as an agent, but predictable, cheap and testable.
