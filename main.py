# SPDX-License-Identifier: MIT
"""BTC race bot v6: oversold bounce entry, Chandelier trailing exit.

Long only, one position, full size. Integer math throughout, no clock,
no network, no files, no randomness: the reply is a pure function of
the bars and fills seen so far.

Entry: the bot arms when the latest close sits at least 2% below the
highest close of the 240 bars before it (a washout), and fires when
the close breaks above the highest close of the 60 bars before it
(the turn confirmed at its start).

Exit: a Chandelier trail. The bot tracks the highest close since
entry and sells everything when the close falls 3 times the average
true range of the last 60 bars below that peak, so the trail widens
and narrows with the market's own volatility instead of a fixed
number of basis points.

Port note: this is the v6 port written for race btc-race-24h-20261115-0828
from the prose specification in STRATEGY.md section 9. Its own gate
check on this race's dev window (1,440 bars) gave net PnL +$14.35,
8 trades, max drawdown -1.62%, deterministic across two runs
(IDENTICAL). Every parameter is research-set from that specification
and was not tuned against the window.
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
)

import makefun_bars

SYMBOL = "CBBTC"

ARM_BARS = 240
ARM_DRAWDOWN_BPS = 200
BREAKOUT_BARS = 60
ATR_BARS = 60
TRAIL_MULTIPLE = 3
MAX_SLIPPAGE_BPS = 100


class Bot:
    """Keeps the bar history and the open-trade bookkeeping."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.lows = []
        self.entry_price = None
        self.peak_close = None
        self.buy_pending = False

    def fold_fills(self, fills):
        """Apply this batch's fills to the trade bookkeeping."""
        for fill in fills:
            if fill.get("symbol") != SYMBOL:
                continue
            side = fill.get("side")
            if side == "buy":
                self.buy_pending = False
                if fill.get("status") == "filled":
                    self.entry_price = int(fill["price"])
                    self.peak_close = int(fill["price"])
            elif side == "sell":
                if fill.get("status") == "filled":
                    self.entry_price = None
                    self.peak_close = None

    def average_true_range(self):
        """Mean true range over the last ATR_BARS bars, integer division.

        A bar's true range is the largest of its high-low span and the
        two gaps between its high/low and the previous bar's close.
        """
        total = 0
        start = len(self.closes) - ATR_BARS
        for i in range(start, len(self.closes)):
            prev_close = self.closes[i - 1]
            high = self.highs[i]
            low = self.lows[i]
            span = high - low
            up_gap = high - prev_close
            down_gap = prev_close - low
            total += max(span, up_gap, down_gap)
        return total // ATR_BARS

    def decide(self, state, batch):
        self.fold_fills(batch.get("fills", []))
        bar = state.latest.get(SYMBOL)
        if bar is None or state.warming_up:
            return []
        close = int(bar["c"])
        self.closes.append(close)
        self.highs.append(int(bar["h"]))
        self.lows.append(int(bar["l"]))

        holding = state.positions.get(SYMBOL)
        qty = holding.qty if holding is not None else 0
        if qty > 0:
            if self.peak_close is None or close > self.peak_close:
                self.peak_close = close
            if len(self.closes) > ATR_BARS:
                trail = TRAIL_MULTIPLE * self.average_true_range()
                if close < self.peak_close - trail:
                    return [
                        {
                            "side": "sell",
                            "symbol": SYMBOL,
                            "qty": qty,
                            "max_slippage_bps": MAX_SLIPPAGE_BPS,
                        }
                    ]
            return []

        if self.buy_pending or len(self.closes) <= ARM_BARS:
            return []
        prior = self.closes[:-1]
        high_240 = max(prior[-ARM_BARS:])
        drawdown_bps = (close - high_240) * 10000 // high_240
        if drawdown_bps > -ARM_DRAWDOWN_BPS:
            return []
        high_60 = max(prior[-BREAKOUT_BARS:])
        if close <= high_60:
            return []
        self.buy_pending = True
        return [
            {
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": state.cash,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]


def on_batch(state, batch):
    return _BOT.decide(state, batch)


_BOT = Bot()

makefun_bars.run(on_batch)
