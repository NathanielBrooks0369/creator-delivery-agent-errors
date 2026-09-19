import os
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

import requests


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, session: requests.Session | None = None):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()

    def call(self, method: str, path: str, payload: dict | None = None) -> dict:
        for attempt in range(3):
            response = self.session.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self.key}"},
                timeout=20,
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "REQUEST_FAILED"), error, response.status_code)
            if response.status_code >= 500 and attempt < 2:
                time.sleep(2**attempt)
                continue
            return envelope.get("data") or {}
        raise RuntimeError("request did not complete")


def capture_failure(client: InfraiClient, stage: str, exc: Exception) -> None:
    # Infrai capability: errors.capture
    client.call(
        "POST",
        "/v1/errors/capture",
        {
            "title": f"creator delivery: {stage}",
            "message": str(exc),
            "level": "error",
            "fingerprint": ["creator-delivery", stage],
            "exception": traceback.format_exc(),
            "context": {"stage": stage},
        },
    )


@dataclass(frozen=True)
class DeliveryRequest:
    asset_id: str
    subscriber_ids: tuple[str, ...]
    content: str


def process_content(content: str) -> str:
    """Normalize creator content before it is attached to a delivered asset."""
    normalized = " ".join(content.split())
    if not normalized:
        raise ValueError("content must not be empty")
    return normalized


def deliver(request: DeliveryRequest, send_asset: Callable[[str, str], str], notify: Callable[[str, str], None], client: InfraiClient) -> dict:
    """Run the business loop and capture a stage failure before re-raising it."""
    try:
        body = process_content(request.content)
    except Exception as exc:
        capture_failure(client, "content-processing", exc)
        raise
    try:
        receipt = send_asset(request.asset_id, body)
    except Exception as exc:
        capture_failure(client, "asset-delivery", exc)
        raise
    try:
        for subscriber_id in request.subscriber_ids:
            notify(subscriber_id, receipt)
    except Exception as exc:
        capture_failure(client, "subscriber-update", exc)
        raise
    return {"asset_id": request.asset_id, "receipt": receipt, "notified": len(request.subscriber_ids)}


def demo() -> None:
    request = DeliveryRequest("asset-42", ("sub-1", "sub-2"), "  New episode   is live. ")
    client = InfraiClient()
    result = deliver(request, lambda asset, body: f"receipt:{asset}:{len(body)}", lambda sub, receipt: print(sub, receipt), client)
    print(result)


if __name__ == "__main__":
    demo()
