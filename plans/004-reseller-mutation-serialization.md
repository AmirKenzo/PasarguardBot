# Plan 004: Serialize bot-reseller creation, revocation, and lifecycle changes

> **Executor instructions:** Execute this plan in an isolated worktree, task by task, with the listed checks. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` if available. Honor STOP conditions and update `plans/README.md` only with verified results, unless a reviewer owns the index.
>
> **Drift check first:** `git diff --stat 58375f2..HEAD -- app/services/bot_reseller app/routers/webapp/bot_reseller.py app/routers/panel/bot_resellers.py app/jobs/reseller/bot_billing.py tests/unit/services/bot_reseller tests/unit/routers/webapp/test_bot_reseller_routes.py tests/unit/routers/panel/test_bot_reseller_routes.py tests/unit/jobs/test_bot_reseller_billing.py`. Run `git status --short`. Expected predecessor changes are described below; reconcile them, never overwrite them.

**Goal:** A successful grant revocation cannot be followed by successful completion of an overlapping creation under that revoked grant; creation must also respect concurrent suspension/freeze.

**Architecture:** Use one feature-scoped, token-owned Redis lease per reseller Telegram ID for webapp mutations, administrative lifecycle mutations, and billing freeze/unfreeze. Reuse the existing Redis client and lock-key builder, but not the generic fail-open acquire/release protocol. Acquire before loading mutable context and retain ownership through the entire operation; fail closed when coordination is unavailable.

**Tech stack:** Python 3.14, FastAPI, asyncio, the already-installed redis package, SQLAlchemy CRUD, pytest/pytest-asyncio, AsyncMock, uv, Ruff. No new dependency, schema, or UI.

**Spec:** This file is the complete specification. `docs/content/docs/admin/bot-reseller.mdx:128-134` says suspension prevents management and grant revocation settles and removes all service users. Existing Redis availability must become a requirement for this feature's mutations; reads remain available. This is an intentional safety/availability tradeoff, not a global change to the bot.

## Status

- **Priority:** P1
- **Effort:** M, approximately one to two days including adversarial tests
- **Risk:** MED — new coordination can temporarily reject mutations during Redis failures
- **Depends on:** Plans 001 and 003; preserve their guarded settlement and corrected restoration behavior
- **Category:** security
- **Planned at:** commit `58375f2`, 2026-11-02
- **Confidence:** HIGH; an event-controlled source-extraction check revoked an empty grant successfully before an already-started creation inserted a new live user

## Global constraints

- No new dependencies, global lock refactor, database transactions spanning HTTP, schema changes, or frontend/API shape changes.
- Do not modify `app/telegram/state/lock.py`: other features currently rely on its behavior.
- The same key must cover all mutations for one reseller across workers; different resellers must not block one another.
- Never treat a Redis error as successful acquisition, release another owner's lease, or continue writes after detected lease loss.
- Keep panel creation compensation and Plan 001's settlement guard; a lease is not a substitute for either.
- Use fake Redis and fake panel APIs in tests. Do not run requests against production infrastructure.

## Review focus

1. Both interleavings of create/revoke must finish without a surviving unauthorized user.
2. A request queued behind revocation must load fresh grants after acquiring the lease.
3. Slow operations must retain ownership beyond the initial lease lifetime through renewal.
4. Redis failure, lost ownership, cancellation, and exceptions must not produce false success or delete a successor's lock.
5. Billing freeze/unfreeze must coordinate with user/admin changes and recheck state after acquisition.

## Current state and conventions

Webapp operations are protected only against other webapp operations (`app/routers/webapp/bot_reseller.py:62-69`):

```python
if not await acquire_user_lock(user_id, "bot_reseller", ttl=60):
    raise core.Refused(LOCK_BUSY)
try:
    return await call()
finally:
    await release_user_lock(user_id, "bot_reseller")
```

The callbacks load context inside this wrapper, which is the correct placement to preserve. `app/telegram/state/lock.py:19-28` deliberately returns True when Redis is absent or errors. Release at lines 31-38 deletes the key without checking ownership; the stored value is a constant. Those semantics are inappropriate for this new cross-worker authorization boundary, but changing them globally is out of scope.

Admin revoke (`app/routers/panel/bot_resellers.py:335-346`) calls `_act(... lambda: core.revoke_grant(...))` without acquiring that lock. Admin suspend/unsuspend and user deletion follow the same pattern at lines 422-484.

`core.revoke_grant` snapshots users, deletes them, and only then revokes the grant (`app/services/bot_reseller/core.py:264-269`):

```python
users = await crud.list_users(reseller.id, service_id=grant.service_id)
removed = 0
for user in users:
    await _delete_user(reseller, user)
    removed += 1
