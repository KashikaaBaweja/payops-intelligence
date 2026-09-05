from fastapi import APIRouter, Depends, HTTPException
from payops_core.ledger.isolation import isolation_for
from payops_core.ledger.transfer import (
    account_views,
    get_transfer,
    list_recent_transfers,
    run_ledger_transfer,
)
from payops_core.models.schemas import LedgerAccountsResponse, TransferRequest, TransferResult
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.deps import get_engine, get_session
from apps.api.query import require_id

router = APIRouter(tags=["transactions"])


@router.get(
    "/transactions/accounts",
    response_model=LedgerAccountsResponse,
    summary="Ledger wallets",
    description="Merchant and platform wallet balances used by the live transfer.",
)
def list_ledger_accounts(
    session: Session = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> LedgerAccountsResponse:
    accounts = account_views(session)
    session.commit()
    isolation, reason = isolation_for(engine)
    return LedgerAccountsResponse(
        isolation_level=isolation,
        isolation_reason=reason,
        accounts=accounts,
    )


@router.get(
    "/transactions/transfers",
    response_model=list[TransferResult],
    summary="Recent ledger transfers",
)
def list_transfers(engine: Engine = Depends(get_engine)) -> list[TransferResult]:
    return list_recent_transfers(engine)


@router.get(
    "/transactions/transfers/{id}",
    response_model=TransferResult,
    summary="Fetch one ledger transfer",
)
def fetch_transfer(id: str, engine: Engine = Depends(get_engine)) -> TransferResult:
    transfer_id = require_id(id, "id")
    result = get_transfer(engine, transfer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="transfer not found")
    return result


@router.post(
    "/transactions/transfers",
    response_model=TransferResult,
    summary="Run a debit/credit/ledger transfer",
    description=(
        "BEGIN → debit → credit → update ledger → COMMIT in one database transaction. "
        "fail_at injects a failure after a named step and forces ROLLBACK."
    ),
)
def create_transfer(
    payload: TransferRequest,
    engine: Engine = Depends(get_engine),
) -> TransferResult:
    try:
        return run_ledger_transfer(
            engine,
            from_account_id=payload.from_account_id,
            to_account_id=payload.to_account_id,
            amount_cents=payload.amount_cents,
            fail_at=payload.fail_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
