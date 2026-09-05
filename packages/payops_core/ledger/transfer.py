"""Double-entry transfer that the database commits or rolls back as one unit."""

from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from payops_core.data.models import LedgerAccount, LedgerAuditEvent, LedgerEntry, LedgerTransfer
from payops_core.ledger.accounts import seed_ledger_accounts
from payops_core.ledger.errors import ConsistencyError, InjectedFailure
from payops_core.ledger.isolation import connect_for_transfer, isolation_for
from payops_core.models.schemas import (
    LedgerAccountView,
    TransferAuditEvent,
    TransferOperation,
    TransferResult,
)

logger = getLogger(__name__)

FAIL_POINTS = frozenset({"after_debit", "after_credit", "after_ledger", "before_commit"})


def run_ledger_transfer(
    engine: Engine,
    *,
    from_account_id: str,
    to_account_id: str,
    amount_cents: int,
    fail_at: str | None = None,
) -> TransferResult:
    if fail_at is not None and fail_at not in FAIL_POINTS:
        raise ValueError(f"unknown fail_at: {fail_at}")
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    transfer_id = f"txn-{uuid4().hex[:12]}"
    operations: list[TransferOperation] = []
    before_source = 0
    before_dest = 0
    with Session(engine) as setup:
        seed_ledger_accounts(setup)
        setup.commit()
    connection, isolation, reason = connect_for_transfer(engine)
    try:
        session = Session(bind=connection)
        try:
            operations.append(_op("BEGIN", "started"))
            source, dest, before_source, before_dest = _lock_and_check(
                session, from_account_id, to_account_id, amount_cents
            )
            source.balance_cents -= amount_cents
            source.version += 1
            source.updated_at = _now()
            operations.append(_op("debit", "applied", source.account_id, -amount_cents))
            _maybe_fail(fail_at, "after_debit")

            dest.balance_cents += amount_cents
            dest.version += 1
            dest.updated_at = _now()
            operations.append(_op("credit", "applied", dest.account_id, amount_cents))
            _maybe_fail(fail_at, "after_credit")

            session.add(
                LedgerTransfer(
                    transfer_id=transfer_id,
                    from_account_id=from_account_id,
                    to_account_id=to_account_id,
                    amount_cents=amount_cents,
                    currency=source.currency,
                    status="committed",
                    isolation_level=isolation,
                    fail_at=fail_at,
                    failure_point=None,
                    before_from_cents=before_source,
                    before_to_cents=before_dest,
                    after_from_cents=source.balance_cents,
                    after_to_cents=dest.balance_cents,
                )
            )
            session.add(
                LedgerEntry(
                    entry_id=f"le-{uuid4().hex[:12]}",
                    transfer_id=transfer_id,
                    account_id=source.account_id,
                    direction="debit",
                    amount_cents=amount_cents,
                )
            )
            session.add(
                LedgerEntry(
                    entry_id=f"le-{uuid4().hex[:12]}",
                    transfer_id=transfer_id,
                    account_id=dest.account_id,
                    direction="credit",
                    amount_cents=amount_cents,
                )
            )
            operations.append(_op("update ledger", "applied"))
            _maybe_fail(fail_at, "after_ledger")
            _assert_after(source, dest, before_source, before_dest, amount_cents)
            _maybe_fail(fail_at, "before_commit")
            for event, detail in (
                ("BEGIN", f"isolation={isolation}"),
                ("debit", f"{from_account_id} -{amount_cents}"),
                ("credit", f"{to_account_id} +{amount_cents}"),
                ("ledger", "journal entries written"),
                ("COMMIT", "balances persisted"),
            ):
                session.add(_audit_row(transfer_id, event, detail))
            session.commit()
            operations.append(_op("COMMIT", "committed"))
            return _result(
                transfer_id=transfer_id,
                status="committed",
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount_cents=amount_cents,
                isolation=isolation,
                reason=reason,
                fail_at=fail_at,
                failure_point=None,
                before_source=before_source,
                before_dest=before_dest,
                after_source=source.balance_cents,
                after_dest=dest.balance_cents,
                operations=operations,
                audits=_load_audits(engine, transfer_id),
            )
        except (InjectedFailure, ConsistencyError) as exc:
            session.rollback()
            operations.append(_op("ROLLBACK", "rolled_back"))
            failure_point = _failure_point(exc)
            after_source, after_dest = _balances(engine, from_account_id, to_account_id)
            if before_source == 0 and before_dest == 0:
                before_source, before_dest = after_source, after_dest
            try:
                _persist_rollback(
                    engine,
                    transfer_id=transfer_id,
                    from_account_id=from_account_id,
                    to_account_id=to_account_id,
                    amount_cents=amount_cents,
                    isolation=isolation,
                    fail_at=fail_at,
                    failure_point=failure_point,
                    detail=str(exc),
                    before_from=before_source,
                    before_to=before_dest,
                    after_from=after_source,
                    after_to=after_dest,
                )
            except Exception:
                logger.exception(
                    "ledger rollback audit persist failed transfer_id=%s", transfer_id
                )
            return _result(
                transfer_id=transfer_id,
                status="rolled_back",
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount_cents=amount_cents,
                isolation=isolation,
                reason=reason,
                fail_at=fail_at,
                failure_point=failure_point,
                before_source=before_source,
                before_dest=before_dest,
                after_source=after_source,
                after_dest=after_dest,
                operations=operations,
                audits=_load_audits(engine, transfer_id),
            )
        finally:
            session.close()
    finally:
        connection.close()


