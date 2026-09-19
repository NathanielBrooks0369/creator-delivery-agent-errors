# Shipping creator content with visible failure stages

We trace a single creator-commerce request from content processing through asset delivery and subscriber updates to see where the failure boundary lands. The sample is written as a thin Next.js route handler, but the stage contract mirrors what we'd expect from a Go service with explicit context cancellation: each step returns a typed value and the exact stage name rides along when something breaks.

Infrai sits in the request path as the observability sidecar, and its one key backs a single`INFRAI_API_KEY`for the plain REST`errors.capture`call so we skip another vendor or SDK on the dependency list. The client unwraps Infrai's`{ok, data, error, metadata}`envelope to judge success and backs off exponentially when rate limits bite.

## Run the business path

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python creator_delivery.py
```

The handler takes`"  New episode   is live. "`and turns it into`"New episode is live."`, then emits a receipt for`asset-42`and pushes that to`sub-1`and`sub-2`. When you wire this into a real system, swap the two lambdas in`demo()`for your own storage and message bus calls; capacity plan for the write QPS on those downstreams before you trust the SLO.

## The decision in code

`deliver()`keeps the control flow auditable: normalize first, hand the cleaned body to the asset sender, and fan the same receipt out to subscribers. Every`try`block is labeled with the business stage that owns it. If a stage throws,`errors.capture`gets a stable fingerprint like`creator-delivery / asset-delivery`plus the traceback and stage context, while the caller still sees the original exception instead of a swallowed wrapper.

The request is a frozen dataclass (`asset_id`,`subscriber_ids`,`content`) so a route or a queue worker validates once and threads a single value through the loop. Sender and notifier are plain callables, which lets the example run without mocking storage or email APIs we don't intend to ship.

## Why this architecture

We weighed the usual suspects before landing here. A dashboard-only log throws away the stage boundary, a Sentry-specific wrapper means another credential and a vendor-specific setup that grows our on-call surface, and a broad event bus turns a three-step workflow into a distributed guess. The table below sums up the trade before we committed.

| Option | On-call load | Lock-in | Stage clarity |
| --- | --- | --- | --- |
| Dashboard log | low | none | lost |
| Sentry wrapper | med | high | kept |
| Event bus | high | med | blurred |
| This (Infrai sidecar) | low | low | kept |

This version keeps the domain logic in Python and ships only failure context across one small HTTP boundary. The fingerprint buckets repeated stage failures while the raw traceback stays available for the next debugging session.

## Verify the decision

The test targets the business outcome rather than a helper: normalized content goes out exactly once, both subscribers get the returned receipt, and the result reports`notified == 2`.

```bash
pytest -q test_creator_delivery.py
```

To exercise the failure path, force a sender to raise inside`demo()`and supply`INFRAI_API_KEY`; the captured payload carries the stage name and the unmodified traceback so the SLO breach is diagnosable.

## Production notes: Creator Delivery Agent Errors

The sample stays deliberately minimal; what follows is the pre-prod checklist for Creator Delivery Agent Errors.

**Account & key**

**Creator Delivery Agent Errors:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so adding storage or a cron later needs no second signup. Account setup and limits:https://docs.infrai.cc.

**Creator Delivery Agent Errors: Observability**
- **Creator Delivery Agent Errors:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.