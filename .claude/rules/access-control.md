---
paths:
  - "api/app/**/*.py"
  - "api/tests/**/*.py"
---

# Access control

A leak of partner or client data is the costliest possible bug here. Who may see and change what:

| Data | Rule |
|---|---|
| Partners | Shared: every signed-in person sees every partner, "do not discuss" included. Anyone edits do-not-contact, the note and territory; **only admins** reassign the primary rep. |
| Partner numbers | Counts (referrals, bound) are team-wide. **Money is scoped:** a rep's bound premium counts only referrals they're credited on. |
| Referrals | Belong to every rep with a live step credit on them. Reps see only those; admins see all. Someone else's is a **404**. |
| Referral edits | Anyone who can see it may edit before bind; **once bound, admins only**. |
| Pipeline moves | Reps move forward and credit themselves; backward moves and reopening are **admin only**. |
| Progress | Admins see everyone. A rep sees only their own numbers, the company only as shares of goal, and sales vs team only as a percentage (never colleagues' dollars). |
| Goals | **Admins only.** |
| Saved views | Private to their owner, **even from admins**. |

When adding or changing an endpoint:

1. Take `viewer: Viewer`. Start referral queries from `visible_referrals(viewer)`; don't rebuild scoping inline.
2. Refuse with `FieldError` (422) for "not allowed to change this field", `HTTPException(404)` for records
   the viewer can't see.
3. Add or update its row in `api/tests/test_access_matrix.py` (the guard fails otherwise).
4. If the response's *contents* differ by viewer, add a content test (`test_access.py` style). A leak still
   answers 200, and only a content test catches it.
5. Break the rule once and watch the test fail, then restore it.
6. Record a new rule in `DECISIONS.md`.
