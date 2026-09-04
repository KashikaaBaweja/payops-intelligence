from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import Merchant, Payment, PaymentMethod, WebhookEvent
from payops_core.data.seed import seed
from payops_core.data.synthetic_generator import INCIDENT_UPI_SPIKE, INCIDENT_WEBHOOK_DELAY
from sqlalchemy import func, select


def test_seed_is_deterministic_and_fictional(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'a.db'}"
    first = seed(url, rng_seed=42)
    second = seed(url, rng_seed=42)
    assert first["payments"] == second["payments"]
    assert first["payments"] >= 2000
    assert first["merchants"] == 5
    factory = session_factory(make_engine(url))
    with factory() as session:
        names = [row.name for row in session.scalars(select(Merchant)).all()]
        joined = " ".join(names).lower()
        assert "harbor retail" in joined
        assert "@gmail" not in joined
        assert all(
            merchant.extra.get("synthetic") is True
            for merchant in session.scalars(select(Merchant))
        )


def test_seed_supports_success_failure_and_method_breakdown(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'ops.db'}"
    seed(url, rng_seed=42)
    factory = session_factory(make_engine(url))
    with factory() as session:
        succeeded = session.scalar(
            select(func.count()).select_from(Payment).where(Payment.status == "succeeded")
        )
        failed = session.scalar(
            select(func.count()).select_from(Payment).where(Payment.status == "failed")
        )
        methods = set(session.scalars(select(PaymentMethod.method_id)).all())
        merchants = session.scalars(select(Payment.merchant_id).distinct()).all()
        assert succeeded and failed and succeeded > failed > 0
        assert methods >= {"card", "upi", "netbanking", "wallet"}
        assert len(merchants) == 5


def test_planted_upi_timeout_window(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'upi.db'}"
    seed(url, rng_seed=42)
    factory = session_factory(make_engine(url))
    start = INCIDENT_UPI_SPIKE["start"]
    end = INCIDENT_UPI_SPIKE["end"]
    with factory() as session:
        failed = session.scalar(
            select(func.count())
            .select_from(Payment)
            .where(
                Payment.merchant_id == "M102",
                Payment.method_id == "upi",
                Payment.status == "failed",
                Payment.created_at >= start,
                Payment.created_at < end,
                Payment.error_code == "GATEWAY_TIMEOUT",
            )
        )
        assert failed and failed > 10


def test_planted_webhook_delays(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'wh.db'}"
    seed(url, rng_seed=42)
    factory = session_factory(make_engine(url))
    start = INCIDENT_WEBHOOK_DELAY["start"]
    end = INCIDENT_WEBHOOK_DELAY["end"]
    with factory() as session:
        delayed = session.scalar(
            select(func.count())
            .select_from(WebhookEvent)
            .join(Payment, Payment.payment_id == WebhookEvent.payment_id)
            .where(
                Payment.merchant_id == "M201",
                WebhookEvent.delivery_status == "delayed",
                WebhookEvent.created_at >= start,
                WebhookEvent.created_at < end,
            )
        )
        assert delayed and delayed > 10
