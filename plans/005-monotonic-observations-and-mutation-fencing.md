# Monotonic Observation and Mutation Fencing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task. No commits, merge, push, or PR without separate authorization.

**Goal:** Close the four confirmed final-review failures without changing public APIs, statuses, dependencies, or generic locks.

**Architecture:** Add one migration with a per-user `observation_revision` and per-reseller `mutation_generation`, both non-null BigInteger counters initialized to zero. Billing compares `(baseline_bytes, observation_revision)` captured before panel I/O and advances the revision for every accepted user observation. A mutation advances the reseller generation after Redis acquisition and before reading mutable context; creation's ownership insert conditionally locks/checks that generation and active authorization in the same transaction as insertion. No transaction spans panel HTTP.

**Tech Stack:** Existing Python, SQLAlchemy, Alembic, MySQL, SQLite regression fixtures, Redis lease, pytest, Ruff.

**Spec:** The user explicitly approved this full description in chat on 2026-11-02, superseding the no-schema constraint and baseline-only guard in Plans 001/004. The original plans otherwise remain binding. The user also approved fixing both lifecycle failures.

## Global Constraints

- One additive migration, descending from `b8e4d1f6c2a9`; never modify historical migrations.
- No changes to public statuses/API shapes, UI, dependencies, generic locks, payment code, historical balances, or live infrastructure.
- Preserve real counter-reset accounting, whole-batch rejection, ownership filtering, and carried money arithmetic.
- Preserve cancellation and known committed users; fence stale inserts before commitment rather than deleting committed authorized rows.
- Migration must precede deployment; drain old workers before running the new protocol.
- Keep all work uncommitted in the existing isolated worktree.

## Review Focus

1. Baseline ABA and unchanged-counter settlement must both invalidate earlier observations.
2. A successor mutation must either see an already-committed user or reject its old-generation insert.
3. Missing/failed generation updates must refuse mutation before any callback/panel write.
4. A zero-balance retry after partial unsuspend must disable previously restored users, preserving manual disables.
5. Failed suspension persistence must never return successful suspension.

### Task 1: Revision columns and complete observation guard

**Files:** `app/db/models/bot_reseller.py`; new `app/db/migrations/versions/c2d9a6e4f8b1_add_bot_reseller_revisions.py`; `app/db/crud/bot_reseller.py`; `app/jobs/reseller/bot_billing.py`; `app/services/bot_reseller/core.py`; affected existing reseller tests; new `tests/integration/db/test_bot_reseller_revisions_migration.py`.

**Interfaces:** `apply_usage(..., *, expected_observations: dict[int, tuple[int, int]], now=None)` requires pre-read `(baseline, revision)` per observed row. `_read_counters` retains two return maps; the second contains these tuples. No implicit production fallback.

- [x] Retain the already-RED ABA regression; update it to capture the original revision as well as baseline. Add a zero-delta settlement invalidating an older observation regression and migration upgrade/backfill/downgrade assertions using synthetic rows.
- [x] Add the two counters to current models and one additive migration; test defaults/backfill and preservation of existing rows.
- [x] Compare complete observation tuples before any billing mutation, then increment each accepted user's revision even when delta is zero. Carry tuples through job/settlement; update fakes and helper interfaces explicitly.
- [x] Run scoped billing/job/settlement/migration tests. Expected: ABA and zero-delta stale cases reject; genuine resets, duplicate fresh reads, carry, ownership, and destructive-operation refusal still pass.

### Task 2: Database fence for ownership insertion

**Files:** `app/db/crud/bot_reseller.py`, `app/services/bot_reseller/core.py`, existing creation/lease/job/lifecycle test fixtures, new `tests/integration/db/crud/test_bot_reseller_mutations.py`.

**Interfaces:** `advance_mutation_generation(telegram_id: int) -> bool` performs one transactional increment and refuses missing/failed rows. `add_user(*, expected_generation: int, **values)` conditionally checks/locks the reseller generation and active status, verifies an approved service grant, and inserts in that same transaction. `run_mutation` advances generation before invoking its callback. `create_user` captures its original context generation before remote I/O and passes it to insertion.

- [x] Retain the already-RED lease-loss/revocation/blocked-insert test; make fake CRUD model the same pre-insert generation condition as the real database.
- [x] Add actual database tests: matching generation succeeds; old generation cannot insert after an advance; revoked grant/frozen reseller refuse; a committed user remains visible to a subsequent mutation. Add a wrapper test proving failed advancement runs no callback.
- [x] Implement the conditional generation update in the insertion transaction, acquiring the reseller row's write lock before authorization/insertion. Advance the same row before a successor reads users. Keep cancellation shielding and uncertainty-safe cleanup.
- [x] Run mutation integration, creation races, lease, route, job, lifecycle and settlement tests. Expected: both ordering directions preserve authorization and all prior cancellation/ownership checks pass.

### Task 3: Lifecycle failure recovery and final gates

**Files:** `app/services/bot_reseller/core.py`, `tests/unit/services/bot_reseller/test_lifecycle.py`, `plans/README.md`, execution ledgers.

- [x] Use the already-RED partial-unsuspend/zero-balance retry and suspension-save failure tests; include failed-status-save recovery in the partial transition matrix.
- [x] Nonpositive unsuspend first disables unmarked users via the existing panel-before-marker helper, then converts remaining admin markers to system and persists frozen. Manually reseller-disabled users remain untouched.
- [x] Check suspension status persistence and refuse before success notification/count on failure.
- [x] Run `uv run --no-sync pytest -q`; expect all tests pass, including the four final-review regressions.
- [x] Run scoped Ruff lint, Ruff format --check, `git diff --check`, migration graph checks, and scope/status review. Update index rows only with actual verified results and rollout requirements.

**Self-review:** Interfaces are consistent; each counter has one owner and one purpose. Existing integration fixtures cover money, new database tests cover the real fence, and event-controlled tests cover lease-loss ordering. No dependency, frontend, status, payment, or generic-lock expansion is required.
