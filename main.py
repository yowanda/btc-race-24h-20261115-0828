#!/usr/bin/env python3
"""BTC race bot v4 — Elder Triple Screen: tide 720 min, wave 240 min, ripple 60 min.

Long only, one position, full size. The bot trades cbBTC (CBBTC) against
USDC on 1-minute bars, speaking agent-fun/bars-replay/v1 through the
vendored shim (vendor/makefun_bars.py, byte-identical to the race kit SDK).

Why three screens (see STRATEGY.md): on the previous race's dev window the
bot kept buying dead-cat bounces inside a downtrend. A 240-minute gate is
flippable by a single strong bounce hour, and a Donchian breakout fires at
the top of that bounce — so every round trip bled about one round-trip
cost. Elder's Triple Screen fixes this structurally: screen one is a
strict filter with no exceptions. A long is only considered when the
day-scale tide itself is up; the wave must agree; only then does the
1-hour breakout trigger an entry.

  Screen 1 — TIDE (12 h): 720-min return > 0 AND close above EMA(720).
    A bounce can only flip a 12-hour return positive by retracing the
    whole 12-hour drop, i.e. a genuine reversal, not a bounce. On the
    -4.91% dev window this gate was open 0/720 bars.
  Screen 2 — WAVE (4 h): 240-min return > 0 AND close above EMA(240).
    The medium-term trend must be up; a 1-hour bounce cannot flip it.
  Screen 3 — RIPPLE (1 h): close breaks above the highest close of the
    last 60 bars (Donchian breakout). Fires at the start of a leg.

  Exit — TRAILING STOP: sell when the close falls 0.3% below the highest
    close since entry (about one round-trip cost, ~26 bps).
  Exit — TREND-BREAK BACKSTOP: sell if the close falls below EMA(240).
    The 4-hour trend that justified the entry is gone, so the premise is
    gone. Covers slow rollovers where price drifts under the trend
    without a sharp pullback from the peak.

Known trade-off, stated up front: the tide needs 720 bars of history,
so the bot cannot trade the first 12 hours of a 24-hour window. That is
the price of the filter. Trends persist, so the second half of a genuine
uptrend day still has up-moves to catch, and the bot only needs ONE good
round trip to pass the dev gate. On a downtrend day the correct answer is
zero trades ($0, no bleed) rather than four losing bounces.

Pure function of bar closes, integer math only: deterministic, no clock,
no network, no randomness, no files.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# --- Parameters (research-chosen, see STRATEGY.md; not fitted to any window)
TIDE_BARS = 720          # screen 1 lookback: 12 h
TIDE_EMA_SPAN = 720      # EMA span for the tide gate
WAVE_BARS = 240          # screen 2 lookback: 4 h
EMA_SPAN = 240           # EMA span for the wave filter / exit backstop
BREAKOUT_BARS = 60       # screen 3: 1-hour Donchian high, in minutes
TRAIL_BPS = 30           # trailing stop: 0.3% below the peak since entry
MAX_SLIPPAGE_BPS = 100   # 4x the expected ~26 bps cost; caps gap fills
BPS = 10_000
EMA_FP = 1_000_000       # fixed-point scale for the integer EMAs

SYMBOL = "CBBTC"

# --- State ------------------------------------------------------------------
closes = []             # closes (ints, price_scale 5), in batch order
ema_wave_fp = None      # EMA(240) in fixed point (price * EMA_FP)
ema_tide_fp = None      # EMA(720) in fixed point (price * EMA_FP)
entry_price = None      # fill price of the open position (int), or None
entry_seq = -1          # seq of the batch whose fills opened the position
peak_close = None       # highest close seen while holding (int), or None
buy_pending = False     # a buy order is decided but not yet filled/rejected


def ret_bps(now, then):
    """Return from `then` to `now` in basis points, integer math."""
    return (now - then) * BPS // then


def _ema_step(prev_fp, close, span):
    """One integer EMA step; alpha = 2 / (span + 1)."""
    if prev_fp is None:
        return close * EMA_FP
    return prev_fp + (close * EMA_FP - prev_fp) * 2 // (span + 1)


def on_batch(state, batch):
    global ema_wave_fp, ema_tide_fp, entry_price, entry_seq, peak_close, buy_pending

    # --- Settle last batch's orders first: fills arrive with this batch.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL:
            continue
        if fill.get("side") == "buy":
            buy_pending = False
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

    ema_wave_fp = _ema_step(ema_wave_fp, close, EMA_SPAN)
    ema_tide_fp = _ema_step(ema_tide_fp, close, TIDE_EMA_SPAN)

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
        # Trend-break backstop: close below EMA(240) — premise gone, exit.
        if close * EMA_FP < ema_wave_fp:
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # --- Entry: flat ---------------------------------------------------------
    # A full 720-bar tide window is required (it covers the 240-bar wave
    # and the 60-bar breakout windows too).
    if buy_pending or n <= TIDE_BARS:
        return []
    # Screen 1 (tide, 12 h): the day-scale trend itself must be up.
    tide_up = (ret_bps(close, closes[-TIDE_BARS - 1]) > 0
               and close * EMA_FP > ema_tide_fp)
    # Screen 2 (wave, 4 h): the medium-term trend must be up.
    wave_up = (ret_bps(close, closes[-WAVE_BARS - 1]) > 0
               and close * EMA_FP > ema_wave_fp)
    # Screen 3 (ripple, 1 h): breakout above the 1-hour high.
    breakout = close > max(closes[-BREAKOUT_BARS - 1:-1])
    if tide_up and wave_up and breakout:
        cash = state.cash
        if cash <= 0:
            return []
        buy_pending = True
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


# --- Entry point: the shim owns the wire (stdin JSON lines -> stdout replies).
makefun_bars.run(on_batch)
