from src.execution.schwab_bridge import SchwabBridge


def test_schwab_bridge_submit_order():
    b = SchwabBridge(token="t")
    resp = b.submit_order({"symbol": "ABC", "qty": 10})
    assert resp["status"] == "submitted"
