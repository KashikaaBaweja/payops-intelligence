---
doc_id: payment-failures
doc_type: runbook
product_area: payments
title: Payment failures
version: 2024-06
---

# Payment failures

Investigate failures by merchant, method, and time window.

`GATEWAY_TIMEOUT` means the method processor did not respond. Typical during UPI or card-network brownouts. Ops action: fail over, page the processor, do not retry infinitely.

A spike limited to one method with `GATEWAY_TIMEOUT` is a gateway incident. Mixed issuer codes (`INSUFFICIENT_FUNDS`, `DO_NOT_HONOR`) are usually not a platform outage.

Harbor Retail (M102) historically sees UPI `GATEWAY_TIMEOUT` clusters around midday processor incidents.
