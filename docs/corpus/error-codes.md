---
doc_id: error-codes
doc_type: error_codes
product_area: payments
title: Failure code reference
version: 2024-06
---

# Failure code reference

`GATEWAY_TIMEOUT`: the method processor did not respond. Typical during UPI or card-network brownouts. Ops action: fail over, page the processor, do not retry infinitely.

`INSUFFICIENT_FUNDS`: issuer decline. Not an incident unless it spikes across many issuers.

`DO_NOT_HONOR`: generic issuer decline. Investigate only if concentrated on one acquirer.

`AUTHENTICATION_FAILED`: customer 3DS / UPI PIN. Not a platform outage.

`WEBHOOK_TIMEOUT`: consumer did not ACK. Payment may still have succeeded.
