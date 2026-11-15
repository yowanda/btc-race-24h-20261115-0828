# BTC race bot v1 — multi-timeframe trend-following with momentum trigger (make.fun `btc-race-24h-20261115-0828`)

Long-only cbBTC (CBBTC) trading bot for the make.fun 24-hour BTC race.
Python standard library only; speaks `agent-fun/bars-replay/v1` via the
vendored shim in `vendor/makefun_bars.py` (byte-identical to the race kit SDK).
Deterministic: pure function of bar closes, integer math, no clock, no
network, no randomness.

## Strategy — multi-timeframe trend-following with momentum trigger

| Rule | Detail |
|---|---|
| Trend filter, 2 h | 120-min return > 0 **and** close above EMA(120) |
| Entry trigger, 30 min | 30-min return > +0.3% (30 bps) |
| Minimum hold | 180 bars (3 h), anti-churn |
| Exit | Take-profit +0.6% from fill, or trend break after min hold (close below EMA(120) or 30-min return < −0.2%) |

A long is only taken when the trend filter and the momentum trigger
agree. The 30-min trigger only fires on a confirmed leg, not on 1-min
noise, and the minimum hold forbids exiting on noise for 3 hours.

**Note:** this repo previously held the v4 port (Elder Triple Screen
720/240/60) and then the v3 port (Donchian breakout + trailing exit +
240-min regime gate). v4's gate check on this race's dev window failed
with PnL $0.00 and 0 trades; v3's gate check failed with PnL −$6.34,
6 trades, maxDD −1.25%. `main.py` was rewritten as v1 for the v1 gate
check. The v4 and v3 ports are preserved in the git history (commits
20a6bc5 and 66a1483).

## How to run

The race harness drives the bot: it reads one JSON line per batch from
stdin and the bot replies with one JSON line of orders per batch. Locally:

```sh
python3 main.py < bars.ndjson
```

## Files

- `main.py` — the bot (v1, multi-timeframe trend-following with momentum trigger)
- `vendor/makefun_bars.py` — protocol shim, byte-identical to the kit SDK
- `.makefun/owner.json` — entry owner wallet
- `LICENSE` — MIT
