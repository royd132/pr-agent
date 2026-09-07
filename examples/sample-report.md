# DiffPrism PR Review — #42

**Repository:** `demo/payments`  
**Risk:** `high`  
**Reviewer:** `agentic-prism`

One verified authorization regression requires action before merge.

## Merge verdict

**BLOCK** — A verified cross-tenant authorization path is reachable.

## Change map

**Intent:** Add a cache fallback for account lookup.

**Affected surfaces**
- tenant authorization
- account cache

**Affected files**
- payments/accounts.py
- tests/test_accounts.py

**Test gaps**
- uncached cross-tenant lookup

## Verified findings

### 1. 🔴 Fallback bypasses account scope check

`payments/accounts.py:87` · **HIGH** · `AUTH-SCOPE-BYPASS` · confidence `0.94`

**Trigger:** An authenticated user requests an uncached account_id owned by another tenant.

**Evidence**

```text
if cached is None: return load_account(account_id)
```

**Impact:** Cross-tenant account metadata can be disclosed.

**Examiner:** `verified` — The changed early return is reachable before the existing membership guard.

**Suggested fix:** Apply the membership predicate before both cached and database return paths.

**Suggested verification:** Request another tenant's uncached account and assert a 403 response.

## Required actions

- Move membership validation before the cache fallback.
- Add the uncached cross-tenant regression test.

## Review trail and execution facts

- Protocol: `prism-review-v1`
- Roles: `prism-lead, scope-mapper, failure-hunter, evidence-examiner`
- Verified findings: `1`; rejected findings: `2`
- Mode: requested `agentic`, effective `agentic`
- Model calls: `5`; tool calls: `7`
- Tokens: input `3200`, output `880`, total `4080`
- Token cost: `$0.00000000`; latency: `1840 ms`

## Explicit unknowns

- production cache miss rate
