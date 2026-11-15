# BTC race bot v3 — Donchian breakout + trailing exit + 240-min regime gate (make.fun `btc-race-24h-20261115-0828`)

Long-only cbBTC (CBBTC) trading bot for the make.fun 24-hour BTC race.
Python standard library only; speaks `agent-fun/bars-replay/v1` via the
vendored shim in `vendor/makefun_bars.py` (byte-identical to the race kit SDK).
Deterministic: pure function of bar closes, integer math, no clock, no
network, no randomness.

## Strategy — Donchian breakout + trailing exit + regime gate

| Rule | Detail |
|---|---|
| Regime gate, 4 h | 240-min return > 0 **and** close above EMA(240) |
| Trend filter, 2 h | 120-min return > 0 **and** close above EMA(120) |
| Entry, 1 h | Close breaks above the highest close of the last 60 bars |

A long is only taken when the regime gate, the trend filter, and the
breakout agree. The 4-hour gate is the v3 addition: the 120-min filter
kept passing on local 2-hour bounces inside a downtrend, so the bot
only enters when the medium-term trend itself has turned up.

**Exit:** trailing stop 0.3% below the highest close since entry (about
one round-trip cost). Full size (100% of cash), one position, max
slippage 100 bps.

**Note:** this repo previously held the v4 port (Elder Triple Screen
720/240/60). v4's gate check on this race's dev window failed with
PnL $0.00 and 0 trades, so `main.py` was rewritten as v3 for the v3
gate check. The v4 port is preserved in the git history (commit
20a6bc5).

## How to run

The race harness drives the bot: it reads one JSON line per batch from
stdin and the bot replies with one JSON line of orders per batch. Locally:

```sh
python3 main.py < bars.ndjson
```

## Files

- `main.py` — the bot (v3, Donchian breakout + trailing exit + 240-min regime gate)
- `vendor/makefun_bars.py` — protocol shim, byte-identical to the kit SDK
- `.makefun/owner.json` — entry owner wallet
- `LICENSE` — MIT
