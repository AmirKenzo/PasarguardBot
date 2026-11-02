# Plan 001: Reject stale bot-reseller billing snapshots

> **Executor instructions:** Read this file fully, follow the checkboxes, and honor the STOP conditions. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` if available. Work in an isolated git worktree; do not implement on the operator's dirty checkout. Update this plan's row in `plans/README.md` when finished, unless a reviewer owns that index.
>
> **Drift check first:** `git diff --stat 58375f2..HEAD -- app/db/crud/bot_reseller.py app/jobs/reseller/bot_billing.py app/services/bot_reseller/core.py tests/integration/db/crud/test_bot_reseller_usage.py tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py`. Compare any changed files with the excerpts below before proceeding. Also run `git status --short`; never overwrite unrelated changes.

**Goal:** An older panel observation must never debit traffic already settled by a newer operation.

**Architecture:** Carry the baseline observed before panel I/O alongside every counter. Inside the existing billing transaction, compare those expected baselines with the locked rows before changing anything; reject the whole observation batch on a mismatch. Keep legitimate counter-reset accounting unchanged.

**Tech stack:** Python 3.14, uv, SQLAlchemy async sessions, MySQL in deployment, pytest/pytest-asyncio and SQLite integration fixtures, Ruff. The frontend is React/TypeScript with Bun/Vite and is not changed here.

**Spec:** This file is the complete bug-fix specification. Product intent is recorded in `docs/content/docs/admin/bot-reseller.mdx:160-198`: bill only new consumption, carry fractional toman, retain missed readings for later billing, and settle before deleting a user. A real reset must still be distinguishable from an out-of-order reading.

## Status

- **Priority:** P1
- **Effort:** M, approximately one day including tests
- **Risk:** MED — incorrect reset handling can undercharge legitimate consumption
- **Depends on:** none
- **Category:** bug
- **Planned at:** commit `58375f2`, 2026-11-02
- **Confidence:** HIGH; an isolated source-extraction check billed 4 GB for 2 GB using observations 2 GB, 1 GB, 2 GB

## Global constraints

- No dependencies, migrations, frontend/API response changes, or changes to legacy panel-reseller billing.
- Keep integer wallet debits, carried fractional amounts, per-service prices, and hourly aggregation.
- Reject stale observations; do not replace reset handling with `max(0, counter - baseline)`.
- Do not hold database transactions open across panel HTTP requests.
- Tests must use synthetic data and disposable databases, never a configured live panel or production wallet.

## Review focus

1. Older observations after settlement must leave the wallet, carry, baseline, and hourly rows unchanged.
2. One stale user must not permit partial billing of other users in the same observation batch.
3. A genuine lower counter with a matching pre-read baseline must retain reset-from-zero behavior.
4. A deleted user's outstanding snapshot must not resurrect billing after deletion.
5. Reset/delete must stop before destructive panel I/O when settlement is rejected.

## Current state and conventions

- `app/db/crud/bot_reseller.py:50-54` treats every lower counter as a reset:

```python
def usage_delta(counter: int, baseline: int) -> int:
    counter = max(0, int(counter))
    baseline = max(0, int(baseline))
    return counter if counter < baseline else counter - baseline
```

- `BotResellerCRUD.apply_usage` locks the reseller, wallet, and matching owned user rows, but has no observation-time guard (`app/db/crud/bot_reseller.py:381-409`):

```python
counter = int(counters[user.id])
delta = usage_delta(counter, user.baseline_bytes)
user.baseline_bytes = counter
```

- `app/jobs/reseller/bot_billing.py:37-71` reads detached rows with `live_users()`, fetches panel counters, and returns only counters. It collects all panels before applying charges at lines 104-117.
- `app/services/bot_reseller/core.py:335-343` settles a user independently of that background read:

```python
result = await BotResellerCRUD().apply_usage(
    reseller.id, {user.id: panel_api.traffic_counter(panel_user)}, await prices_for(reseller.id)
)
if not result.ok:
    raise Refused("ثبت مصرف این یوزر ممکن نشد، دوباره تلاش کنید.")
