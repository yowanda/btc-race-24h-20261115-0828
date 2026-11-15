#!/usr/bin/env python3
"""BTC race bot v1 — multi-timeframe trend-following with momentum trigger.

Long only, one position, full size. Strategy (see STRATEGY.md):

  - Trend filter (higher timeframe, ~2 h): 120-min return > 0 AND price
    above EMA(120). Elder's rule — never take a long against the higher
    timeframe.
  - Entry trigger (middle timeframe, 30 min): 30-min return > +0.3%
    (30 bps). A 30-min leg of 30 bps is already larger than the ~26 bps
    round-trip cost, so the move itself has paid for the trade.
  - Position: 100% of cash on entry (single position max, no leverage).
  - Minimum hold: 180 bars (3 h) — anti-churn; once in, the bot is
    forbidden from exiting on noise for 3 hours, so a real leg has time
    to develop.
  - Exit, whichever comes first:
      * Take-profit +0.6% from the fill price.
      * Trend break after the minimum hold: price below EMA(120), or
        30-min return < -0.2%. If the medium-term trend that justified
        the entry is gone, the premise is gone — exit, don't hope.

Pure function of bar closes, integer math only: deterministic, no clock,
no network, no randomness, no files. Speaks agent-fun/bars-replay/v1 via
the vendored shim (vendor/makefun_bars.py, byte-identical to the kit SDK).

Port note: this file is the v1 port for race btc-race-24h-20261115-0828.
It replaces the v3 port in this repo for the v1 gate check (v4 gate on
this race's dev window: PnL $0.00, 0 trades — failed; v3 gate: PnL
-$6.34, 6 trades, maxDD -1.25% — failed). Parameters are research-set
from STRATEGY.md, unchanged from the v1 reference; nothing was tuned
against this race's dev window.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# --- Parameters (research-set from STRATEGY.md, not fitted) ------------------
TREND_BARS = 120        # trend lookback: 2 h (4x the trigger timeframe)
TRIGGER_BARS = 30       # entry-trigger lookback: 30 min
TRIGGER_BPS = 30        # entry trigger: 30-min return > +0.3%
TP_BPS = 60             # take-profit: +0.6% from the fill price
EXIT_RET_BPS = -20      # trend-break exit: 30-min return < -0.2%
MIN_HOLD = 180          # minimum hold: 180 bars (3 h), anti-churn
EMA_SPAN = 120          # EMA span for the trend filter
MAX_SLIPPAGE_BPS = 100  # 4x the expected ~26 bps cost; caps gap fills
BPS = 10_000
EMA_FP = 1_000_000      # fixed-point scale for the integer EMA

SYMBOL = "CBBTC"

# --- State ------------------------------------------------------------------
closes = []             # close prices (ints, price_scale 5), in batch order
ema_fp = None           # EMA(120) in fixed point (price * EMA_FP)
entry_price = None      # fill price of the open position (int), or None
entry_seq = -1          # seq of the batch whose fills opened the position
pending_buy = False     # a buy order is decided but not yet filled/rejected


def ret_bps(now, then):
    """Return from `then` to `now` in basis points (integer math)."""
    return (now - then) * BPS // then


def on_batch(state, batch):
    global ema_fp, entry_price, entry_seq, pending_buy

    # --- Fold in this batch's fills first: they settle last batch's orders.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL:
            continue
        if fill.get("side") == "buy":
            pending_buy = False
            if fill.get("status") == "filled":
                entry_price = int(fill["price"])
                entry_seq = state.seq
        elif fill.get("side") == "sell" and fill.get("status") == "filled":
            entry_price = None
            entry_seq = -1

    bar = state.latest.get(SYMBOL)
    if bar is None or state.warming_up:
        return []
    close = int(bar["c"])
    closes.append(close)

    # Integer EMA: seeded on the first close, alpha = 2 / (span + 1).
    if ema_fp is None:
        ema_fp = close * EMA_FP
    else:
        ema_fp += (close * EMA_FP - ema_fp) * 2 // (EMA_SPAN + 1)

    held = state.positions.get(SYMBOL)
    n = len(closes)

    # --- Exit: holding a position -------------------------------------------
    if held is not None and held.qty > 0:
        if entry_price is not None:
            # Take-profit: +0.6% from the fill price.
            if close * BPS >= entry_price * (BPS + TP_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            # Trend break, only after the minimum hold: price below
            # EMA(120), or 30-min return < -0.2%.
            if state.seq - entry_seq >= MIN_HOLD and n > TRIGGER_BARS:
                if (close * EMA_FP < ema_fp
                        or ret_bps(close, closes[-TRIGGER_BARS - 1]) < EXIT_RET_BPS):
                    return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                             "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- Entry: flat ---------------------------------------------------------
    if pending_buy or n <= TREND_BARS:
        return []
    ret_trend = ret_bps(close, closes[-TREND_BARS - 1])
    ret_trig = ret_bps(close, closes[-TRIGGER_BARS - 1])
    above_ema = close * EMA_FP > ema_fp
    if ret_trend > 0 and ret_trig > TRIGGER_BPS and above_ema:
        cash = state.cash
        if cash <= 0:
            return []
        pending_buy = True
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
