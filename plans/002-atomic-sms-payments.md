# Plan 002: Finalize SMS wallet payments atomically

> **Executor instructions:** Follow the checkboxes and STOP conditions. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` if available. Execute in an isolated worktree with synthetic configuration, not the operator's checkout. Update the status row in `plans/README.md` unless a reviewer maintains it.
>
> **Drift check first:** `git diff --stat 58375f2..HEAD -- app/db/crud/auto_card.py app/routers/sms.py tests/integration/db/crud/test_auto_card_payment.py tests/unit/routers/test_sms.py`. Compare changed files with Current state and run `git status --short` before editing.

**Goal:** An SMS confirmation either completes the invoice, wallet credit, and approved transaction together, or leaves all three unchanged and retryable.

**Architecture:** Replace the separate claim and credit with one `CRUDAutoCard.approve_and_credit` transaction. The database is the financial idempotency boundary; Redis delivery markers remain an optimization. Notifications, statistics, and invoice cleanup happen only after commit and cannot cause financial replay.

**Tech stack:** Python 3.14, FastAPI, SQLAlchemy async sessions, MySQL deployment, pytest/SQLite integration tests, Telethon and Redis at mocked boundaries, uv and Ruff.

**Spec:** This file is the complete specification. Preserve `app/routers/sms.py` authentication, bank-rule precedence, supported JSON/form payloads, rial invoice matching, toman credits, configurable bonus, and existing HTTP response shapes. This is not a new payment framework.

## Status

- **Priority:** P1
- **Effort:** M, approximately one day including tests
- **Risk:** MED — payment transaction and retry semantics change
- **Depends on:** none; independent of the reseller plans
- **Category:** bug
- **Planned at:** commit `58375f2`, 2026-11-02
- **Confidence:** HIGH; an isolated SQLite check proved a failed pre-credit attempt leaves an unclaimable invoice

## Global constraints

- No dependencies, schema changes, bonus formula changes, webhook authentication changes, or edits to other payment processors.
- Do not catch a failed financial transaction and report it as a successful payment.
- Never reset an already-committed invoice to pending because a Telegram notification failed.
- Do not connect to a bank, SMS provider, live Telegram account, production database, or live Redis in tests.
- No automatic repair of previously stuck invoices: an old `status=True` row does not prove whether its wallet was credited.

## Review focus

1. Failure before commit leaves the invoice pending and wallet/ledger unchanged.
2. Duplicate confirmations credit exactly once even without Redis delivery markers.
3. Notification/log failures after commit must not cause another credit or a financial 500 response.
4. Bonuses credit the right total while the transaction stores the original toman amount.
5. Missing wallets and database errors remain retryable failures, not silent successes.

## Current state and conventions

`app/db/crud/auto_card.py:131-147` commits its claim when this context exits:

```python
async with GetDB() as db, db.begin():
    stmt = select(AutoCard).where(AutoCard.amount == amount, AutoCard.status.is_(False))
    dialect = db.bind.dialect if db.bind is not None else None
    if dialect and dialect.name != "sqlite":
        stmt = stmt.with_for_update()

    result = await db.execute(stmt)
    auto_card = result.scalar_one_or_none()
    if not auto_card:
        return None

    auto_card.status = True
    await db.flush()
    return auto_card
```

`app/routers/sms.py:94-101` claims first and then calls `_process_payment`. That function loads bonus settings, calls `UserCRUD.Add_Money`, and separately calls `TransactionCRUD.create` (`sms.py:157-171`). It subsequently performs statistics, notification, logging, and deletion (`sms.py:173-193`). These are independent database commits.

`app/db/crud/user.py:611-627` commits a wallet change in its own session. `app/db/crud/transactions.py:23-46` commits the ledger row in another session. Neither can participate in the invoice's already-committed claim.

Reuse the local transaction style from `TransactionCRUD.approve_manual` (`app/db/crud/transactions.py:85-109`):

```python
user.amount = int(user.amount or 0) + total
locked_tx.status = "approved"
locked_tx.completed_at = now
locked_tx.auto_approve_at = None
locked_tx.auto_approve_rule_id = None
new_balance = int(user.amount or 0)
```

That contiguous excerpt is inside the same session transaction that loaded and locked both rows; it is an exemplar, not a body to paste into the SMS helper. Also inspect `app/db/crud/ir_gateway_payments.py:130-161` for the existing `approve_and_credit` naming and payment-plus-balance return pattern. Unlike that helper's broad error-to-None conversion, this SMS helper must propagate database failures so the existing webhook can return 500 and release its delivery marker.

`app/services/billing/payment_bonus.py:4-7` is deliberately free of app/database imports. Reuse it without changing its formula:

```python
async def calculate_payment_bonus(amount: int, bonus_enabled: bool, bonus_percent: int) -> int:
    if not bonus_enabled or bonus_percent <= 0:
        return 0
    return int(amount * bonus_percent / 100)
