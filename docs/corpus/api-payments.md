---
doc_id: api-payments
doc_type: api_docs
product_area: payments
title: Payments API
version: 2024-06
---

# Payments API

Create a payment against an order. A payment belongs to exactly one merchant and one method (`card`, `upi`, `netbanking`, `wallet`).

Statuses: `succeeded`, `failed`, `pending`. Failed payments always carry an `error_code`.

Success rate for a merchant in a window is succeeded / all payments in that window. A method-specific drop with a concentrated error code is a processor incident, not a merchant integration bug.

Webhooks are emitted after capture. A delayed `payment.succeeded` webhook is not a failed payment.