def get_transfer(engine: Engine, transfer_id: str) -> TransferResult | None:
    with Session(engine) as session:
        row = session.get(LedgerTransfer, transfer_id)
        if row is None:
            return None
        isolation, reason = isolation_for(engine)
        return _result_from_row(
            row,
            isolation=row.isolation_level or isolation,
            reason=reason,
            audits=_load_audits(engine, transfer_id),
        )


def list_recent_transfers(engine: Engine, limit: int = 8) -> list[TransferResult]:
    isolation, reason = isolation_for(engine)
    with Session(engine) as session:
        rows = list(
            session.query(LedgerTransfer)
            .order_by(LedgerTransfer.created_at.desc())
            .limit(limit)
        )
        ids = [row.transfer_id for row in rows]
        audits_by_id: dict[str, list[TransferAuditEvent]] = {item_id: [] for item_id in ids}
        if ids:
            events = (
                session.query(LedgerAuditEvent)
                .filter(LedgerAuditEvent.transfer_id.in_(ids))
                .order_by(LedgerAuditEvent.created_at.asc())
                .all()
            )
            for event in events:
                audits_by_id.setdefault(event.transfer_id, []).append(
                    TransferAuditEvent(
                        audit_id=event.audit_id,
                        event=event.event,
                        detail=event.detail,
                        created_at=event.created_at,
                    )
                )
        return [
            _result_from_row(
                row,
                isolation=row.isolation_level or isolation,
                reason=reason,
                audits=audits_by_id[row.transfer_id],
            )
            for row in rows
        ]


def account_views(session: Session) -> list[LedgerAccountView]:
    from payops_core.ledger.accounts import list_accounts

    return [
        LedgerAccountView(
            account_id=item.account_id,
            merchant_id=item.merchant_id,
            kind=item.kind,
            currency=item.currency,
            balance_cents=item.balance_cents,
            version=item.version,
            status=item.status,
        )
        for item in list_accounts(session)
    ]


def _lock_and_check(
    session: Session,
    from_account_id: str,
    to_account_id: str,
    amount_cents: int,
) -> tuple[LedgerAccount, LedgerAccount, int, int]:
    if from_account_id == to_account_id:
        raise ConsistencyError("from and to accounts must differ")
    source = session.get(LedgerAccount, from_account_id, with_for_update=True)
    dest = session.get(LedgerAccount, to_account_id, with_for_update=True)
    if source is None or dest is None:
        raise ConsistencyError("ledger account not found")
    if source.status != "active" or dest.status != "active":
        raise ConsistencyError("ledger account is not active")
    if source.currency != dest.currency:
        raise ConsistencyError("currency mismatch")
    if source.balance_cents < amount_cents:
        raise ConsistencyError("insufficient funds")
    return source, dest, source.balance_cents, dest.balance_cents


def _assert_after(
    source: LedgerAccount,
    dest: LedgerAccount,
    before_source: int,
    before_dest: int,
    amount_cents: int,
) -> None:
    if source.balance_cents != before_source - amount_cents:
        raise ConsistencyError("source balance did not match debit")
    if dest.balance_cents != before_dest + amount_cents:
        raise ConsistencyError("dest balance did not match credit")
    if source.balance_cents + dest.balance_cents != before_source + before_dest:
        raise ConsistencyError("conservation invariant failed")
    if source.balance_cents < 0 or dest.balance_cents < 0:
        raise ConsistencyError("negative balance")


def _maybe_fail(fail_at: str | None, point: str) -> None:
    if fail_at == point:
        raise InjectedFailure(point)


def _failure_point(exc: Exception) -> str:
    if isinstance(exc, InjectedFailure):
        return str(exc)
    return "consistency"


def _account_currency(engine: Engine, account_id: str) -> str:
    with Session(engine) as session:
        row = session.get(LedgerAccount, account_id)
        return row.currency if row is not None else "INR"


