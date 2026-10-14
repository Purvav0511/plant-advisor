# 0007: Interactive ticket chat with guardrails; learning only through reviewed changes

**Context:** staff want to chat with an agent on each ticket and reason about the recommendation, and corrections should improve the system. Conversations must stay on business topics.

**Decision**
- The copilot becomes a **chat on the ticket** (`chat_messages` table) preloaded with the ticket context, using only the read-only, tenant-scoped MCP tools. Staff only; plant users message humans.
- **Guardrails, layered:** (1) a cheap topic classifier rejects anything not about this ticket, products, plants or wear; (2) a ticket-scoped system prompt, with photos, documents and messages treated as data, never instructions; (3) read-only tools, no cross-tenant access, no sending to customers; (4) code validates outputs (product IDs exist, citations exist); (5) caps on tool calls and cost per message; (6) everything traced in Langfuse.
- **Learning:** chat never changes knowledge directly. The signals are (a) the engineer's review, which creates a case in case memory, and (b) **proposals** (`knowledge_proposals`: product value fix, rule or weight change) that the chat or an engineer writes and an admin approves only if `poe eval` shows no increase in the confident-but-wrong rate. No model fine-tuning in the MVP.

**Why:** one wrong conversation must not corrupt the knowledge base; every change is reviewed, versioned and reversible.

**Alternatives:** auto-learn from chat (unsafe); fine-tuning (no data volume yet, not auditable).
