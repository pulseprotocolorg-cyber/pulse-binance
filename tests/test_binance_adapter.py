"""Tests for Binance adapter. All mocked — no real API calls."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from pulse.message import PulseMessage
from pulse.adapter import AdapterError, AdapterConnectionError

from pulse_binance import BinanceAdapter


# --- Mock Helpers ---


def mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    mock.raise_for_status.return_value = None
    return mock


# --- Fixtures ---


@pytest.fixture
def adapter():
    """Create a BinanceAdapter with mocked session."""
    a = BinanceAdapter(api_key="test-key", api_secret="test-secret")
    a._session = MagicMock()
    a.connected = True
    return a


@pytest.fixture
def price_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT"},
        sender="test-bot",
    )


@pytest.fixture
def price_24h_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT", "type": "24h"},
        sender="test-bot",
    )


@pytest.fixture
def klines_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT", "type": "klines", "interval": "4h", "limit": 50},
        sender="test-bot",
    )


@pytest.fixture
def depth_message():
    return PulseMessage(
        action="ACT.QUERY.DATA",
        parameters={"symbol": "BTCUSDT", "type": "depth", "limit": 10},
        sender="test-bot",
    )


@pytest.fixture
def buy_message():
    return PulseMessage(
        action="ACT.TRANSACT.REQUEST",
        parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def limit_buy_message():
    return PulseMessage(
        action="ACT.TRANSACT.REQUEST",
        parameters={
            "symbol": "ETHUSDT",
            "side": "BUY",
            "quantity": 1.0,
            "order_type": "LIMIT",
            "price": 2000.0,
        },
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def cancel_message():
    return PulseMessage(
        action="ACT.CANCEL",
        parameters={"symbol": "BTCUSDT", "order_id": 12345},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def status_message():
    return PulseMessage(
        action="ACT.QUERY.STATUS",
        parameters={"symbol": "BTCUSDT", "order_id": 12345},
        sender="test-bot",
        validate=False,
    )


@pytest.fixture
def balance_message():
    return PulseMessage(
        action="ACT.QUERY.BALANCE",
        parameters={},
        sender="test-bot",
        validate=False,
    )


# --- Test Initialization ---


class TestBinanceAdapterInit:

    def test_basic_init(self):
        adapter = BinanceAdapter(api_key="key", api_secret="secret")
        assert adapter.name == "binance"
        assert adapter.base_url == "https://api.binance.com"
        assert adapter.connected is False

    def test_testnet_init(self):
        adapter = BinanceAdapter(testnet=True)
        assert adapter.base_url == "https://testnet.binance.vision"
        assert adapter._testnet is True

    def test_repr(self):
        adapter = BinanceAdapter(api_key="k", api_secret="s")
        r = repr(adapter)
        assert "testnet=False" in r
        assert "connected=False" in r


# --- Test to_native: Market Data ---


class TestToNativeMarketData:

    def test_price_query(self, adapter, price_message):
        native = adapter.to_native(price_message)
        assert native["method"] == "GET"
        assert native["endpoint"] == "/api/v3/ticker/price"
        assert native["params"]["symbol"] == "BTCUSDT"
        assert native["signed"] is False

    def test_price_all_symbols(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={})
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/api/v3/ticker/price"
        assert "params" not in native or "symbol" not in native.get("params", {})

    def test_24h_query(self, adapter, price_24h_message):
        native = adapter.to_native(price_24h_message)
        assert native["endpoint"] == "/api/v3/ticker/24hr"
        assert native["params"]["symbol"] == "BTCUSDT"

    def test_klines_query(self, adapter, klines_message):
        native = adapter.to_native(klines_message)
        assert native["endpoint"] == "/api/v3/klines"
        assert native["params"]["interval"] == "4h"
        assert native["params"]["limit"] == 50

    def test_depth_query(self, adapter, depth_message):
        native = adapter.to_native(depth_message)
        assert native["endpoint"] == "/api/v3/depth"
        assert native["params"]["limit"] == 10

    def test_symbol_uppercased(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "btcusdt"})
        native = adapter.to_native(msg)
        assert native["params"]["symbol"] == "BTCUSDT"

    def test_unknown_query_type_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"type": "invalid"})
        with pytest.raises(AdapterError, match="Unknown query type"):
            adapter.to_native(msg)

    def test_klines_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"type": "klines"})
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)


# --- Test to_native: Orders ---


class TestToNativeOrders:

    def test_market_buy(self, adapter, buy_message):
        native = adapter.to_native(buy_message)
        assert native["method"] == "POST"
        assert native["endpoint"] == "/api/v3/order"
        assert native["params"]["symbol"] == "BTCUSDT"
        assert native["params"]["side"] == "BUY"
        assert native["params"]["type"] == "MARKET"
        assert native["params"]["quantity"] == "0.001"
        assert native["signed"] is True

    def test_limit_buy(self, adapter, limit_buy_message):
        native = adapter.to_native(limit_buy_message)
        assert native["params"]["type"] == "LIMIT"
        assert native["params"]["price"] == "2000.0"
        assert native["params"]["timeInForce"] == "GTC"

    def test_limit_order_no_price_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 1, "order_type": "LIMIT"},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Price required"):
            adapter.to_native(msg)

    def test_order_missing_symbol_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"side": "BUY", "quantity": 1},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Missing required field 'symbol'"):
            adapter.to_native(msg)

    def test_order_missing_side_raises(self, adapter):
        msg = PulseMessage(
            action="ACT.TRANSACT.REQUEST",
            parameters={"symbol": "BTCUSDT", "quantity": 1},
            validate=False,
        )
        with pytest.raises(AdapterError, match="Missing required field 'side'"):
            adapter.to_native(msg)

    def test_cancel_order(self, adapter, cancel_message):
        native = adapter.to_native(cancel_message)
        assert native["method"] == "DELETE"
        assert native["params"]["orderId"] == 12345
        assert native["signed"] is True

    def test_cancel_no_symbol_raises(self, adapter):
        msg = PulseMessage(action="ACT.CANCEL", parameters={"order_id": 123}, validate=False)
        with pytest.raises(AdapterError, match="Symbol required"):
            adapter.to_native(msg)

    def test_cancel_no_order_id_raises(self, adapter):
        msg = PulseMessage(action="ACT.CANCEL", parameters={"symbol": "BTCUSDT"}, validate=False)
        with pytest.raises(AdapterError, match="Order ID required"):
            adapter.to_native(msg)


# --- Test to_native: Account ---


class TestToNativeAccount:

    def test_order_status(self, adapter, status_message):
        native = adapter.to_native(status_message)
        assert native["method"] == "GET"
        assert native["endpoint"] == "/api/v3/order"
        assert native["params"]["orderId"] == 12345
        assert native["signed"] is True

    def test_open_orders(self, adapter):
        msg = PulseMessage(action="ACT.QUERY.LIST", parameters={"symbol": "BTCUSDT"}, validate=False)
        native = adapter.to_native(msg)
        assert native["endpoint"] == "/api/v3/openOrders"
        assert native["signed"] is True

    def test_account_balance(self, adapter, balance_message):
        native = adapter.to_native(balance_message)
        assert native["endpoint"] == "/api/v3/account"
        assert native["signed"] is True

    def test_unsupported_action_raises(self, adapter):
        msg = PulseMessage(action="ACT.CREATE.TEXT", parameters={}, validate=False)
        with pytest.raises(AdapterError, match="Unsupported action"):
            adapter.to_native(msg)


# --- Test call_api ---


class TestCallAPI:

    def test_get_request(self, adapter):
        adapter._session.get.return_value = mock_response(
            {"symbol": "BTCUSDT", "price": "65432.10"}
        )
        result = adapter.call_api({
            "method": "GET",
            "endpoint": "/api/v3/ticker/price",
            "params": {"symbol": "BTCUSDT"},
            "signed": False,
        })
        assert result["price"] == "65432.10"

    def test_post_request(self, adapter):
        adapter._session.post.return_value = mock_response(
            {"orderId": 12345, "status": "FILLED"}
        )
        result = adapter.call_api({
            "method": "POST",
            "endpoint": "/api/v3/order",
            "params": {"symbol": "BTCUSDT", "side": "BUY", "quantity": "0.001"},
            "signed": True,
        })
        assert result["orderId"] == 12345

    def test_delete_request(self, adapter):
        adapter._session.delete.return_value = mock_response(
            {"orderId": 12345, "status": "CANCELED"}
        )
        result = adapter.call_api({
            "method": "DELETE",
            "endpoint": "/api/v3/order",
            "params": {"symbol": "BTCUSDT", "orderId": 12345},
            "signed": True,
        })
        assert result["status"] == "CANCELED"

    def test_api_error_response(self, adapter):
        adapter._session.get.return_value = mock_response(
            {"code": -1121, "msg": "Invalid symbol."},
            status_code=400,
        )
        with pytest.raises(AdapterError, match="Invalid symbol"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v3/ticker/price",
                "params": {"symbol": "INVALID"},
                "signed": False,
            })

    def test_signed_without_secret_raises(self, adapter):
        adapter._api_secret = None
        with pytest.raises(AdapterError, match="API secret required"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v3/account",
                "params": {},
                "signed": True,
            })

    def test_connection_error(self, adapter):
        adapter._session.get.side_effect = ConnectionError("Network down")
        with pytest.raises(AdapterConnectionError, match="Cannot reach"):
            adapter.call_api({
                "method": "GET",
                "endpoint": "/api/v3/ticker/price",
                "signed": False,
            })


# --- Test from_native ---


class TestFromNative:

    def test_response_conversion(self, adapter):
        native = {"symbol": "BTCUSDT", "price": "65432.10"}
        response = adapter.from_native(native)
        assert isinstance(response, PulseMessage)
        assert response.content["parameters"]["result"]["price"] == "65432.10"


# --- Test Full Pipeline ---


class TestFullPipeline:

    def test_price_query_pipeline(self, adapter, price_message):
        adapter._session.get.return_value = mock_response(
            {"symbol": "BTCUSDT", "price": "65432.10"}
        )
        response = adapter.send(price_message)
        assert response.type == "RESPONSE"
        assert response.envelope["sender"] == "adapter:binance"
        assert response.content["parameters"]["result"]["price"] == "65432.10"

    def test_order_pipeline(self, adapter, buy_message):
        adapter._session.post.return_value = mock_response(
            {"orderId": 99999, "status": "FILLED", "executedQty": "0.001"}
        )
        response = adapter.send(buy_message)
        assert response.type == "RESPONSE"
        assert response.content["parameters"]["result"]["status"] == "FILLED"

    def test_pipeline_tracks_requests(self, adapter, price_message):
        adapter._session.get.return_value = mock_response({"price": "100"})
        adapter.send(price_message)
        adapter.send(price_message)
        assert adapter._request_count == 2


# --- Test Signing ---


class TestSigning:

    def test_sign_adds_signature(self, adapter):
        params = {"symbol": "BTCUSDT", "timestamp": 1234567890}
        signed = adapter._sign_request(params)
        assert "signature" in signed
        assert len(signed["signature"]) == 64  # SHA256 hex


# --- Test Supported Actions ---


class TestSupportedActions:

    def test_supported_actions(self, adapter):
        actions = adapter.supported_actions
        assert "ACT.QUERY.DATA" in actions
        assert "ACT.TRANSACT.REQUEST" in actions
        assert "ACT.CANCEL" in actions
        assert "ACT.QUERY.BALANCE" in actions
        assert len(actions) == 6

    def test_supports_check(self, adapter):
        assert adapter.supports("ACT.QUERY.DATA") is True
        assert adapter.supports("ACT.CREATE.TEXT") is False