def _persist_rollback(
    engine: Engine,
    *,
    transfer_id: str,
    from_account_id: str,
    to_account_id: str,
    amount_cents: int,
    isolation: str,
    fail_at: str | None,
    failure_point: str,
    detail: str,
    before_from: int,
    before_to: int,
    after_from: int,
    after_to: int,
) -> None:
    with Session(engine) as session:
        session.add(
            LedgerTransfer(
                transfer_id=transfer_id,
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount_cents=amount_cents,
                currency=_account_currency(engine, from_account_id),
                status="rolled_back",
                isolation_level=isolation,
                fail_at=fail_at,
                failure_point=failure_point,
                before_from_cents=before_from,
                before_to_cents=before_to,
                after_from_cents=after_from,
                after_to_cents=after_to,
            )
        )
        session.add(_audit_row(transfer_id, "BEGIN", f"isolation={isolation}"))
        session.add(_audit_row(transfer_id, "ROLLBACK", f"{failure_point}: {detail}"))
        session.commit()


def _balances(engine: Engine, source_id: str, dest_id: str) -> tuple[int, int]:
    with Session(engine) as session:
        source = session.get(LedgerAccount, source_id)
        dest = session.get(LedgerAccount, dest_id)
        return (
            source.balance_cents if source else 0,
            dest.balance_cents if dest else 0,
        )


def _load_audits(engine: Engine, transfer_id: str) -> list[TransferAuditEvent]:
    with Session(engine) as session:
        rows = (
            session.query(LedgerAuditEvent)
            .filter(LedgerAuditEvent.transfer_id == transfer_id)
            .order_by(LedgerAuditEvent.created_at.asc())
            .all()
        )
        return [
            TransferAuditEvent(
                audit_id=row.audit_id,
                event=row.event,
                detail=row.detail,
                created_at=row.created_at,
            )
            for row in rows
        ]


def _audit_row(transfer_id: str, event: str, detail: str) -> LedgerAuditEvent:
    return LedgerAuditEvent(
        audit_id=f"la-{uuid4().hex[:12]}",
        transfer_id=transfer_id,
        event=event,
        detail=detail,
    )


def _op(
    name: str,
    state: str,
    account_id: str | None = None,
    delta_cents: int | None = None,
) -> TransferOperation:
    return TransferOperation(
        name=name,
        state=state,
        account_id=account_id,
        delta_cents=delta_cents,
    )


def _result_from_row(
    row: LedgerTransfer,
    *,
    isolation: str,
    reason: str,
    audits: list[TransferAuditEvent],
) -> TransferResult:
    return _result(
        transfer_id=row.transfer_id,
        status=row.status,
        from_account_id=row.from_account_id,
        to_account_id=row.to_account_id,
        amount_cents=row.amount_cents,
        isolation=isolation,
        reason=reason,
        fail_at=row.fail_at,
        failure_point=row.failure_point,
        before_source=row.before_from_cents,
        before_dest=row.before_to_cents,
        after_source=row.after_from_cents,
        after_dest=row.after_to_cents,
        operations=[
            _op("BEGIN", "started"),
            _op("debit", "applied" if row.status == "committed" else "rolled_back"),
            _op("credit", "applied" if row.status == "committed" else "rolled_back"),
            _op("update ledger", "applied" if row.status == "committed" else "rolled_back"),
            _op("COMMIT" if row.status == "committed" else "ROLLBACK", row.status),
        ],
        audits=audits,
    )


def _result(
    *,
    transfer_id: str,
    status: str,
    from_account_id: str,
    to_account_id: str,
    amount_cents: int,
    isolation: str,
    reason: str,
    fail_at: str | None,
    failure_point: str | None,
    before_source: int,
    before_dest: int,
    after_source: int,
    after_dest: int,
    operations: list[TransferOperation],
    audits: list[TransferAuditEvent],
) -> TransferResult:
    return TransferResult(
        transfer_id=transfer_id,
        status=status,  # type: ignore[arg-type]
        current_state=status,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount_cents=amount_cents,
        isolation_level=isolation,
        isolation_reason=reason,
        fail_at=fail_at,
        failure_point=failure_point,
        before_balance={"from": before_source, "to": before_dest},
        after_balance={"from": after_source, "to": after_dest},
        operations=operations,
        commit_or_rollback="COMMIT" if status == "committed" else "ROLLBACK",
        audit_events=audits,
        notes=(
            "Committed debit, credit, and ledger journal in one database transaction."
            if status == "committed"
            else "Injected or invariant failure rolled back debit/credit. Balances unchanged."
        ),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
