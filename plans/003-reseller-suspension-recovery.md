# Plan 003: Restore frozen users correctly after administrative suspension

> **Executor instructions:** Read this plan fully; execute its checkboxes in an isolated worktree and honor the STOP conditions. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` if available. Update `plans/README.md` only with actual results, unless a reviewer owns it.
>
> **Drift check first:** `git diff --stat 58375f2..HEAD -- app/services/bot_reseller/core.py tests/unit/services/bot_reseller/test_lifecycle.py tests/unit/jobs/test_bot_reseller_billing.py`. Run `git status --short`. Plan 001 intentionally changes settlement in `core.py` and creates the job test file; retain those changes. Any other excerpt mismatch needs review before implementation.

**Goal:** Removing administrative suspension must restore eligible users when funds are positive, or leave them consistently frozen and automatically recoverable when funds are insufficient.

**Architecture:** Keep the existing reseller statuses and per-user `disabled_by` markers. On unsuspend, read the current wallet: with positive funds, restore both admin- and system-disabled users; otherwise convert admin-disabled users to system-disabled and retain frozen state. Never restore users disabled manually by the reseller.

**Tech stack:** Python 3.14, uv, SQLAlchemy-backed CRUD, pytest/pytest-asyncio, AsyncMock/monkeypatch for panel boundaries, Ruff. No frontend change.

**Spec:** This file is the full specification. `docs/content/docs/admin/bot-reseller.mdx:184-194` promises automatic recovery after top-up and preservation of manually disabled users. `docs/content/docs/user/bot-reseller.mdx:149-155` distinguishes frozen-for-balance from administrative suspension. Those are separate causes even when they overlap.

## Status

- **Priority:** P1
- **Effort:** S, hours including regression tests
- **Risk:** LOW — localized lifecycle correction, but incorrect marker handling could reconnect intentionally disabled users
- **Depends on:** Plan 001 (`plans/001-reject-stale-billing-snapshots.md`) for the job regression harness and safe settlement contract
- **Category:** bug
- **Planned at:** commit `58375f2`, 2026-11-02
- **Confidence:** HIGH; the source-extracted sequence freeze → suspend → unsuspend ended active with its system-disabled user still offline

## Global constraints

- No new status values, columns, migration, dependency, generic state machine, or UI change.
- Retain ownership checks, active-grant requirements, and normal freeze/unfreeze behavior.
- Preserve `disabled_by='reseller'` users through every transition.
- Suspension must continue to prevent automatic top-up recovery until an admin removes it.
- Panel failure must not be reported as a completed unsuspension.
- Do not change billing prices, rounding, wallet charging, or legacy panel-reseller lifecycle.

## Review focus

1. Frozen → suspended → positive top-up → unsuspend restores system-disabled users.
2. Removing suspension with zero or negative balance does not enable users.
3. A later top-up recovers those users through the existing billing job.
4. Manual reseller-disabled users remain disabled throughout.
5. A partial panel failure leaves suspension in place and permits a safe retry.

## Current state and conventions

`app/db/models/bot_reseller.py:17-23` already defines all needed state:

```python
RESELLER_ACTIVE = "active"
RESELLER_FROZEN = "frozen"
RESELLER_SUSPENDED = "suspended"

DISABLED_BY_SYSTEM = "system"
DISABLED_BY_RESELLER = "reseller"
DISABLED_BY_ADMIN = "admin"
```

`app/services/bot_reseller/core.py:478-493` filters by the marker before panel calls:

```python
users = await crud.list_users(reseller.id)
users = [u for u in users if u.disabled_by == (mark if only_marked else None)]
```

It updates markers only after the corresponding panel bulk call succeeds. Preserve that ordering. `freeze` sets `frozen_at` and system markers; `suspend` disables unmarked users as admin and changes reseller status, but leaves existing system markers alone (`core.py:497-523`).

The faulty unsuspend path (`core.py:526-533`) is:

```python
count = await _switch_users(reseller, enabled=True, mark=DISABLED_BY_ADMIN, only_marked=True)
await crud.update_reseller(reseller.id, status=RESELLER_ACTIVE)
return count
```

The job only automatically restores status-frozen accounts (`app/jobs/reseller/bot_billing.py:126-134`):

```python
elif reseller.status == RESELLER_FROZEN and balance > 0:
    await core.unfreeze(reseller)
    stats.unfrozen += 1
