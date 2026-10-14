# 0005: The plant user sees the AI recommendation, labelled preliminary

**Context:** the owner wants the technician to see the recommendation immediately and then call or text the engineer/salesperson. Accuracy is the top priority, so a wrong product must not look final.

**Decision**
- When an analysis is ready, the plant user sees the diagnosis and top-3 products marked **"Preliminary, pending engineer confirmation"**, then **"Confirmed"** after review (showing the engineer's final version).
- Products are **withheld** (the user sees "an engineer is reviewing this") when the analysis has `low_confidence`, `checks_failed` or `no_candidates`.
- Contact actions on the request: call and text (`tel:` / `sms:` links to the assigned contact's work phone) plus in-app messages. `profiles.phone` and `requests.contact_user_id` (defaults to the tenant's on-call contact, then the claiming engineer) are added.
- The engineer review is still mandatory before any quote (unchanged).

**Why:** speed for the technician without presenting weak or unchecked output as advice.

**Alternatives:** hide until reviewed (slower, owner rejected); show everything (exposes low-confidence output).