```

The existing `Transaction` model requires `user_id`, `amount`, `method`, `status`, and `created_at`; an approved row also receives `completed_at` (`app/db/models/transaction.py:14-24`). `AutoCard.amount` is rial, `AutoCard.first_amount` is toman.

Test conventions: `tests/unit/routers/test_sms.py` uses FastAPI/ASGITransport, AsyncMock, and a fake Redis. `tests/integration/db/crud/test_auto_card_code.py` replaces the CRUD's `GetDB` with a temporary SQLite session maker. For SQLite autoincrement of `Transaction.id`, copy the existing `@compiles(BigInteger, "sqlite") -> "INTEGER"` fixture pattern from `tests/integration/services/payments/test_ir_gateways_flow.py:33-35`; do not change production column types.

## Commands you will need

Run from the isolated worktree root.

| Purpose | Command | Expected result |
|---|---|---|
| Install if needed | `uv sync --frozen` | Exit 0; lockfile unchanged |
| Financial tests | `uv run --no-sync pytest -q tests/integration/db/crud/test_auto_card_payment.py tests/integration/db/crud/test_auto_card_code.py` | All pass after implementation |
| Webhook tests | `uv run --no-sync pytest -q tests/unit/routers/test_sms.py tests/unit/routers/panel/test_auto_card_routes.py tests/unit/services/payments/test_auto_card_sms_parser.py` | All pass |
| Full backend suite | `uv run --no-sync pytest -q` | Exit 0; no failures |
| Lint | `uv run --no-sync ruff check --no-cache app/db/crud/auto_card.py app/routers/sms.py tests/integration/db/crud/test_auto_card_payment.py tests/unit/routers/test_sms.py` | Exit 0 |
| Format check | `uv run --no-sync ruff format --check app/db/crud/auto_card.py app/routers/sms.py tests/integration/db/crud/test_auto_card_payment.py tests/unit/routers/test_sms.py` | Exit 0 |
| Frontend gate | None | Frontend is untouched; existing build is `bun run --cwd frontend build` |

The read-only audit ran scoped Ruff successfully, not full pytest. `tests/conftest.py:36-46` creates/removes a synthetic `.env` if absent; allow this only in the isolated execution worktree. Never copy a production `.env` or Telethon session into it.

## Scope

**Modify:** `app/db/crud/auto_card.py`, `app/routers/sms.py`, `tests/unit/routers/test_sms.py`.

**Create:** `tests/integration/db/crud/test_auto_card_payment.py`.

**Index only:** the status row in `plans/README.md`.

**Out of scope:** shared `UserCRUD`, `TransactionCRUD`, other gateways/processors, schema/migration files, SMS parser, secrets/cache, bonus helper, generic idempotency storage, UI, and reconciliation of historical payments.

## Steps

### Task 1: Introduce one transactional finalizer, with real database assertions

**Interfaces produced in `app/db/crud/auto_card.py`:**

```python
@dataclass
class AutoCardPaymentResult:
    invoice: AutoCard
    balance: int
    bonus: int