await crud.decide_grant(grant.id, status=GRANT_REVOKED, actor_id=actor_id)
```

Meanwhile `core.create_user` performs panel I/O before recording ownership (`core.py:380-395`):

```python
created = await panel_api.create_user(panel, payload)
```

It subsequently calls `crud.add_user(...)`. A pending remote create is absent from the revoker's snapshot. The existing cleanup at `core.py:396-401` removes a created remote user if its database insert fails; preserve and extend that compensation for aborted creation.

`app/jobs/reseller/bot_billing.py:126-132` directly calls `core.freeze`/`core.unfreeze` without coordinating with either route. `max_instances=1` in `app/jobs/registry.py:62-73` only serializes scheduled instances, not HTTP handlers or another worker.

Use existing small async helper conventions: the router's `_locked(user_id, call)` and `_act(actor, ..., call, ...)` already take zero-argument awaitable callbacks. Keep that callback contract. Core refusals use `core.Refused`; webapp `_run` and panel `_act` already translate them to existing response shapes.

**Expected predecessor changes:** Plan 001 makes `apply_usage(..., expected_baselines=...)` mandatory and changes `_read_counters` to return `(counters_by_reseller, expected_baselines_by_reseller)`. Plan 003 makes unsuspend restore admin/system markers with positive funds, otherwise convert admin markers to system and remain frozen. Do not replace either behavior while adding locks. This summary is sufficient to understand the dependencies without relying on conversation history.

## Commands you will need

Run from the isolated worktree root after the predecessor plans are verified.

| Purpose | Command | Expected result |
|---|---|---|
| Install if needed | `uv sync --frozen` | Exit 0; lockfile unchanged |
| Lease and creation tests | `uv run --no-sync pytest -q tests/unit/services/bot_reseller/test_locking.py tests/unit/services/bot_reseller/test_creation_races.py` | All pass after implementation |
| Route and job tests | `uv run --no-sync pytest -q tests/unit/routers/webapp/test_bot_reseller_routes.py tests/unit/routers/panel/test_bot_reseller_routes.py tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_lifecycle.py tests/unit/services/bot_reseller/test_settlement.py` | All pass |
| Full backend suite | `uv run --no-sync pytest -q` | Exit 0 |
| Lint | `uv run --no-sync ruff check --no-cache app/services/bot_reseller app/routers/webapp/bot_reseller.py app/routers/panel/bot_resellers.py app/jobs/reseller/bot_billing.py tests/unit/services/bot_reseller tests/unit/routers/webapp/test_bot_reseller_routes.py tests/unit/routers/panel/test_bot_reseller_routes.py tests/unit/jobs/test_bot_reseller_billing.py` | Exit 0 |
| Format check | `uv run --no-sync ruff format --check app/services/bot_reseller app/routers/webapp/bot_reseller.py app/routers/panel/bot_resellers.py app/jobs/reseller/bot_billing.py tests/unit/services/bot_reseller tests/unit/routers/webapp/test_bot_reseller_routes.py tests/unit/routers/panel/test_bot_reseller_routes.py tests/unit/jobs/test_bot_reseller_billing.py` | Exit 0 |
| Frontend gate | None | No frontend edits; existing build is `bun run --cwd frontend build` |

The read-only audit did not run full pytest. `tests/conftest.py` creates/removes a synthetic `.env`; permit that only in the disposable execution worktree, never by copying real secrets/session files. Tests added here are required gates, not previously executed results.

## Scope

**Create:**

- `app/services/bot_reseller/locking.py` — feature-scoped owned lease and renewal only.
- `tests/unit/services/bot_reseller/test_locking.py` — fake-Redis protocol/failure tests.
- `tests/unit/services/bot_reseller/test_creation_races.py` — event-controlled create/revoke and creation-abort tests.
- `tests/unit/routers/webapp/test_bot_reseller_routes.py` — webapp lock/context wiring.
- `tests/unit/routers/panel/test_bot_reseller_routes.py` — admin lock wiring and actor-versus-target identity.

**Modify:** `app/services/bot_reseller/core.py`, `app/routers/webapp/bot_reseller.py`, `app/routers/panel/bot_resellers.py`, `app/jobs/reseller/bot_billing.py`, and the predecessor `tests/unit/jobs/test_bot_reseller_billing.py` / `tests/unit/services/bot_reseller/test_lifecycle.py` as needed for integration.

**Index only:** this plan's status row in `plans/README.md`.

**Out of scope:** generic lock/key/client implementations, other payment/reseller flows, migrations, UI/locales, live load testing, durable panel command queues/outboxes, and repair of historical orphan users.

## Steps

### Task 1: Implement a feature-scoped owned lease

**Interfaces produced in `app/services/bot_reseller/locking.py`:**

- `MutationBusy(Exception)` and `MutationLockUnavailable(Exception)`.
- `ResellerMutationLease` with `async def ensure_owned(self) -> None`.
- `reseller_mutation_lock(telegram_id: int)` as an async context manager yielding that lease.

- [ ] Create fake Redis tests that support conditional SET and ownership-aware renewal/release. Assert: same-reseller contention rejects without running the callback; different reseller IDs proceed; missing Redis/acquire error refuses; stale-owner release cannot delete a replacement token; exceptions and external cancellation release only the owned lease; renewal retains ownership; renewal error/token replacement aborts the protected operation.
- [ ] Run `uv run --no-sync pytest -q tests/unit/services/bot_reseller/test_locking.py`; expect failure before implementation.
- [ ] Use existing `get_redis()` and `build_lock_key(telegram_id, 'bot_reseller')`. Acquire with a fresh random token using `SET NX EX`, not the generic constant-valued helper. Set lease lifetime to 120 seconds and renew every 30 seconds with atomic compare-token-and-expire; release with atomic compare-token-and-delete. Redis `eval` with constant Lua and keys/arguments is suitable; never interpolate user input into a script.
- [ ] Start renewal before entering the protected callback and keep it alive until that callback has fully exited, including cleanup. On detected lost ownership/unavailable renewal, cancel the protected task and surface `MutationLockUnavailable`, never successful completion. Distinguish externally requested cancellation and preserve its cancellation semantics. Cancel/await the renewal task on exit; do not leak tasks.
- [ ] Call `ensure_owned()` immediately before yielding and before accepting successful completion. Renewal/release failure must never delete another token; log no tokens. Release failure after a fully completed mutation may leave a temporary busy lease until its TTL, but must not replay the mutation.
- [ ] Drive renewal/cancellation tests with events and controlled scheduling, not 30-second sleeps. Run the lease test command; all pass. This is feature-specific coordination, not a reusable lock framework.

### Task 2: Use the same lease for webapp and administrative mutations

**Interfaces produced:** `core.run_mutation(telegram_id: int, call)` awaits a zero-argument callback under the new lease and translates busy/unavailable errors into `core.Refused`. Retain `_locked(user_id, call)` as the webapp's thin delegating wrapper; existing route callback signatures need not change.

- [ ] Add route tests using normal imports, FastAPI ASGITransport, and monkeypatched authentication/guards. Follow the ASGI fixture structure in `tests/unit/routers/test_sms.py`, not source-extracted AST tests. Assert all six webapp writes use the reseller's Telegram ID and load mutable context inside the protected callback; state/users/user/usage reads remain unlocked.
- [ ] Add admin route tests for revoke, suspend, unsuspend, and user deletion. The lock identity is the target reseller's Telegram ID, **not** admin actor ID, reseller primary key, grant ID, or user-row ID. Audit actor attribution must remain the authenticated admin.
- [ ] Implement `core.run_mutation`, moving/reusing the existing busy refusal text rather than changing response DTOs. Replace webapp `_locked`'s direct generic acquire/release calls with delegation. Remove unused imports.
- [ ] In the admin router, resolve the target reseller identity, then enter `core.run_mutation` before calling the actual lifecycle operation. Preliminary reads may resolve immutable identity only; reload mutable grant/user/reseller state in the callback. Keep `_act`'s audit on successful mutation and unchanged refusal handling. Do not nest the same non-reentrant lease.
- [ ] Add event-barrier creation tests for both legal orderings: (a) creation owns the lease and pauses during remote create; revoke gets busy, then is retried after creation and removes it; (b) revoke owns the lease first; a later create acquires only afterward, reloads context, and is refused for the revoked grant. After each completed sequence, assert no tracked/live user remains under the revoked grant. Calls are rejected while busy, not silently queued or retried by the server.
- [ ] Extend creation compensation in `core.create_user`: after a known remote user was created, any failure before its ownership row is successfully committed must attempt removal of that known remote ID, including cancellation/lease loss. Preserve cancellation, and do not remove a user whose ownership row already committed. Revalidate fresh grant/reseller state after remote creation before inserting the row; refuse and compensate if permission was withdrawn. Add tests for ordinary insert refusal, detected lease loss, cancellation after the remote ID is known, and cleanup failure reporting. Do not blindly retry a timed-out panel create.
- [ ] Run lease/creation and route/job test commands; expect all pass. Run `rg -n 'acquire_user_lock|release_user_lock' app/routers/webapp/bot_reseller.py`; expect no matches.

### Task 3: Coordinate scheduled freeze/unfreeze with the same owners

**Interfaces consumed:** `core.run_mutation(telegram_id, call)`, existing lifecycle functions, and Plan 001's guarded billing interfaces.

- [ ] Add job tests that hold the target reseller lease while creation/admin mutation is paused. Assert billing never toggles those panel users concurrently; busy/unavailable coordination defers lifecycle enforcement and the next successful run performs it.
- [ ] Keep bulk counter reading and `apply_usage` outside the lifecycle lease; Plan 001 guards their observation freshness. When a reseller appears to need freeze/unfreeze, use `core.run_mutation` around only the lifecycle operation. After acquisition, reload the reseller and current wallet and re-evaluate the status/balance gate. Never act solely on the pre-lock `resellers` list or balance snapshot.
- [ ] Count frozen/unfrozen only when the rechecked transition actually succeeds. A busy/unavailable lease logs/records a deferred error, does not pretend the transition succeeded, and does not prevent processing other resellers. Suspended accounts must not automatically unfreeze after top-up.
- [ ] Run route/job tests and the full backend suite. All must pass, including Plan 003's manual-disable preservation and insufficient-balance recovery matrix.
- [ ] Run lint, format check, `git diff --check`, `git diff --name-only`, and `git status --short`. Expect clean checks and Scope-only edits; update the plan index with the results.

## Test plan and done criteria

All must hold:

- [ ] Task 3 verification commands exit 0; new tests cover every Review focus item.
- [ ] Same-reseller operations share one target-identity lease across routes/job; different resellers remain independent.
- [ ] Busy/unavailable coordination refuses web/admin writes and defers job transitions without financial replay.
- [ ] Renewal keeps a slow operation protected; token replacement prevents old-owner success/release of the successor's lease.
- [ ] Both create/revoke orderings pass with no surviving unauthorized user after completed cleanup.
- [ ] Cancellation cleanup is tested once a remote ID is known; committed ownership rows are never mistaken for failed inserts.
- [ ] Plan 001's expected baselines and Plan 003's restoration behavior remain passing.
- [ ] No generic lock behavior, public API shape, schema, or frontend changed.

## Git workflow

Use isolated branch `advisor/004-reseller-mutation-serialization` based on verified Plans 001 and 003. Do not commit, merge, push, or open a PR without explicit authorization. If authorized, match the repo style, e.g. `fix(reseller): serialize revocation with user mutations`, plus current attribution instructions. During rollout, do not leave old fail-open workers running concurrently with the new lock protocol; drain/restart the bot as one coordinated deployment.

## STOP conditions

Stop on unexpected drift beyond the documented predecessors, missing Redis atomic scripting support, a requirement to keep mutations fail-open without coordination, or a new direct mutation caller outside Scope. Stop if cancellation cannot be made safe for a known created user, ORM commit outcome is ambiguous, or cleanup cannot determine whether ownership persisted: do not delete a potentially committed user's account or claim success. A need for durable panel command IDs, schema changes, or globally altered Redis behavior requires a new design decision, not an improvised expansion. Stop after two failed gate attempts or any necessary out-of-scope edit.

## Maintenance notes

The lease protects normal running workers; it cannot make an external panel command and local database commit atomic across process crashes. A timed-out remote create whose ID was never returned, an ambiguous commit, or failed compensation still needs explicit reconciliation and must not be described as solved. Keep ownership tokens, renewal, fresh-context loading, and feature-local fail-closed behavior together in review. Longer bulk operations must retain renewal through cleanup, not rely on a large fixed TTL. New mutation entry points must use the same lease identity before reading authorization state.
