"""Seedable synthetic payments universe with planted, discoverable incidents."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

MERCHANTS = [
    ("M101", "Northwind Checkout", "IN", "active"),
    ("M102", "Harbor Retail", "IN", "active"),
    ("M201", "Cedar Digital Goods", "US", "active"),
    ("M305", "Low-volume Labs", "SG", "active"),
    ("M410", "Summit Subscriptions", "GB", "active"),
]

METHODS = [("card", "Card"), ("upi", "UPI"), ("netbanking", "Netbanking"), ("wallet", "Wallet")]

ERROR_CODES = [
    ("GATEWAY_TIMEOUT", "gateway", "Acquirer or method gateway did not respond in time."),
    ("INSUFFICIENT_FUNDS", "issuer", "Issuer declined for insufficient funds."),
    ("DO_NOT_HONOR", "issuer", "Generic issuer decline."),
    ("WEBHOOK_TIMEOUT", "platform", "Webhook consumer did not acknowledge in time."),
    ("AUTHENTICATION_FAILED", "customer", "3DS / UPI PIN authentication failed."),
]

# Headline incident windows used by demos and eval.
INCIDENT_UPI_SPIKE = {
    "incident_id": "INC-UPI-M102",
    "merchant_id": "M102",
    "method_id": "upi",
    "start": datetime(2024, 6, 15, 10, 0, 0),
    "end": datetime(2024, 6, 15, 12, 0, 0),
    "cause": "UPI gateway timeouts at the method processor",
}
INCIDENT_WEBHOOK_DELAY = {
    "incident_id": "INC-WH-M201",
    "merchant_id": "M201",
    "start": datetime(2024, 6, 18, 14, 0, 0),
    "end": datetime(2024, 6, 18, 16, 0, 0),
    "cause": "Webhook delivery delays after successful capture",
}
INCIDENT_SPARSE = {
    "incident_id": "INC-SPARSE-M305",
    "merchant_id": "M305",
    "start": datetime(2024, 5, 1, 0, 0, 0),
    "end": datetime(2024, 5, 2, 0, 0, 0),
    "cause": "Insufficient evidence by design",
}


def _ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def generate(engine: Engine, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    with engine.begin() as conn:
        for table in [
            "webhook_events",
            "disputes",
            "refunds",
            "settlements",
            "payments",
            "orders",
            "error_codes",
            "payment_methods",
            "merchants",
        ]:
            conn.execute(text(f"DELETE FROM {table}"))

        for merchant_id, name, country, status in MERCHANTS:
            conn.execute(
                text(
                    "INSERT INTO merchants VALUES (:id, :name, :country, :status, :created)"
                ),
                {
                    "id": merchant_id,
                    "name": name,
                    "country": country,
                    "status": status,
                    "created": "2024-01-01 00:00:00",
                },
            )
        for method_id, name in METHODS:
            conn.execute(
                text("INSERT INTO payment_methods VALUES (:id, :name)"),
                {"id": method_id, "name": name},
            )
        for code, category, description in ERROR_CODES:
            conn.execute(
                text("INSERT INTO error_codes VALUES (:code, :cat, :desc)"),
                {"code": code, "cat": category, "desc": description},
            )

        base = datetime(2024, 6, 1, 0, 0, 0)
        payment_count = 0
        for day in range(30):
            for merchant_id, *_ in MERCHANTS:
                volume = 8 if merchant_id == "M305" else 40
                for _ in range(volume):
                    created = base + timedelta(days=day, minutes=rng.randint(0, 24 * 60 - 1))
                    method_id = rng.choice(["card", "upi", "netbanking", "wallet"])
                    amount = rng.randint(500, 25000)
                    order_id = f"O{payment_count:06d}"
                    payment_id = f"P{payment_count:06d}"
                    status, error_code, delay_ms = _outcome(
                        rng, merchant_id, method_id, created
                    )
                    conn.execute(
                        text(
                            "INSERT INTO orders VALUES (:oid, :mid, :amt, 'INR', :ts)"
                        ),
                        {
                            "oid": order_id,
                            "mid": merchant_id,
                            "amt": amount,
                            "ts": _ts(created),
                        },
                    )
                    conn.execute(
                        text(
                            """
                            INSERT INTO payments
                            VALUES (:pid, :oid, :mid, :method, :amt, 'INR', :status, :err, :ts)
                            """
                        ),
                        {
                            "pid": payment_id,
                            "oid": order_id,
                            "mid": merchant_id,
                            "method": method_id,
                            "amt": amount,
                            "status": status,
                            "err": error_code,
                            "ts": _ts(created),
                        },
                    )
                    event_status = "delayed" if delay_ms >= 30_000 else "delivered"
                    if rng.random() < 0.03:
                        event_status = "failed"
                    delivered_at = created + timedelta(milliseconds=delay_ms)
                    conn.execute(
                        text(
                            """
                            INSERT INTO webhook_events
                            VALUES (:eid, :pid, :etype, :dstatus, :delay, :ts, :dts)
                            """
                        ),
                        {
                            "eid": f"E{payment_count:06d}",
                            "pid": payment_id,
                            "etype": f"payment.{status}",
                            "dstatus": event_status,
                            "delay": delay_ms,
                            "ts": _ts(created),
                            "dts": _ts(delivered_at) if event_status != "failed" else None,
                        },
                    )
                    if status == "succeeded" and rng.random() < 0.04:
                        conn.execute(
                            text(
                                "INSERT INTO refunds VALUES (:rid, :pid, :amt, 'processed', :ts)"
                            ),
                            {
                                "rid": f"R{payment_count:06d}",
                                "pid": payment_id,
                                "amt": amount // 2,
                                "ts": _ts(created + timedelta(hours=6)),
                            },
                        )
                    if status == "succeeded" and rng.random() < 0.01:
                        conn.execute(
                            text(
                                "INSERT INTO disputes VALUES (:did, :pid, 'fraud', 'open', :ts)"
                            ),
                            {
                                "did": f"D{payment_count:06d}",
                                "pid": payment_id,
                                "ts": _ts(created + timedelta(days=2)),
                            },
                        )
                    payment_count += 1

        payment_count = _plant_incidents(conn, rng, payment_count)

        for merchant_id, *_ in MERCHANTS:
            conn.execute(
                text(
                    "INSERT INTO settlements VALUES (:sid, :mid, :amt, 'settled', :ts)"
                ),
                {
                    "sid": f"S-{merchant_id}",
                    "mid": merchant_id,
                    "amt": 1_000_000,
                    "ts": "2024-06-20 00:00:00",
                },
            )

    return {
        "payments": payment_count,
        "incidents": [INCIDENT_UPI_SPIKE, INCIDENT_WEBHOOK_DELAY, INCIDENT_SPARSE],
    }


def _outcome(
    rng: random.Random, merchant_id: str, method_id: str, created: datetime
) -> tuple[str, str | None, int]:
    delay_ms = rng.randint(80, 2_000)
    # Incident 1: Harbor Retail UPI timeouts 10:00-12:00 on 15 Jun.
    if (
        merchant_id == "M102"
        and method_id == "upi"
        and INCIDENT_UPI_SPIKE["start"] <= created < INCIDENT_UPI_SPIKE["end"]
    ):
        if rng.random() < 0.62:
            return "failed", "GATEWAY_TIMEOUT", delay_ms
    # Incident 2: Cedar webhook delays after successful payments.
    if merchant_id == "M201" and INCIDENT_WEBHOOK_DELAY["start"] <= created < INCIDENT_WEBHOOK_DELAY["end"]:
        delay_ms = rng.randint(45_000, 180_000)
        if rng.random() < 0.12:
            return "failed", "DO_NOT_HONOR", delay_ms
        return "succeeded", None, delay_ms
    # Sparse merchant stays mostly quiet / healthy so investigations look incomplete.
    if merchant_id == "M305":
        if rng.random() < 0.08:
            return "failed", "INSUFFICIENT_FUNDS", delay_ms
        return "succeeded", None, delay_ms

    if rng.random() < 0.07:
        code = rng.choice(["INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "AUTHENTICATION_FAILED"])
        return "failed", code, delay_ms
    return "succeeded", None, delay_ms


def _insert_payment(
    conn,
    payment_count: int,
    merchant_id: str,
    method_id: str,
    created: datetime,
    status: str,
    error_code: str | None,
    delay_ms: int,
    event_status: str,
) -> int:
    order_id = f"O{payment_count:06d}"
    payment_id = f"P{payment_count:06d}"
    amount = 15000
    conn.execute(
        text("INSERT INTO orders VALUES (:oid, :mid, :amt, 'INR', :ts)"),
        {"oid": order_id, "mid": merchant_id, "amt": amount, "ts": _ts(created)},
    )
    conn.execute(
        text(
            "INSERT INTO payments VALUES (:pid, :oid, :mid, :method, :amt, 'INR', :status, :err, :ts)"
        ),
        {
            "pid": payment_id,
            "oid": order_id,
            "mid": merchant_id,
            "method": method_id,
            "amt": amount,
            "status": status,
            "err": error_code,
            "ts": _ts(created),
        },
    )
    delivered_at = created + timedelta(milliseconds=delay_ms)
    conn.execute(
        text(
            "INSERT INTO webhook_events VALUES (:eid, :pid, :etype, :dstatus, :delay, :ts, :dts)"
        ),
        {
            "eid": f"E{payment_count:06d}",
            "pid": payment_id,
            "etype": f"payment.{status}",
            "dstatus": event_status,
            "delay": delay_ms,
            "ts": _ts(created),
            "dts": _ts(delivered_at) if event_status != "failed" else None,
        },
    )
    return payment_count + 1


def _plant_incidents(conn, rng: random.Random, payment_count: int) -> int:
    start = INCIDENT_UPI_SPIKE["start"]
    for minute in range(0, 120, 3):
        created = start + timedelta(minutes=minute)
        failed = minute % 5 != 0
        payment_count = _insert_payment(
            conn,
            payment_count,
            "M102",
            "upi",
            created,
            "failed" if failed else "succeeded",
            "GATEWAY_TIMEOUT" if failed else None,
            rng.randint(80, 2000),
            "delivered",
        )

    start = INCIDENT_WEBHOOK_DELAY["start"]
    for minute in range(0, 120, 4):
        created = start + timedelta(minutes=minute)
        payment_count = _insert_payment(
            conn,
            payment_count,
            "M201",
            "card",
            created,
            "succeeded",
            None,
            rng.randint(45_000, 180_000),
            "delayed",
        )
    return payment_count
