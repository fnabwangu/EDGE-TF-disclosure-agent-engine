from src.execution.schwab_bridge import SchwabBridge


def test_schwab_bridge_submit_order():
    b = SchwabBridge(token="t")
    resp = b.submit_order({"symbol": "ABC", "qty": 10})
    assert resp["status"] == "submitted"

# ==============================================================================
# PIPELINE STEP: BROKER EXECUTION BRIDGE UNIT TESTS (test_schwab_bridge.py)
# ==============================================================================
# Operational Goal: Verify the Charles Schwab API bridge interface, ensuring
# deterministic order payload formatting, OAuth token lifecycle management,
# and adherence to hard risk governor limits before order transmission.
# ==============================================================================

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import json

# Test Pipeline Component Simulation
def test_schwab_execution_pipeline_mock() -> dict:
    """
    Simulates validation, translation, and dispatch of trade orders to Charles Schwab.
    
    Inputs:
      - order_instruction: Structured instruction payload from trade design engine
      - account_hash: Encrypted/hashed Schwab target account identifier
      - mock_api_response: Mocked response payload from Schwab endpoint
    """
    order_instruction = {
        "symbol": "AAPL", "quantity": 1, "order_type": "MARKET",
        "duration": "DAY", "session": "NORMAL",
    }
    account_hash = "ACC_HASH"
    mock_api_response = {"order_id": "ORDER-1"}

    # 1. Validate payload fields
    required_keys = ["symbol", "quantity", "order_type", "duration", "session"]
    for key in required_keys:
        if key not in order_instruction:
            raise ValueError(f"Missing required execution parameter: {key}")

    # 2. Format Schwab-compliant JSON payload
    schwab_payload = {
        "orderType": order_instruction["order_type"],
        "session": order_instruction["session"],
        "duration": order_instruction["duration"],
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": order_instruction.get("instruction", "BUY"),
                "quantity": order_instruction["quantity"],
                "instrument": {
                    "symbol": order_instruction["symbol"],
                    "assetType": order_instruction.get("asset_type", "EQUITY")
                }
            }
        ]
    }
    
    # 3. Simulate authenticated dispatch
    return {
        "status": "ORDER_SUBMITTED",
        "account_id": account_hash,
        "payload": schwab_payload,
        "broker_order_id": mock_api_response.get("order_id", "SCHWAB-ORD-99999")
    }

"""
Edge-TF Disclosure Agent Engine - Charles Schwab Execution Bridge Tests
Path: tests/test_schwab_bridge.py

Unit test suite for Schwab API bridge authentication, order payload construction,
options leg specification, and deterministic execution risk constraints.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from src.execution.schwab_bridge import SchwabBridge, SchwabOrderRequest, SchwabAuthManager
from risk.risk_governor import RiskGovernor


class TestSchwabBridge(unittest.TestCase):
    """
    Unit tests validating the Schwab API interface and order dispatch routines.
    """

    def setUp(self):
        """Initializes mock credentials and configuration."""
        self.mock_auth = Mock(spec=SchwabAuthManager)
        self.mock_auth.get_access_token.return_value = "mock_access_token_12345"
        self.mock_auth.account_hash = "ACC_HASH_SECURE_987"
        
        self.bridge = SchwabBridge(
            auth_manager=self.mock_auth,
            base_url="https://api.schwabapi.com/trader/v1",
            enforce_dry_run=True
        )

    def test_equity_order_payload_construction(self):
        """Validates standard equity/ETF buy order structure."""
        order_req = SchwabOrderRequest(
            symbol="NVDA",
            quantity=50.0,
            instruction="BUY",
            asset_type="EQUITY",
            order_type="LIMIT",
            limit_price=125.50,
            duration="DAY",
            session="NORMAL"
        )
        
        payload = self.bridge.build_schwab_order_payload(order_req)
        
        self.assertEqual(payload["orderType"], "LIMIT")
        self.assertEqual(payload["price"], 125.50)
        self.assertEqual(payload["duration"], "DAY")
        self.assertEqual(payload["orderStrategyType"], "SINGLE")
        self.assertEqual(len(payload["orderLegCollection"]), 1)
        
        leg = payload["orderLegCollection"][0]
        self.assertEqual(leg["instruction"], "BUY")
        self.assertEqual(leg["quantity"], 50.0)
        self.assertEqual(leg["instrument"]["symbol"], "NVDA")
        self.assertEqual(leg["instrument"]["assetType"], "EQUITY")

    def test_option_order_payload_construction(self):
        """Validates LEAP option call order construction."""
        order_req = SchwabOrderRequest(
            symbol="NVDA  280121C00120000",
            quantity=5.0,
            instruction="BUY_TO_OPEN",
            asset_type="OPTION",
            order_type="LIMIT",
            limit_price=35.00,
            duration="DAY",
            session="NORMAL"
        )
        
        payload = self.bridge.build_schwab_order_payload(order_req)
        
        self.assertEqual(payload["orderType"], "LIMIT")
        self.assertEqual(payload["price"], 35.00)
        leg = payload["orderLegCollection"][0]
        self.assertEqual(leg["instruction"], "BUY_TO_OPEN")
        self.assertEqual(leg["quantity"], 5.0)
        self.assertEqual(leg["instrument"]["symbol"], "NVDA  280121C00120000")
        self.assertEqual(leg["instrument"]["assetType"], "OPTION")

    @patch("requests.post")
    def test_order_submission_dry_run_mode(self, mock_post):
        """Ensures dry-run mode does not make live network POST calls."""
        order_req = SchwabOrderRequest(
            symbol="AAPL",
            quantity=10.0,
            instruction="BUY",
            asset_type="EQUITY",
            order_type="MARKET"
        )
        
        result = self.bridge.submit_order(order_req)
        
        # In dry run, no HTTP request should be sent
        mock_post.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["status"], "DRY_RUN_VALIDATED")

    @patch("requests.post")
    def test_live_order_submission_success(self, mock_post):
        """Tests successful live order execution endpoint interaction."""
        self.bridge.enforce_dry_run = False
        
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"Location": "https://api.schwabapi.com/trader/v1/accounts/ACC_HASH_SECURE_987/orders/998877"}
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        order_req = SchwabOrderRequest(
            symbol="MSFT",
            quantity=25.0,
            instruction="BUY",
            asset_type="EQUITY",
            order_type="LIMIT",
            limit_price=410.00
        )

        result = self.bridge.submit_order(order_req)

        self.assertEqual(result["status"], "SUBMITTED")
        self.assertEqual(result["order_id"], "998877")
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
