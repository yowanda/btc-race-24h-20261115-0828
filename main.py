#!/usr/bin/env python3
"""BTC race bot v3 — Donchian breakout + trailing exit + strong regime gate.

Long only, one position, full size. Strategy (see STRATEGY.md):

  - Regime gate (higher timeframe, ~4 h) -- the v3 addition: only consider
    longs when the 240-min return is positive AND the price is above
    EMA(240). This is the structural fix for the v1/v2 failure mode
    (buying bounces inside a downtrend): the v2 120-min filter kept
    passing on local 2-hour bounces while the day trend was down, and
    the Donchian breakouts then whipsawed 6x for -$29.55. A 4-hour
    trend gate (2x the 120-min filter, 4x the 60-min breakout window --
    Elder Triple Screen spacing) only lets the bot in when the
    medium-term trend itself has turned up. If the window is a
    downtrend, the bot stays in cash: $0, no bleed.
  - Trend filter (higher TF, ~2 h, unchanged from v2): 120-min return
    positive AND price above EMA(120).
  - Entry (breakout, unchanged from v2): close breaks above the
    highest close of the last 60 bars (1-hour Donchian high).
  - Exit (trailing stop, unchanged from v2): sell when the close falls
    0.3% below the highest close since entry (~the round-trip cost).

Pure function of bar closes, integer math only: deterministic, no clock,
no network, no randomness, no files. Speaks agent-fun/bars-replay/v1 via
the vendored shim (vendor/makefun_bars.py, byte-identical to the kit SDK).

Port note: this file is the v3 port for race btc-race-24h-20261115-0828.
It replaces the v4 port in this repo for the v3 gate check (v4 gate on
this race's dev window: PnL $0.00, 0 trades — failed). Parameters are
research-set from STRATEGY.md, unchanged from the v3 reference; nothing
was tuned against this race's dev window.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# --- Parameters (research-chosen; see STRATEGY.md) ---------------------------
REGIME_BARS = 240       # regime-gate lookback: 4 h (2x the trend filter)
REGIME_EMA_SPAN = 240   # EMA span for the regime gate
TREND_BARS = 120        # higher-timeframe trend lookback (minutes)
BREAKOUT_BARS = 60      # Donchian breakout lookback: 1-hour high (minutes)
TRAIL_BPS = 30          # trailing stop: 0.3% below the peak since entry
EMA_SPAN = 120          # EMA span for the trend filter
MAX_SLIPPAGE_BPS = 100  # 4x the expected ~26 bps cost; caps gap fills
BPS = 10_000
EMA_FP = 1_000_000      # fixed-point scale for the integer EMA

SYMBOL = "CBBTC"

# --- State ------------------------------------------------------------------
closes = []             # close prices (ints, price_scale 5), in batch order
ema_fp = None           # EMA(120) in fixed point (price * EMA_FP)
ema_regime_fp = None    # EMA(240) in fixed point (price * EMA_FP)
entry_price = None      # fill price of the open position (int), or None
entry_seq = -1          # seq of the batch whose fills opened the position
peak_close = None       # highest close seen while holding (int), or None
pending_buy = False     # a buy order is decided but not yet filled/rejected


def ret_bps(now, then):
    """Return from `then` to `now` in basis points (integer math)."""
    return (now - then) * BPS // then


def on_batch(state, batch):
    global ema_fp, ema_regime_fp, entry_price, entry_seq, peak_close, pending_buy

    # --- Fold in this batch's fills first: they settle last batch's orders.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL:
            continue
        if fill.get("side") == "buy":
            pending_buy = False
            if fill.get("status") == "filled":
                entry_price = int(fill["price"])
                entry_seq = state.seq
                peak_close = None
        elif fill.get("side") == "sell" and fill.get("status") == "filled":
            entry_price = None
            entry_seq = -1
            peak_close = None

    bar = state.latest.get(SYMBOL)
    if bar is None or state.warming_up:
        return []
    close = int(bar["c"])
    closes.append(close)

    # Integer EMAs: seeded on the first close, alpha = 2 / (span + 1).
    if ema_fp is None:
        ema_fp = close * EMA_FP
    else:
        ema_fp += (close * EMA_FP - ema_fp) * 2 // (EMA_SPAN + 1)
    if ema_regime_fp is None:
        ema_regime_fp = close * EMA_FP
    else:
        ema_regime_fp += (close * EMA_FP - ema_regime_fp) * 2 // (REGIME_EMA_SPAN + 1)

    held = state.positions.get(SYMBOL)
    n = len(closes)

    # --- Exit: holding a position -------------------------------------------
    if held is not None and held.qty > 0:
        if peak_close is None or close > peak_close:
            peak_close = close
        # Trailing stop: 0.3% below the highest close since entry.
        if peak_close is not None and close * BPS < peak_close * (BPS - TRAIL_BPS):
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- Entry: flat ---------------------------------------------------------
    # Need a full 240-bar regime window (covers the 120-bar trend and
    # 60-bar breakout windows too).
    if pending_buy or n <= REGIME_BARS:
        return []
    ret_trend = ret_bps(close, closes[-TREND_BARS - 1])
    above_ema = close * EMA_FP > ema_fp
    # Regime gate (v3): 4-hour trend must itself be up.
    ret_regime = ret_bps(close, closes[-REGIME_BARS - 1])
    above_regime_ema = close * EMA_FP > ema_regime_fp
    breakout = close > max(closes[-BREAKOUT_BARS - 1:-1])
    if (ret_regime > 0 and above_regime_ema
            and ret_trend > 0 and above_ema and breakout):
        cash = state.cash
        if cash <= 0:
            return []
        pending_buy = True
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)