```

- Both `reset_user_usage` and `_delete_user` fetch the owned user before panel I/O and call settlement before reset/removal (`core.py:447-460`). Those detached user baselines are the expected values to carry, not a fresh query after the panel response.
- Match `tests/integration/db/crud/test_bot_reseller_usage.py`: its `db` fixture swaps the CRUD's `Session` for a temporary SQLite database; `_seed`, `_apply`, and `_read` keep assertions concise. Existing exemplar:

```python
def test_same_counters_twice_never_bill_twice(db) -> None:
    ids = _seed(db, balance=10_000)
    assert _apply({ids["ali"]: 15052 * MB}).charged == 1400
    assert _apply({ids["ali"]: 15052 * MB}).charged == 0
    assert _read(db, User, id=WALLET)[0].amount == 8_600
```

## Commands you will need

Run from the isolated worktree root. Install only if that worktree lacks dependencies.

| Purpose | Command | Expected result |
|---|---|---|
| Install | `uv sync --frozen` | Exit 0; no lockfile changes |
| Focused tests | `uv run --no-sync pytest -q tests/integration/db/crud/test_bot_reseller_usage.py tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py` | All pass after implementation |
| Full backend tests | `uv run --no-sync pytest -q` | Exit 0; no failures |
| Lint | `uv run --no-sync ruff check --no-cache app/db/crud/bot_reseller.py app/jobs/reseller/bot_billing.py app/services/bot_reseller/core.py tests/integration/db/crud/test_bot_reseller_usage.py tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py` | Exit 0 |
| Format check | `uv run --no-sync ruff format --check app/db/crud/bot_reseller.py app/jobs/reseller/bot_billing.py app/services/bot_reseller/core.py tests/integration/db/crud/test_bot_reseller_usage.py tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py` | Exit 0 |
| Frontend gate | None | No frontend changes; its existing command is `bun run --cwd frontend build` |

`tests/conftest.py:36-46` creates and removes a minimal `.env` when absent. Full pytest was not run during the read-only audit for that reason. In an isolated execution worktree this is expected; do not copy a real `.env` or Telethon session into it. The scoped Ruff check passed during the audit; the test commands above remain execution gates, not claimed results.

## Scope

**Modify:** `app/db/crud/bot_reseller.py`, `app/jobs/reseller/bot_billing.py`, `app/services/bot_reseller/core.py`, `tests/integration/db/crud/test_bot_reseller_usage.py`.

**Create:** `tests/unit/jobs/test_bot_reseller_billing.py`, `tests/unit/services/bot_reseller/test_settlement.py`.

**Index only:** the status row in `plans/README.md`.

**Do not change:** `app/jobs/reseller/billing.py`, `app/db/crud/reseller_billing_snapshots.py`, money rounding, panel counter selection, Redis locks, schemas, UI, or existing migration history.

## Steps

### Task 1: Prove stale observations and guard the billing transaction

**Interface produced:**

```python
async def apply_usage(
    self, reseller_id: int, counters: dict[int, int], prices: dict[int, float], *,
    expected_baselines: dict[int, int], now: int | None = None,
) -> UsageResult:
```

- [ ] Add `test_stale_snapshot_after_newer_settlement_is_rejected`. Use the existing seed: Ali starts at 14540 MB. Save that baseline, settle 15564 MB (1024 MB new, 2800 toman), then submit an older 15052 MB reading with the original expected baseline. Assert `ok is False`, balance stays 7200, baseline stays 15564 MB, and hourly bytes stay 1024 MB. A subsequent 15564 MB reading with expected baseline 15564 MB charges zero.
- [ ] Add `test_stale_mixed_batch_is_atomic`, `test_deleted_user_snapshot_is_rejected`, and `test_matching_baseline_preserves_real_counter_reset`. The mixed batch must leave every user's baseline, carry, wallet, and hourly totals unchanged. Keep `test_users_of_another_reseller_are_ignored` passing: foreign-owner IDs remain ignored, not charged.
- [ ] Extend the test-only `_apply` helper to accept an explicit expected-baseline map; for ordinary existing cases it may read current fixture baselines before calling the CRUD. The production method must have no implicit fallback.
- [ ] Run `uv run --no-sync pytest -q tests/integration/db/crud/test_bot_reseller_usage.py`; expect the new stale tests to fail before implementation. Record the behavioral failure rather than accepting an unrelated fixture/import error as RED.
- [ ] Make `expected_baselines` required. After locking/selecting all owned rows and before mutating any row, reject with `UsageResult(ok=False)` if an owned requested row is deleted or its persisted baseline differs from its expected baseline. Perform the check for the complete batch before changing carry, wallet, or hourly rows. Preserve ownership filtering, reset arithmetic, and existing error behavior.
- [ ] Run the same test command; expect all tests in that file to pass.

### Task 2: Carry observation baselines through both production callers

**Interfaces consumed/produced:** `settle_user(reseller, user, panel_user) -> None` retains its signature. `_read_counters(stats)` returns `(counters_by_reseller, expected_baselines_by_reseller)`, each `dict[int, dict[int, int]]`.

- [ ] Add job tests that pause a fake panel fetch with `asyncio.Event`, advance a baseline through another settlement, then resume the old observation. Assert the original baseline is passed to `apply_usage`, the stale batch is not charged, and a later fresh observation can succeed. Do not use wall-clock sleeps.
- [ ] Add settlement tests asserting that a failed guarded settlement raises `core.Refused` and neither `panel_api.reset_usage` nor `panel_api.remove_user` is awaited. Also cover successful settlement allowing each operation.
- [ ] Run `uv run --no-sync pytest -q tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py`; expect new assertions to fail against the old callers.
- [ ] In `_read_counters`, record `int(user.baseline_bytes or 0)` from the original `live_users()` result for every returned counter. Do not re-read baselines after HTTP. Unpack both maps in `run_bot_reseller_billing` and pass the matching map as `expected_baselines`.
- [ ] In `settle_user`, pass `{user.id: int(user.baseline_bytes or 0)}` as `expected_baselines`. Keep the existing refusal on `not result.ok`; do not silently continue reset/deletion, retry a destructive action automatically, or create a second settlement transaction.
- [ ] Run the focused-tests command from the table; expect all pass. Run `rg -n 'apply_usage\(' app tests` and inspect every bot-reseller call: all supply an expected map captured before their corresponding observation or explicitly constructed in tests.

### Task 3: Run the complete verification gates

- [ ] Run full backend tests, scoped lint, and scoped format check from the table; all must exit 0. Run `git diff --check`; expect exit 0.
- [ ] Run `git diff --name-only` and `git status --short`; changes must be confined to Scope plus the index row. Update the index status to DONE only with the actual test results, otherwise BLOCKED with the failing gate.

## Test plan

Use normal imports, pytest monkeypatch/AsyncMock for panel boundaries, the existing SQLite fixture for wallet/baseline assertions, and explicit event barriers for ordering. The required cases are stale-after-newer settlement, mixed-batch rollback, real reset, duplicate equal readings, deleted row, cross-owner filtering, job baseline capture, and reset/delete refusal after rejected settlement. Keep the existing carry and per-service examples unchanged.

## Done criteria

- [ ] Every command in Task 3 exits 0.
- [ ] New tests above exist and pass; the stale regression leaves the wallet at 7200, not a lower amount.
- [ ] No production `apply_usage` caller can omit its observation-time expected baselines.
- [ ] Rejected observations produce no wallet/baseline/carry/hourly mutations.
- [ ] `plans/README.md` records the result; no out-of-scope edits exist.

## Git workflow

Use branch `advisor/001-reject-stale-billing-snapshots` in a disposable worktree. Do not commit unless the operator separately authorizes it; do not push, merge, or open a PR. If commits are authorized, match the repo's conventional style, e.g. `fix(reseller): reject stale usage observations`, and honor current attribution instructions.

## STOP conditions

Stop and report if the baseline is no longer the persisted observation guard, a caller cannot capture it before HTTP, production writes occur outside the inspected transaction, preserving reset behavior requires schema changes, or an in-scope excerpt has unexpected drift. Stop if a verification fails twice after a reasonable fix, or any fix needs an out-of-scope file. SQLite tests do not prove production row-lock semantics; do not claim they do.

## Maintenance notes

Any future billing/reset/delete caller must carry its pre-read baseline. Row locking alone does not make an old observation fresh. A stale background batch may defer charging until the next run; that is intentional and safer than charging it. Historical overcharges are not automatically detectable from these aggregate rows: do not alter balances retroactively as part of this fix.
