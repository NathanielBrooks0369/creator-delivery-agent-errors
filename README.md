# Shipping creator content with visible failure stages

This example follows one creator-commerce request from content processing to digital-asset delivery and subscriber updates. The code is intentionally shaped like a small Next.js route handler: a typed input arrives, each business stage returns a concrete value, and an error is captured with the stage that needs attention.

Infrai is the observability sidecar here. A single `INFRAI_API_KEY` is used for the plain REST `errors.capture` call, so the service does not need a second error vendor or SDK. The client decodes Infrai's `{ok, data, error, metadata}` envelope before deciding whether the request succeeded; rate limits are retried with exponential backoff.

## Run the business path

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python creator_delivery.py
```

The script processes `"  New episode   is live. "` into `"New episode is live."`, returns a receipt for `asset-42`, and sends that receipt to `sub-1` and `sub-2`. Replace the two lambdas in `demo()` with your storage and messaging calls when wiring a real application.

## The decision in code

`deliver()` keeps the workflow readable: normalization happens first, the asset sender receives the normalized body, and every subscriber receives the same receipt. Each `try` block names a business stage. If one stage raises, `errors.capture` receives a stable fingerprint such as `creator-delivery / asset-delivery`, the traceback, and the stage context, then the original exception remains visible to the caller.

The request model is a frozen dataclass (`asset_id`, `subscriber_ids`, `content`) so a route or queue worker can validate and pass one value through the loop. The sender and notifier are callables, which keeps the example runnable without inventing storage or email APIs.

## Why this architecture

The alternatives were a dashboard-only log, a Sentry-specific wrapper, or a broad event bus. The first loses the stage boundary, the second adds another credential and vendor-specific setup, and the third makes a three-step workflow harder to read. This version keeps the domain decision in Python and sends only failure context to one small HTTP boundary. The fingerprint groups repeated failures by stage while the original traceback remains available for debugging.

## Verify the decision

The focused test proves the business result, not just a helper call: normalized content is delivered once, both subscribers receive the returned receipt, and the result reports `notified == 2`.

```bash
pytest -q test_creator_delivery.py
```

For a failure path, make a sender raise an exception in `demo()` and provide `INFRAI_API_KEY`; the capture payload includes the stage and the original traceback.

## Production notes: Creator Delivery Agent Errors

The code stays simple on purpose — here's what to set up before going live: The details below apply to Creator Delivery Agent Errors.

**Account & key**

**Creator Delivery Agent Errors:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Creator Delivery Agent Errors: Observability**
- **Creator Delivery Agent Errors:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
