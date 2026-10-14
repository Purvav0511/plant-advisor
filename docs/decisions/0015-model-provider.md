# 0015: The first model provider is the Anthropic API

**Decision:** the gateway's first provider is the Anthropic API (paid; API data isn't used for training by default; vision and structured output). Exact model IDs per task are pinned in `config/models.yaml` at PLAN 3.1: a stronger model for evidence and ingestion extraction, a cheaper one for explanation wording and the chat topic classifier. The gateway interface stays provider-neutral.
