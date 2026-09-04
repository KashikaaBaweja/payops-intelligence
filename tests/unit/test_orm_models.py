from datetime import datetime

from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.data.models import Merchant, Order, Payment, PaymentMethod
from sqlalchemy.exc import IntegrityError


def _session() -> tuple:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = session_factory(engine)
    return engine, factory()


def test_payment_requires_order_and_merchant() -> None:
    _engine, session = _session()
    session.add(
        PaymentMethod(
            method_id="card",
            name="Card",
            category="card",
            is_active=1,
            created_at=datetime(2024, 1, 1),
            extra={},
        )
    )
    session.add(
        Merchant(
            merchant_id="M101",
            name="Northwind Checkout",
            country="IN",
            status="active",
            mcc="5999",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
            extra={},
        )
    )
    session.add(
        Order(
            order_id="O1",
            merchant_id="M101",
            amount_cents=1000,
            currency="INR",
            status="created",
            created_at=datetime(2024, 6, 1),
            updated_at=datetime(2024, 6, 1),
            extra={},
        )
    )
    session.add(
        Payment(
            payment_id="P1",
            order_id="O1",
            merchant_id="M101",
            method_id="card",
            amount_cents=1000,
            currency="INR",
            status="succeeded",
            error_code=None,
            created_at=datetime(2024, 6, 1, 10, 0),
            extra={},
        )
    )
    session.commit()
    payment = session.get(Payment, "P1")
    assert payment is not None
    assert payment.merchant.name == "Northwind Checkout"
    assert payment.order.order_id == "O1"
    assert payment.method.method_id == "card"
    session.close()


def test_failed_payment_without_error_code_is_rejected() -> None:
    _engine, session = _session()
    session.add(
        PaymentMethod(
            method_id="upi",
            name="UPI",
            category="realtime",
            is_active=1,
            created_at=datetime(2024, 1, 1),
            extra={},
        )
    )
    session.add(
        Merchant(
            merchant_id="M102",
            name="Harbor Retail",
            country="IN",
            status="active",
            mcc="5311",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
            extra={},
        )
    )
    session.add(
        Order(
            order_id="O2",
            merchant_id="M102",
            amount_cents=500,
            currency="INR",
            status="created",
            created_at=datetime(2024, 6, 1),
            updated_at=datetime(2024, 6, 1),
            extra={},
        )
    )
    session.add(
        Payment(
            payment_id="P2",
            order_id="O2",
            merchant_id="M102",
            method_id="upi",
            amount_cents=500,
            currency="INR",
            status="failed",
            error_code=None,
            created_at=datetime(2024, 6, 1, 10, 0),
            extra={},
        )
    )
    try:
        session.commit()
        raise AssertionError("expected IntegrityError")
    except IntegrityError:
        session.rollback()
    session.close()


def test_invalid_merchant_status_is_rejected() -> None:
    _engine, session = _session()
    session.add(
        Merchant(
            merchant_id="MX",
            name="Bad Status Co",
            country="IN",
            status="unknown",
            mcc="5999",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
            extra={},
        )
    )
    try:
        session.commit()
        raise AssertionError("expected IntegrityError")
    except IntegrityError:
        session.rollback()
    session.close()
