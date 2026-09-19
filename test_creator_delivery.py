from creator_delivery import DeliveryRequest, InfraiClient, deliver


class NoNetworkClient(InfraiClient):
    def __init__(self):
        pass

    def call(self, method, path, payload=None):
        raise AssertionError("capture is not expected on the successful path")


def test_delivery_normalizes_content_and_notifies_each_subscriber():
    sent = []
    notified = []
    result = deliver(
        DeliveryRequest("asset-7", ("alice", "bob"), "  launch   notes "),
        lambda asset, body: sent.append((asset, body)) or "receipt-7",
        lambda subscriber, receipt: notified.append((subscriber, receipt)),
        NoNetworkClient(),
    )
    assert sent == [("asset-7", "launch notes")]
    assert notified == [("alice", "receipt-7"), ("bob", "receipt-7")]
    assert result["notified"] == 2
