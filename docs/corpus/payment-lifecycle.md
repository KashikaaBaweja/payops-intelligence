---
doc_id: payment-lifecycle
doc_type: api_docs
product_area: payments
title: Payment lifecycle
version: 2024-06
---

# Payment lifecycle

A payment is created against an order. It belongs to one merchant and one method (`card`, `upi`, `netbanking`, `wallet`).

Statuses: `pending`, `succeeded`, `failed`, `cancelled`.

Success rate in a window is succeeded payments divided by all payments in that window. A method-specific drop with a concentrated error code is a processor incident, not a merchant integration bug.

Capture happens before settlement. A delayed `payment.succeeded` webhook is not a failed payment.
