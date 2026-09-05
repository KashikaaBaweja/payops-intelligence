from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from payops_core.data.models import LedgerAccount, Merchant

PLATFORM_ACCOUNT = "PLATFORM-clearing"
_STARTING = {
    "M101": 1_000_000,
    "M102": 5_000_000,
    "M201": 2_000_000,
    "M305": 250_000,
    "M410": 1_500_000,
}


def wallet_id(merchant_id: str) -> str:
    return f"{merchant_id}-wallet"


def seed_ledger_accounts(session: Session) -> None:
    created = datetime(2024, 1, 1, 0, 0, 0)
    if session.get(LedgerAccount, PLATFORM_ACCOUNT) is None:
        session.add(
            LedgerAccount(
                account_id=PLATFORM_ACCOUNT,
                merchant_id=None,
                kind="platform_clearing",
                currency="INR",
                balance_cents=0,
                version=1,
                status="active",
                created_at=created,
                updated_at=created,
            )
        )
    merchants = list(session.scalars(select(Merchant)))
    for merchant in merchants:
        account_id = wallet_id(merchant.merchant_id)
        if session.get(LedgerAccount, account_id) is not None:
            continue
        session.add(
            LedgerAccount(
                account_id=account_id,
                merchant_id=merchant.merchant_id,
                kind="merchant_wallet",
                currency="INR",
                balance_cents=_STARTING.get(merchant.merchant_id, 100_000),
                version=1,
                status="active",
                created_at=created,
                updated_at=created,
            )
        )


def list_accounts(session: Session) -> list[LedgerAccount]:
    seed_ledger_accounts(session)
    session.flush()
    return list(
        session.scalars(select(LedgerAccount).order_by(LedgerAccount.account_id.asc()))
    )
