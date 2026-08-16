"""schwab_bridge.py
Very small mock of Schwab bridge for tests.
"""
class SchwabBridge:
    def __init__(self, token: str = None):
        self.token = token

    def submit_order(self, payload: dict) -> dict:
        # Mock behavior for tests
        return {"status": "submitted", "order": payload}
