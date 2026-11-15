# BTC race bot v4 — Elder Triple Screen (make.fun `btc-race-24h-20261115-0828`)

Long-only cbBTC (CBBTC) trading bot for the make.fun 24-hour BTC race.
Python standard library only; speaks `agent-fun/bars-replay/v1` via the
vendored shim in `vendor/makefun_bars.py` (byte-identical to the race kit SDK).
Deterministic: pure function of bar closes, integer math, no clock, no
network, no randomness.

## Strategy — Elder Triple Screen (720 / 240 / 60)

| Screen | Rule |
|---|---|
| 1 — Tide, 12 h | 720-min return > 0 **and** close above EMA(720) |
| 2 — Wave, 4 h | 240-min return > 0 **and** close above EMA(240) |
| 3 — Ripple, 1 h | Close breaks above the highest close of the last 60 bars |

A long is only taken when all three screens agree. The tide is a strict
filter with no exceptions: a bounce cannot flip a 12-hour return positive
unless it retraces the whole 12-hour drop, so the bot stands aside on
downtrend days instead of buying every dead-cat bounce.

**Exit:** trailing stop 0.3% below the highest close since entry, plus a
trend-break backstop (sell if the close falls below EMA(240) — the premise
is gone). Full size (100% of cash), one position, max slippage 100 bps.

**Trade-off:** the tide needs 720 bars of history, so the bot cannot trade
the first 12 hours of a 24-hour window. On a downtrend day the correct
answer is zero trades ($0, no bleed).

## How to run

The race harness drives the bot: it reads one JSON line per batch from
stdin and the bot replies with one JSON line of orders per batch. Locally:

```sh
python3 main.py < bars.ndjson
```

## Files

- `main.py` — the bot (v4, Elder Triple Screen 720)
- `vendor/makefun_bars.py` — protocol shim, byte-identical to the kit SDK
- `.makefun/owner.json` — entry owner wallet
- `LICENSE` — MIT