async def approve_and_credit(
    self, amount: int, *, bonus_enabled: bool, bonus_percent: int,
) -> AutoCardPaymentResult | None:
```

- [ ] Create the integration fixture using the actual `AutoCard`, `User`, and `Transaction` tables, not mocked credits. Patch only `auto_card.GetDB`. Seed a 100000-toman invoice with a synthetic, distinct rial matching amount and a wallet balance of 1000.
- [ ] Add named tests: `test_payment_credits_wallet_and_records_transaction_once` (10% bonus yields balance 111000; one approved auto transaction with amount 100000); `test_bonus_disabled_credits_original_amount`; `test_duplicate_approval_has_no_financial_effect`; `test_transaction_insert_failure_rolls_back_invoice_and_credit`; `test_commit_failure_leaves_payment_retryable`; `test_missing_wallet_does_not_claim_invoice`; `test_already_claimed_invoice_is_not_recredited`.
- [ ] For failure tests, inject a database error during flush/commit before persistence completes, remove the injection, retry, and assert exactly one final credit/ledger row. A test that merely raises before any write is insufficient.
- [ ] Run the financial-tests command. Expect the new tests to fail before the finalizer exists.
- [ ] Implement the helper in one `GetDB` session and `db.begin()` context. Lock the pending invoice by amount on supported databases. Use a conditional update from `status=False` to `True`, checking that one row was claimed, so correctness does not depend on SQLite honoring `FOR UPDATE`. If no pending invoice exists, return None without changing money.
- [ ] In the same transaction, load/lock its wallet, calculate the bonus with `calculate_payment_bonus(invoice.first_amount, ...)`, increment the wallet, and add an approved `Transaction` with original toman amount and both timestamps set. A missing wallet raises `LookupError` and rolls back; SQLAlchemy errors propagate. Never call helpers that open their own sessions from inside this transaction.
- [ ] Return `AutoCardPaymentResult` only after the context has committed. Keep the completed invoice present until post-commit cleanup. Run the financial-tests command; all must pass. Sequential duplicate assertions prove replay behavior; do not present SQLite as proof of MySQL row-lock scheduling.

### Task 2: Route SMS processing through the atomic result

**Interfaces consumed/produced:** `process_payment_sms` keeps its current public signature. Change the private notification helper to `_process_payment(result: AutoCardPaymentResult, settings) -> None`; it must perform no financial mutations.

- [ ] Extend `tests/unit/routers/test_sms.py` with `test_financial_failure_returns_500_and_retry_can_succeed`, `test_post_commit_notification_failure_returns_success_without_recredit`, and `test_duplicate_without_redis_does_not_recredit`. Update `_patch_auto_card` to fake `approve_and_credit`, not `claim_by_amount`, while preserving all parser-precedence assertions.
- [ ] Run the webhook-tests command; expect failures for the old separate-claim behavior or helper contract.
- [ ] Keep the existing parsing/authentication code unchanged. After choosing the rial amount, fetch settings before attempting finalization and call `approve_and_credit` with the effective bonus settings. None means no new pending payment to complete; keep the existing ignored/no-match behavior.
- [ ] Pass the committed result and settings into `_process_payment`. Use `result.balance`, `result.bonus`, and `result.invoice` for notifications/logs. Remove the old `Add_Money` and `TransactionCRUD.create` calls and now-unused imports; retain `TransactionCRUD` where statistics still need it.
- [ ] Make post-commit notification/log/statistics failures best-effort and logged without turning a committed credit into a webhook 500. Keep try/except boundaries outside finalization. Attempt invoice cleanup by its immutable `code` using `CRUDAutoCard.delete`, not the matching amount. Cleanup failure also must not replay the financial operation. Do not invent statistics if their read fails; skip the affected log instead.
- [ ] Remove `claim_by_amount` once `rg -n 'claim_by_amount' app tests` confirms no remaining production caller. Do not leave a compatibility wrapper that can restore the old two-commit flow.
- [ ] Run the financial-tests and webhook-tests commands; expect all pass, including existing secret rejection, payload formats, delivery retry, test-message ignore, and fallback parsing cases.

### Task 3: Verify the completed financial boundary

- [ ] Run the full backend suite, lint, format check, and `git diff --check`; all exit 0.
- [ ] Run `rg -n 'Add_Money|claim_by_amount|transaction_crud\.create' app/routers/sms.py`; expect no matches. Financial writes must be present only in the new finalizer for this flow.
- [ ] Run `git diff --name-only` and `git status --short`; confirm Scope only and update the plan index with actual verification results.

## Done criteria

- [ ] Task 3 gates exit 0; named database and webhook regression tests pass.
- [ ] A failed transaction leaves invoice pending, balance unchanged, and zero new approved transactions; retry credits once.
- [ ] A successful transaction followed by failed notification still credits only once and receives a success response.
- [ ] Bonus-enabled example yields balance 111000 and ledger amount 100000.
- [ ] No production caller can use the removed separate-claim path.
- [ ] No historical invoices or production balances were changed during execution.

## Git workflow

Use `advisor/002-atomic-sms-payments` in an isolated worktree. No commit, merge, push, or PR without separate operator authorization. If authorized, use the repository's conventional style, e.g. `fix(payments): finalize SMS credits atomically`, plus current attribution requirements.

## STOP conditions

Stop on unexpected source drift, new callers of `claim_by_amount`, a schema change requirement, a bonus helper that now performs external I/O, or a test that requires live infrastructure. Stop if existing paid rows cannot be distinguished safely: do not attempt automatic replay or balance repair. A gate failing twice or a necessary out-of-scope edit also requires reporting back.

## Maintenance notes

Redis message IDs cannot replace invoice-level financial idempotency. Future side effects must remain after commit. This plan intentionally does not add a durable notification outbox, guarantee notification delivery, prevent later reuse of a cleaned-up invoice's amount, or repair old ambiguous rows. Before any historical repair, an operator must reconcile invoice, wallet, ledger, and bank records separately.
