# 0006: Separate `engineer` and `sales` permissions; one person may hold both

**Context:** a salesperson contacts the customer and sends the quote; an engineer approves the technical recommendation. At a small company it's the same person.

**Decision:** `profiles.roles text[]` replaces the single `role` (values `plant_user`, `engineer`, `sales`, `admin`). `engineer` reviews, approves or edits the diagnosis and recommendations. `sales` messages, quotes and moves the status (`quote_sent`, `closed`) but can't approve a diagnosis. `admin` manages knowledge, users and invites. A quote requires an approved or edited review first.

**Alternatives:** a single staff role (loses the "engineer approved it" guarantee).
