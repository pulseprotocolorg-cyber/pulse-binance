# pulse-binance

Binance adapter for [PULSE Protocol](https://github.com/pulseprotocolorg-cyber/pulse-python).

Trade, query prices, manage orders — all through PULSE semantic messages.

## Install

```bash
pip install pulse-binance
```

## Quick Start

```python
from pulse import PulseMessage
from pulse_binance import BinanceAdapter

adapter = BinanceAdapter(api_key="...", api_secret="...")

# Get BTC price
msg = PulseMessage(
    action="ACT.QUERY.DATA",
    parameters={"symbol": "BTCUSDT"}
)
response = adapter.send(msg)
print(response.content["parameters"]["result"]["price"])

# Place a market buy order
msg = PulseMessage(
    action="ACT.TRANSACT.REQUEST",
    parameters={"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001}
)
response = adapter.send(msg)
print(response.content["parameters"]["result"]["status"])
```

## Supported Actions

| PULSE Action | What it does |
|---|---|
| `ACT.QUERY.DATA` | Get price, 24h stats, klines, order book |
| `ACT.TRANSACT.REQUEST` | Place order (MARKET/LIMIT, BUY/SELL) |
| `ACT.CANCEL` | Cancel an order |
| `ACT.QUERY.STATUS` | Check order status |
| `ACT.QUERY.LIST` | List open orders |
| `ACT.QUERY.BALANCE` | Get account balances |

## Switch Exchanges in One Line

```python
# from pulse_binance import BinanceAdapter as Exchange
from pulse_bybit import BybitAdapter as Exchange

adapter = Exchange(api_key="...", api_secret="...")
# Everything else stays the same
```

## License

Apache 2.0
