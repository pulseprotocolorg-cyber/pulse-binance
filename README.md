# PULSE-Binance

**Binance adapter for PULSE Protocol — trade Binance with semantic messages.**

Write your trading bot once, run it on any exchange. Same code works with Bybit, Kraken, OKX — just change one line.

## Quick Start

```bash
pip install pulse-binance
```

```python
from pulse import PulseMessage
from pulse_binance import BinanceAdapter

# Connect
adapter = BinanceAdapter(api_key="your-key", api_secret="your-secret")
adapter.connect()

# Get BTC price
msg = PulseMessage(action="ACT.QUERY.DATA", parameters={"symbol": "BTCUSDT"})
response = adapter.send(msg)
print(response.content["parameters"]["result"]["price"])
```

## Switch Exchanges in One Line

```python
# from pulse_binance import BinanceAdapter as Adapter
from pulse_bybit import BybitAdapter as Adapter

adapter = Adapter(api_key="...", api_secret="...")
```

Your bot code stays exactly the same. Only the import changes.

## Supported Actions

| PULSE Action | What It Does | Binance Endpoint |
|---|---|---|
| `ACT.QUERY.DATA` | Price, 24h stats, klines, order book | `/api/v3/ticker/price`, `/klines`, `/depth` |
| `ACT.TRANSACT.REQUEST` | Place market/limit order | `/api/v3/order` |
| `ACT.CANCEL` | Cancel an order | `/api/v3/order` (DELETE) |
| `ACT.QUERY.STATUS` | Check order status | `/api/v3/order` (GET) |
| `ACT.QUERY.LIST` | List open orders | `/api/v3/openOrders` |
| `ACT.QUERY.BALANCE` | Account balances | `/api/v3/account` |

## Examples

### Query price

```python
msg = PulseMessage(
    action="ACT.QUERY.DATA",
    parameters={"symbol": "BTCUSDT", "type": "price"}
)
response = adapter.send(msg)
```

### Place a limit order

```python
msg = PulseMessage(
    action="ACT.TRANSACT.REQUEST",
    parameters={
        "symbol": "ETHUSDT",
        "side": "BUY",
        "quantity": 0.1,
        "order_type": "LIMIT",
        "price": 3000,
        "time_in_force": "GTC",
    }
)
response = adapter.send(msg)
```

### Get order book

```python
msg = PulseMessage(
    action="ACT.QUERY.DATA",
    parameters={"symbol": "BTCUSDT", "type": "depth", "limit": 10}
)
response = adapter.send(msg)
```

## Features

- **HMAC-SHA256 authentication** — Binance signing fully handled
- **Testnet support** — test with `BinanceAdapter(testnet=True)`
- **Standard pair format** — use `BTCUSDT`, `ETHUSDT`, etc.
- **Tiny footprint** — one file, ~10 KB

## Testing

```bash
pytest tests/ -q  # All tests mocked, no API key needed
```

## PULSE Ecosystem

| Package | Provider | Install |
|---|---|---|
| [pulse-protocol](https://pypi.org/project/pulse-protocol/) | Core | `pip install pulse-protocol` |
| **pulse-binance** | **Binance** | `pip install pulse-binance` |
| [pulse-bybit](https://pypi.org/project/pulse-bybit/) | Bybit | `pip install pulse-bybit` |
| [pulse-kraken](https://pypi.org/project/pulse-kraken/) | Kraken | `pip install pulse-kraken` |
| [pulse-okx](https://pypi.org/project/pulse-okx/) | OKX | `pip install pulse-okx` |
| [pulse-openai](https://pypi.org/project/pulse-openai/) | OpenAI | `pip install pulse-openai` |
| [pulse-anthropic](https://pypi.org/project/pulse-anthropic/) | Anthropic | `pip install pulse-anthropic` |
| [pulse-gateway](https://pypi.org/project/pulse-gateway/) | Gateway | `pip install pulse-gateway` |

## License

Apache 2.0 — open source, free forever.
