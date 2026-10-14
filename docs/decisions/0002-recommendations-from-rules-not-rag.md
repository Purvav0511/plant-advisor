# 0002: Recommendations come from scored diagnosis and catalog rules, not vector search

**Context:** Precision and consistency matter more than speed. The obvious design ("search the vector DB, let the model pick the top 3") is the least repeatable option: similar text comes back, and a model can name a wrong or nonexistent product.

**Decision**
- Diagnosis is computed by code from playbook weights over vision features (fixed vocabulary) and answers. Same inputs, same diagnosis.
- Remedy rules turn the diagnosis into attribute requirements. Requirements are checked **in Python with the same rule evaluator** over the family's approved products loaded from the DB (not compiled to SQL).
- The model only ranks the candidates that pass, must return candidate IDs, and must cite attribute fields.
- Vector search is used for similar past cases (Stage 3) and for the copilot's product lookup, never to choose the recommendation.
- Max-normalized mechanism scores stay as specified, but the total evidence mass is recorded and fed into confidence, so a thin diagnosis shows as low confidence instead of a confident rule match.

**Why:** deterministic, testable, auditable; new products qualify automatically once approved. The naive RAG baseline (SPEC §13) measures whether this actually wins.

**Alternatives:** naive RAG (kept as the baseline only); compiling JSON-logic to SQL (unnecessary below a few thousand products; revisit then).
