"""
PULSE-Binance Adapter.

Bridge PULSE Protocol messages to Binance API.
Trade, query prices, manage orders — all through PULSE messages.

Example:
    >>> from pulse_binance import BinanceAdapter
    >>> adapter = BinanceAdapter(api_key="...", api_secret="...")
    >>> from pulse import PulseMessage
    >>> msg = PulseMessage(
    ...     action="ACT.QUERY.DATA",
    ...     parameters={"symbol": "BTCUSDT"}
    ... )
    >>> response = adapter.send(msg)
    >>> print(response.content["parameters"]["result"]["price"])
"""

from pulse_binance.adapter import BinanceAdapter
from pulse_binance.version import __version__

__all__ = ["BinanceAdapter", "__version__"]
