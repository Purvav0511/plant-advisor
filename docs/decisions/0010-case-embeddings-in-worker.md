# 0010: Case embeddings are computed by the worker

**Context:** SPEC §8 had `POST /review` create a case "with embeddings", but only the worker loads the embedding models.

**Decision:** the API writes the `cases` row with null embeddings and enqueues an `embed_case` message. The worker fills `image_embedding` (mean of the request's photo embeddings from Stage 2) and `text_embedding`. Case search ignores rows whose embeddings are null.

**Alternatives:** load the models in the API (heavy image, slow cold starts).
