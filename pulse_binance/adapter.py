"""Binance adapter for PULSE Protocol.

Translates PULSE semantic messages to Binance REST API calls.
Query prices, place orders, check balances — all through PULSE messages.

Example:
    >>> adapter = BinanceAdapter(api_key="...", api_secret="...")
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTCUSDT"}
    ... )
    >>> response = adapter.send(msg)
    >>> print(response.content["parameters"]["result"]["price"])
"""

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from pulse.message import PulseMessage
from pulse.adapter import PulseAdapter, AdapterError, AdapterConnectionError


# Binance API endpoints
ENDPOINTS = {
    "ticker": "/api/v3/ticker/price",
    "ticker_24h": "/api/v3/ticker/24hr",
    "klines": "/api/v3/klines",
    "depth": "/api/v3/depth",
    "order": "/api/v3/order",
    "open_orders": "/api/v3/openOrders",
    "account": "/api/v3/account",
    "server_time": "/api/v3/time",
}

# Map PULSE actions to Binance operations
ACTION_MAP = {
    "ACT.QUERY.DATA": "query",
    "ACT.QUERY.STATUS": "order_status",
    "ACT.TRANSACT.REQUEST": "place_order",
    "ACT.CANCEL": "cancel_order",
    "ACT.QUERY.LIST": "open_orders",
    "ACT.QUERY.BALANCE": "account",
}


