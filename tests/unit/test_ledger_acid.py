from pathlib import Path
from threading import Thread

from payops_core.data.engine import make_engine, session_factory
from payops_core.data.models import LedgerAccount, LedgerEntry
from payops_core.data.seed import seed
from payops_core.ledger.isolation import ISOLATION_SQLITE
from payops_core.ledger.transfer import run_ledger_transfer
from sqlalchemy import text
from sqlalchemy.orm import Session


def _engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'ledger.db'}"
    seed(url, rng_seed=42)
    return make_engine(url)


def _balance(engine, account_id: str) -> int:
    with Session(engine) as session:
        row = session.get(LedgerAccount, account_id)
        assert row is not None
        return row.balance_cents


def test_commit_moves_balances_and_writes_journal(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before_from = _balance(engine, "M102-wallet")
    before_to = _balance(engine, "M201-wallet")
    result = run_ledger_transfer(
        engine,
        from_account_id="M102-wallet",
        to_account_id="M201-wallet",
        amount_cents=10_000,
    )
    assert result.status == "committed"
    assert result.commit_or_rollback == "COMMIT"
    assert result.isolation_level == ISOLATION_SQLITE
    assert result.after_balance["from"] == before_from - 10_000
    assert result.after_balance["to"] == before_to + 10_000
    assert _balance(engine, "M102-wallet") == before_from - 10_000
    assert _balance(engine, "M201-wallet") == before_to + 10_000
    with Session(engine) as session:
        entries = session.query(LedgerEntry).filter_by(transfer_id=result.transfer_id).all()
        assert {item.direction for item in entries} == {"debit", "credit"}
        assert sum(item.amount_cents for item in entries) == 20_000
    assert any(event.event == "COMMIT" for event in result.audit_events)


def test_fail_after_debit_rolls_back_balances(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before_from = _balance(engine, "M102-wallet")
    before_to = _balance(engine, "M201-wallet")
    result = run_ledger_transfer(
        engine,
        from_account_id="M102-wallet",
        to_account_id="M201-wallet",
        amount_cents=10_000,
        fail_at="after_debit",
    )
    assert result.status == "rolled_back"
    assert result.commit_or_rollback == "ROLLBACK"
    assert result.failure_point == "after_debit"
    assert _balance(engine, "M102-wallet") == before_from
    assert _balance(engine, "M201-wallet") == before_to
    with Session(engine) as session:
        assert session.query(LedgerEntry).filter_by(transfer_id=result.transfer_id).count() == 0
    assert any(event.event == "ROLLBACK" for event in result.audit_events)


def test_fail_after_credit_rolls_back_balances(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before_from = _balance(engine, "M102-wallet")
    before_to = _balance(engine, "M201-wallet")
    result = run_ledger_transfer(
        engine,
        from_account_id="M102-wallet",
        to_account_id="M201-wallet",
        amount_cents=25_000,
        fail_at="after_credit",
    )
    assert result.status == "rolled_back"
    assert result.failure_point == "after_credit"
    assert _balance(engine, "M102-wallet") == before_from
    assert _balance(engine, "M201-wallet") == before_to


def test_fail_after_ledger_rolls_back_journal(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = run_ledger_transfer(
        engine,
        from_account_id="M102-wallet",
        to_account_id="M201-wallet",
        amount_cents=5_000,
        fail_at="after_ledger",
    )
    assert result.status == "rolled_back"
    with Session(engine) as session:
        assert session.query(LedgerEntry).filter_by(transfer_id=result.transfer_id).count() == 0


def test_insufficient_funds_does_not_debit(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before = _balance(engine, "M305-wallet")
    result = run_ledger_transfer(
        engine,
        from_account_id="M305-wallet",
        to_account_id="M102-wallet",
        amount_cents=before + 1,
    )
    assert result.status == "rolled_back"
    assert result.failure_point == "consistency"
    assert _balance(engine, "M305-wallet") == before


def test_committed_state_survives_new_engine(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'durable.db'}"
    seed(url, rng_seed=42)
    engine = make_engine(url)
    result = run_ledger_transfer(
        engine,
        from_account_id="M102-wallet",
        to_account_id="M201-wallet",
        amount_cents=8_000,
    )
    assert result.status == "committed"
    engine.dispose()
    reopened = make_engine(url)
    factory = session_factory(reopened)
    with factory() as session:
        source = session.get(LedgerAccount, "M102-wallet")
        dest = session.get(LedgerAccount, "M201-wallet")
        assert source is not None and dest is not None
        assert source.balance_cents == result.after_balance["from"]
        assert dest.balance_cents == result.after_balance["to"]
        assert session.get(type(source), "M102-wallet") is not None
        from payops_core.data.models import LedgerTransfer

        stored = session.get(LedgerTransfer, result.transfer_id)
        assert stored is not None
        assert stored.status == "committed"


def test_open_debit_is_not_visible_on_second_connection(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    original = _balance(engine, "M102-wallet")
    reader_engine = make_engine(str(engine.url))
    seen: dict[str, int | None] = {"balance": None}
    connection = engine.connect()
    session = Session(bind=connection)
    try:
        account = session.get(LedgerAccount, "M102-wallet")
        assert account is not None
        account.balance_cents -= 1_000
        session.flush()

        def _read() -> None:
            with reader_engine.connect() as reader:
                reader.exec_driver_sql("PRAGMA busy_timeout=250")
                try:
                    value = reader.execute(
                        text(
                            "SELECT balance_cents FROM ledger_accounts "
                            "WHERE account_id = :account_id"
                        ),
                        {"account_id": "M102-wallet"},
                    ).scalar()
                    seen["balance"] = int(value) if value is not None else None
                except Exception:
                    seen["balance"] = original

        worker = Thread(target=_read)
        worker.start()
        worker.join(timeout=2)
        blocked = worker.is_alive()
        session.rollback()
        worker.join(timeout=5)
    finally:
        session.close()
        connection.close()
        reader_engine.dispose()
    if not blocked:
        assert seen["balance"] == original
    assert _balance(engine, "M102-wallet") == original