```

Thus, changing status to active while leaving system markers strands those users.

Match the existing test style in `tests/unit/services/reseller/test_admin_actions.py:31-60`: monkeypatch small CRUD/panel fakes and assert state writes only after successful panel operations. Its fixture records state explicitly:

```python
state = {"activated": [], "updates": [], "clock_resets": [], "events": [], "sync": (True, None)}


class Accounts:
    async def update_account(self, code, **columns):
        state["updates"].append((code, columns))
```

Use the existing `BotResellerCRUD.balances`, `list_users`, `set_disabled_by`, and `update_reseller`; do not add a parallel data-access layer. An unsuspend API returns the count actually enabled, so the insufficient-balance branch must return zero.

## Commands you will need

Run from the isolated worktree root.

| Purpose | Command | Expected result |
|---|---|---|
| Install if needed | `uv sync --frozen` | Exit 0; lockfile unchanged |
| Lifecycle tests | `uv run --no-sync pytest -q tests/unit/services/bot_reseller/test_lifecycle.py` | All pass after implementation |
| Related regressions | `uv run --no-sync pytest -q tests/unit/jobs/test_bot_reseller_billing.py tests/unit/services/bot_reseller/test_settlement.py tests/integration/db/crud/test_bot_reseller_usage.py tests/unit/test_bot_reseller_imports.py tests/unit/test_bot_reseller_naming.py` | All pass |
| Full backend suite | `uv run --no-sync pytest -q` | Exit 0 |
| Lint | `uv run --no-sync ruff check --no-cache app/services/bot_reseller/core.py tests/unit/services/bot_reseller/test_lifecycle.py tests/unit/jobs/test_bot_reseller_billing.py` | Exit 0 |
| Format check | `uv run --no-sync ruff format --check app/services/bot_reseller/core.py tests/unit/services/bot_reseller/test_lifecycle.py tests/unit/jobs/test_bot_reseller_billing.py` | Exit 0 |
| Frontend gate | None | No frontend edits; existing build is `bun run --cwd frontend build` |

Full pytest was not run in the read-only audit. Its root conftest creates/removes a synthetic `.env` if absent; use a disposable execution worktree and never copy live credentials or session files into it. Scoped production lint passed in the audit; the new test gates are not yet executed.

## Scope

**Modify:** `app/services/bot_reseller/core.py`, `tests/unit/jobs/test_bot_reseller_billing.py` (created by Plan 001).

**Create:** `tests/unit/services/bot_reseller/test_lifecycle.py`.

**Index only:** the status row in `plans/README.md`.

**Do not change:** model constants/schema, API response DTOs, frontend/locales, job scheduling, notification text, the generic lock utility, billing arithmetic, or legacy reseller code.

## Steps

### Task 1: Pin the lifecycle transition matrix

**Interface consumed:** Existing `core.freeze(reseller, balance)`, `core.unfreeze(reseller)`, `core.suspend(reseller_id) -> int`, and `core.unsuspend(reseller_id) -> int` retain their public signatures.

- [ ] Create a fake environment with mutable reseller/user rows, wallet balances, recorded bulk enable/disable calls, and fake CRUD methods. Normal-import `core` and monkeypatch its boundaries, following `test_admin_actions.py`; do not extract production AST into committed tests.
- [ ] Add `test_freeze_suspend_top_up_unsuspend_restores_system_users`: start active, freeze at zero, suspend, top up to 3000, then unsuspend. Assert status active, `frozen_at is None`, eligible users have no disable marker, and the returned enabled count matches them.
- [ ] Add `test_unsuspend_without_credit_converts_admin_marks_to_system`, parameterized for balances 0 and -1. Assert no bulk-enable call, count zero, status frozen, non-null frozen_at, admin/system users marked system, and reseller-disabled users untouched.
- [ ] Add `test_manual_disabled_users_survive_all_transitions`, `test_positive_unsuspend_restores_both_admin_and_system_markers`, `test_suspend_rejects_repeat_and_unknown_reseller`, and `test_unsuspend_panel_failure_keeps_suspension_and_can_retry`. In the failure test, fail one panel after another succeeded; retry must only enable still-marked users, never manually disabled ones.
- [ ] Run the lifecycle-tests command. Expect the first two behavioral regressions to fail against the baseline. Do not accept missing imports or broken fixture setup as the required RED result.

### Task 2: Correct unsuspend without adding state

**Interface produced:** Existing `unsuspend(reseller_id: int) -> int` now obeys the wallet/marker rules below; no new public function is needed.

- [ ] Load the reseller and retain the current not-found/not-suspended refusal. Read its current balance with `crud.balances([reseller.telegram_id])`; do not use an old admin-list response or a browser-supplied balance.
- [ ] If balance is positive, call `_switch_users` for admin-marked users and then for system-marked users, both with `enabled=True, only_marked=True`. Sum successful counts. Only after both complete, persist active status, clear `frozen_at`, and reset `warned_hours` consistently with normal `unfreeze`. If a call raises, do not set active status; successful earlier per-panel marker updates remain available for retry.
- [ ] If balance is zero or negative, do not enable anyone. Read live owned rows, convert only admin markers to system with `set_disabled_by`, leave existing system and reseller markers alone, and persist frozen status with the existing `frozen_at` or `_now()` if absent. Return zero. The normal billing job can then restore users after top-up.
- [ ] Preserve the existing `_switch_users` panel-before-marker ordering. Check persistence results where the modified path relies on `update_reseller` succeeding; return a refusal rather than a success count if the status save fails. Do not alter unrelated CRUD error contracts.
- [ ] Run lifecycle-tests and related-regressions commands; expect all pass. Run `git diff -- app/services/bot_reseller/core.py`; changes must be confined to this transition and necessary imports, retaining Plan 001's settlement guard.

### Task 3: Prove the ordinary billing job completes later recovery

- [ ] Extend `tests/unit/jobs/test_bot_reseller_billing.py` with `test_top_up_after_insufficient_unsuspend_recovers_system_users` and `test_top_up_does_not_unfreeze_admin_suspended_reseller`. Drive the actual job function with fake panel/CRUD boundaries, not a handwritten copy of its conditional.
- [ ] The first test starts with the frozen state produced by the insufficient-balance unsuspend, then provides balance 3000. Assert the job calls normal unfreeze and leaves eligible users active/unmarked. The second keeps status suspended with the same positive balance and asserts no enable call.
- [ ] Retain Plan 001's `_read_counters` interface: a pair `(counters_by_reseller, expected_baselines_by_reseller)`. Empty maps are sufficient for an already-frozen reseller's positive-balance recovery; use no live panel or sleep.
- [ ] Run lifecycle-tests and related-regressions commands; expect all pass. Run full backend tests, lint, format check, and `git diff --check`; all exit 0.
- [ ] Run `git diff --name-only` and `git status --short`; confirm Scope only. Update the plan index with verified results.

## Done criteria

- [ ] All commands in Task 3 exit 0.
- [ ] The positive-funds freeze/suspend/unsuspend sequence ends active with eligible users enabled and markers cleared.
- [ ] Nonpositive-funds unsuspend ends frozen with zero enabled users, followed by successful automatic top-up recovery.
- [ ] Manual reseller-disabled users remain untouched in all tests.
- [ ] Partial panel failure does not publish active status and can be retried safely.
- [ ] Status values, public signatures, and API response shapes are unchanged.

## Git workflow

Use isolated branch `advisor/003-reseller-suspension-recovery`, based on the verified Plan 001 result. Do not commit or integrate without operator authorization. If commits are authorized, use the repo style, e.g. `fix(reseller): preserve balance freeze across suspension`, and current attribution requirements. No push or PR without an explicit request.

## STOP conditions

Stop if Plan 001's job test harness is unavailable, unrelated drift changes lifecycle semantics, a new schema/status seems necessary, or another manual-disable marker exists that these rules would overwrite. Stop if tests reveal a required frontend or notification contract change, an operation needs live infrastructure, a gate fails twice, or scope must expand. Multi-worker lifecycle serialization is a separate planned change; do not implement a generic locking refactor here.

## Maintenance notes

Reseller status controls permission, while each user's marker controls restoration eligibility: do not collapse those concepts. Future suspend/freeze code must retain enough marker information to restore only the right users. Plan 004 serializes lifecycle operations; this plan establishes the transition behavior those locks must preserve. Wallet spending can race with any panel-side enable operation, so the existing periodic billing enforcement still remains necessary.
