"""Cross-gateway payment statistics against an in-memory SQLite database."""

import asyncio
from itertools import pairwise

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.cryptopayments import CryptoPayments
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.db.models.stars_transaction import StarsTransaction
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.db.models.transaction import Transaction
from app.services.billing import payment_stats

T0 = 1_000_000  # period start
T1 = 2_000_000  # period end (exclusive)
INSIDE = 1_500_000
BEFORE = 500_000


def _seed() -> list:
    return [
        # manual: one paid inside (counted by completed_at even though created before), one rejected, one outside
        Transaction(
            id=1, user_id=1, amount=100, method="manual", status="approved", created_at=BEFORE, completed_at=INSIDE
        ),
        Transaction(id=2, user_id=1, amount=999, method="manual", status="rejected", created_at=INSIDE),
        Transaction(
            id=3, user_id=2, amount=999, method="manual", status="approved", created_at=BEFORE, completed_at=BEFORE
        ),
        Transaction(id=4, user_id=2, amount=200, method="manual", status="approved", created_at=INSIDE),
        # crypto: toman lives in amount_irt; paytime 0 falls back to createtime
        CryptoPayments(
            order_id=1, user_id=2, arz="TON", amount="1.5", amount_irt=300, status="Paid", paytime=0, createtime=INSIDE
        ),
        CryptoPayments(
            order_id=2, user_id=2, arz="TON", amount="9", amount_irt=999, status="Pending", paytime=0, createtime=INSIDE
        ),
        StarsTransaction(
            id=1, invoice_no="A", user_id=1, amount=400, stars=10, status="approved", created_at=INSIDE, paid_at=INSIDE
        ),
        StarsTransaction(id=2, invoice_no="B", user_id=1, amount=999, stars=10, status="pending", created_at=INSIDE),
        # tonpays: credited_amount includes bonus and must not be summed
        TonPaysInvoice(
            id=1,
            order_id="KZ1",
            user_id=3,
            mode="standard",
            source="bot",
            amount=500,
            credited_amount=550,
            status="completed",
            created_at=INSIDE,
            paid_at=INSIDE,
        ),
        TonPaysInvoice(
            id=2,
            order_id="KZ2",
            user_id=3,
            mode="standard",
            source="bot",
            amount=999,
            status="pending",
            created_at=INSIDE,
        ),
        # Iranian gateways (one table): only live completed payments count; test-mode payments never do
        _gw(1, "zarinpal", user_id=4, amount=50, status="completed", credited_amount=55),
        _gw(2, "zarinpal", user_id=4, amount=777, status="completed", sandbox=True),
        _gw(3, "zarinpal", user_id=4, amount=888, status="pending"),
        _gw(4, "zibal", user_id=5, amount=30, status="completed"),
        _gw(5, "zibal", user_id=5, amount=777, status="completed", sandbox=True),
    ]


def _gw(row_id: int, gateway: str, *, user_id: int, amount: int, status: str, sandbox: bool = False, **extra):
    paid_at = INSIDE if status == "completed" else None
    return IrGatewayPayment(
        id=row_id,
        gateway=gateway,
        order_id=f"GW{row_id}",
        user_id=user_id,
        sandbox=sandbox,
        amount=amount,
        status=status,
        created_at=INSIDE,
        paid_at=paid_at,
        **extra,
    )


@pytest.fixture
def db(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        Transaction.__table__,
        CryptoPayments.__table__,
        StarsTransaction.__table__,
        TonPaysInvoice.__table__,
        IrGatewayPayment.__table__,
    ]

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Transaction.metadata.create_all, tables=tables)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all(_seed())
            await session.commit()
        return maker

    monkeypatch.setattr(payment_stats, "Session", asyncio.run(setup()))
    return payment_stats


def test_method_totals_in_period(db):
    totals = asyncio.run(db.method_totals(T0, T1))
    assert {m: totals[m]["total_amount"] for m in db.METHODS} == {
        "manual": 300,
        "crypto": 300,
        "stars": 400,
        "tonpays": 500,
        "zarinpal": 50,
        "zibal": 30,
    }
    assert totals["total"] == {"count": 7, "total_amount": 1580}


def test_method_totals_all_time_and_per_user(db):
    assert asyncio.run(db.method_totals())["total"] == {"count": 8, "total_amount": 2579}
    user1 = asyncio.run(db.method_totals(user_id=1))
    assert user1["manual"]["total_amount"] == 100 and user1["stars"]["total_amount"] == 400
    assert user1["total"]["total_amount"] == 500


def test_bucket_revenue(db):
    assert asyncio.run(db.bucket_revenue([BEFORE, T0, T1])) == [999, 1580]


def test_top_users(db):
    by_amount = asyncio.run(db.top_users(T0, T1))
    # users 1 and 2 tie on amount (500, 2 payments each); user 3 has 500 in a single payment
    assert {row[0] for row in by_amount[:2]} == {1, 2}
    assert by_amount[2] == (3, 500, 1)
    by_count = asyncio.run(db.top_users(T0, T1, by="count"))
    assert by_count[0][0] in (1, 2) and by_count[0][2] == 2


def test_tehran_day_boundaries():
    bounds = payment_stats.tehran_day_boundaries(3)
    assert len(bounds) == 4
    assert all(b - a == 86400 for a, b in pairwise(bounds))
