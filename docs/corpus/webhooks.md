---
doc_id: webhook-docs
doc_type: webhook_docs
product_area: platform
title: Webhook delivery
version: 2024-06
---

# Webhook delivery

Events: `payment.succeeded`, `payment.failed`, `refund.processed`.

Delivery statuses: `delivered`, `delayed`, `failed`, `pending`. `delayed` means ACK took longer than 30 seconds.

Merchants that poll only webhooks will appear to have missing captures even when `payments.status = succeeded`.

During a webhook delay incident, success rate stays healthy while delayed-event count rises. Cedar Digital Goods (M201) has seen webhook delay storms that generated false payment-failed tickets.
