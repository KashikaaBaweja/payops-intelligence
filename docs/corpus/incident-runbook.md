---
doc_id: incident-runbook
doc_type: runbook
product_area: ops
title: Incident runbook
version: 2024-06
---

# Incident runbook

1. Confirm the merchant, method, and time window.
2. Compare success rate in-window vs the previous equal window.
3. Break down failures by error code and method.
4. Inspect webhook delay/failure counts so delayed notifications are not misread as declines.
5. If evidence is thin (low volume merchant), do not name a root cause. Report insufficient evidence.

Harbor Retail (M102) historically sees UPI `GATEWAY_TIMEOUT` clusters around midday processor incidents.
Cedar Digital Goods (M201) has seen webhook delay storms that generated false "payment failed" tickets.