class BinanceAdapter(PulseAdapter):
    """PULSE adapter for Binance exchange.

    Translates PULSE semantic actions to Binance REST API calls.
    Same interface as OpenAI/Anthropic adapters — your bot speaks PULSE,
    the adapter handles Binance specifics.

    Supported PULSE actions:
        - ACT.QUERY.DATA — get ticker price, 24h stats, klines, order book
        - ACT.QUERY.STATUS — check order status
        - ACT.QUERY.LIST — list open orders
        - ACT.QUERY.BALANCE — get account balances
        - ACT.TRANSACT.REQUEST — place an order (BUY/SELL)
        - ACT.CANCEL — cancel an order

    Example:
        >>> adapter = BinanceAdapter(api_key="...", api_secret="...")
        >>> # Get BTC price
        >>> msg = PulseMessage(
        ...     action="ACT.QUERY.DATA",
        ...     parameters={"symbol": "BTCUSDT"}
        ... )
        >>> response = adapter.send(msg)
        >>> print(response.content["parameters"]["result"]["price"])
    """

    BASE_URL = "https://api.binance.com"
    TESTNET_URL = "https://testnet.binance.vision"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        base_url = self.TESTNET_URL if testnet else self.BASE_URL
        super().__init__(
            name="binance",
            base_url=base_url,
            config=config or {},
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._session: Optional[requests.Session] = None

    def connect(self) -> None:
        """Initialize HTTP session and verify connectivity."""
        self._session = requests.Session()
        if self._api_key:
            self._session.headers.update({"X-MBX-APIKEY": self._api_key})

        try:
            resp = self._session.get(f"{self.base_url}{ENDPOINTS['server_time']}", timeout=10)
            resp.raise_for_status()
            self.connected = True
        except requests.ConnectionError as e:
            raise AdapterConnectionError(f"Cannot reach Binance API: {e}") from e
        except requests.HTTPError as e:
            raise AdapterConnectionError(f"Binance API error: {e}") from e

    def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            self._session.close()
        self._session = None
        self.connected = False

    def to_native(self, message: PulseMessage) -> Dict[str, Any]:
        """Convert PULSE message to Binance API request.

        Args:
            message: PULSE message with action and parameters

        Returns:
            Dictionary with method, endpoint, params, and signed flag
        """
        action = message.content["action"]
        params = message.content.get("parameters", {})
        operation = ACTION_MAP.get(action)

        if not operation:
            raise AdapterError(
                f"Unsupported action '{action}'. Supported: {list(ACTION_MAP.keys())}"
            )

        if operation == "query":
            return self._build_query_request(params)
        elif operation == "place_order":
            return self._build_order_request(params)
        elif operation == "cancel_order":
            return self._build_cancel_request(params)
        elif operation == "order_status":
            return self._build_status_request(params)
        elif operation == "open_orders":
            return self._build_open_orders_request(params)
        elif operation == "account":
            return self._build_account_request()

        raise AdapterError(f"Unknown operation: {operation}")

    def call_api(self, native_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Binance API call.

        Args:
            native_request: Request dict from to_native()

        Returns:
            Binance API response as dictionary
        """
        if not self._session:
            self._ensure_session()

        method = native_request["method"]
        url = f"{self.base_url}{native_request['endpoint']}"
        params = native_request.get("params", {})

        # Sign request if needed
        if native_request.get("signed"):
            if not self._api_secret:
                raise AdapterError("API secret required for signed requests (orders, balance).")
            params = self._sign_request(params)

        try:
            if method == "GET":
                resp = self._session.get(url, params=params, timeout=10)
            elif method == "POST":
                resp = self._session.post(url, params=params, timeout=10)
            elif method == "DELETE":
                resp = self._session.delete(url, params=params, timeout=10)
            else:
                raise AdapterError(f"Unknown HTTP method: {method}")

            # Handle errors
            if resp.status_code != 200:
                error_data = resp.json() if resp.text else {}
                error_code = self.map_error_code(resp.status_code)
                binance_code = error_data.get("code", "unknown")
                binance_msg = error_data.get("msg", resp.text)
                raise AdapterError(
                    f"Binance error {binance_code}: {binance_msg} ({error_code})"
                )

            return resp.json()

        except (requests.ConnectionError, ConnectionError) as e:
            raise AdapterConnectionError(f"Cannot reach Binance: {e}") from e
        except (requests.Timeout, TimeoutError) as e:
            raise AdapterConnectionError(f"Binance request timed out: {e}") from e
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(f"Binance request failed: {e}") from e

    def from_native(self, native_response: Any) -> PulseMessage:
        """Convert Binance response to PULSE message.

        Args:
            native_response: Response from Binance API

        Returns:
            PULSE response message
        """
        return PulseMessage(
            action="ACT.RESPOND",
            parameters={"result": native_response},
            validate=False,
        )

    @property
    def supported_actions(self) -> List[str]:
        """Actions this adapter supports."""
        return list(ACTION_MAP.keys())

    # --- Request Builders ---

    def _build_query_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build market data query request."""
        symbol = params.get("symbol")
        query_type = params.get("type", "price")

        if query_type == "price":
            req = {"method": "GET", "endpoint": ENDPOINTS["ticker"], "signed": False}
            if symbol:
                req["params"] = {"symbol": symbol.upper()}
            return req

        elif query_type == "24h":
            req = {"method": "GET", "endpoint": ENDPOINTS["ticker_24h"], "signed": False}
            if symbol:
                req["params"] = {"symbol": symbol.upper()}
            return req

        elif query_type == "klines":
            if not symbol:
                raise AdapterError("Symbol required for klines query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["klines"],
                "params": {
                    "symbol": symbol.upper(),
                    "interval": params.get("interval", "1h"),
                    "limit": params.get("limit", 100),
                },
                "signed": False,
            }

        elif query_type == "depth":
            if not symbol:
                raise AdapterError("Symbol required for depth query.")
            return {
                "method": "GET",
                "endpoint": ENDPOINTS["depth"],
                "params": {
                    "symbol": symbol.upper(),
                    "limit": params.get("limit", 20),
                },
                "signed": False,
            }

        raise AdapterError(f"Unknown query type '{query_type}'. Use: price, 24h, klines, depth.")

    def _build_order_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order placement request."""
        required = ["symbol", "side", "quantity"]
        for field in required:
            if field not in params:
                raise AdapterError(f"Missing required field '{field}' for order placement.")

        order_params = {
            "symbol": params["symbol"].upper(),
            "side": params["side"].upper(),
            "type": params.get("order_type", "MARKET").upper(),
            "quantity": str(params["quantity"]),
            "timestamp": int(time.time() * 1000),
        }

        # Add price for LIMIT orders
        if order_params["type"] == "LIMIT":
            if "price" not in params:
                raise AdapterError("Price required for LIMIT orders.")
            order_params["price"] = str(params["price"])
            order_params["timeInForce"] = params.get("time_in_force", "GTC")

        return {
            "method": "POST",
            "endpoint": ENDPOINTS["order"],
            "params": order_params,
            "signed": True,
        }

    def _build_cancel_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order cancellation request."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order cancellation.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for cancellation.")

        return {
            "method": "DELETE",
            "endpoint": ENDPOINTS["order"],
            "params": {
                "symbol": params["symbol"].upper(),
                "orderId": params["order_id"],
                "timestamp": int(time.time() * 1000),
            },
            "signed": True,
        }

    def _build_status_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build order status query request."""
        if "symbol" not in params:
            raise AdapterError("Symbol required for order status query.")
        if "order_id" not in params:
            raise AdapterError("Order ID required for status query.")

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["order"],
            "params": {
                "symbol": params["symbol"].upper(),
                "orderId": params["order_id"],
                "timestamp": int(time.time() * 1000),
            },
            "signed": True,
        }

    def _build_open_orders_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build open orders query request."""
        req_params = {"timestamp": int(time.time() * 1000)}
        if "symbol" in params:
            req_params["symbol"] = params["symbol"].upper()

        return {
            "method": "GET",
            "endpoint": ENDPOINTS["open_orders"],
            "params": req_params,
            "signed": True,
        }

    def _build_account_request(self) -> Dict[str, Any]:
        """Build account info request."""
        return {
            "method": "GET",
            "endpoint": ENDPOINTS["account"],
            "params": {"timestamp": int(time.time() * 1000)},
            "signed": True,
        }

    # --- Helpers ---

    def _sign_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add HMAC-SHA256 signature to request parameters."""
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _ensure_session(self) -> None:
        """Create session if not exists."""
        if not self._session:
            self._session = requests.Session()
            if self._api_key:
                self._session.headers.update({"X-MBX-APIKEY": self._api_key})

    def __repr__(self) -> str:
        return (
            f"BinanceAdapter(testnet={self._testnet}, "
            f"connected={self.connected})"
        )
