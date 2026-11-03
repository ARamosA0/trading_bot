from dataclasses import dataclass

from .indicators import ema, rsi
from .models import Candle, MarketEvent, Profile, Signal

ONE_HOUR_MS = 60 * 60 * 1000


def _pivots(values: list[float]) -> tuple[list[int], list[int]]:
    lows = [i for i in range(1, len(values) - 1) if values[i] <= values[i - 1] and values[i] <= values[i + 1]]
    highs = [i for i in range(1, len(values) - 1) if values[i] >= values[i - 1] and values[i] >= values[i + 1]]
    return lows, highs


def rsi_divergence(candles: list[Candle], period: int = 14, lookback: int = 40) -> str | None:
    """Return a divergence only when its second pivot is confirmed by the latest closed 1h candle."""
    prices = [candle.close for candle in candles[-lookback:]]
    if len(prices) < period + 8:
        return None
    rsi_values = [rsi(prices[: i + 1], period) for i in range(len(prices))]
    lows, highs = _pivots(prices)
    confirmed_pivot = len(prices) - 2
    valid_lows = [i for i in lows if rsi_values[i] is not None]
    valid_highs = [i for i in highs if rsi_values[i] is not None]
    if len(valid_lows) >= 2:
        first, second = valid_lows[-2:]
        if second == confirmed_pivot and prices[second] < prices[first] and rsi_values[second] > rsi_values[first]:
            return "alcista"
    if len(valid_highs) >= 2:
        first, second = valid_highs[-2:]
        if second == confirmed_pivot and prices[second] > prices[first] and rsi_values[second] < rsi_values[first]:
            return "bajista"
    return None


def detect_hvn_touch(candles: list[Candle], profile: Profile) -> tuple[str, str] | None:
    """Detect a new touch on the latest closed 1h candle and report its approach direction."""
    if len(candles) < 2 or candles[-1].timestamp - candles[-2].timestamp != ONE_HOUR_MS:
        return None
    previous, current = candles[-2], candles[-1]
    tolerance = max(profile.row_size, current.close * 0.0002)
    for hvn in profile.hvns:
        if previous.close >= hvn and current.low <= hvn + tolerance:
            return "alcista", f"toque de HVN {hvn:,.2f} desde arriba (posible soporte)"
        if previous.close <= hvn and current.high >= hvn - tolerance:
            return "bajista", f"toque de HVN {hvn:,.2f} desde abajo (posible resistencia)"
    return None


def _ema_cross(candles: list[Candle], period: int) -> tuple[str, float] | None:
    if len(candles) < period + 2:
        return None
    closes = [candle.close for candle in candles]
    values = ema(closes, period)
    previous_close, current_close = closes[-2:]
    previous_ema, current_ema = values[-2:]
    if previous_close <= previous_ema and current_close > current_ema:
        return "alcista", current_ema
    if previous_close >= previous_ema and current_close < current_ema:
        return "bajista", current_ema
    return None


@dataclass(frozen=True)
class StrategyUpdate:
    events: tuple[MarketEvent, ...] = ()
    signal: Signal | None = None


@dataclass(frozen=True)
class _PendingEvent:
    direction: str
    reason: str
    bar_index: int


class StrategyState:
    """Track 1h HVN/divergence events and emit one final alert after the EMA confirmation."""

    def __init__(self, period: int = 14, ema_period: int = 15, context_window: int = 16):
        self.period = period
        self.ema_period = ema_period
        self.context_window = context_window
        self._last_bar_timestamp: int | None = None
        self._bar_index = -1
        self._pending_hvn: list[_PendingEvent] = []
        self._pending_divergences: list[_PendingEvent] = []

    def reset(self) -> None:
        """Discard pending contexts after the profile is replaced."""
        self._last_bar_timestamp = None
        self._bar_index = -1
        self._pending_hvn.clear()
        self._pending_divergences.clear()

    def update(self, candles_1h: list[Candle], profile: Profile) -> StrategyUpdate:
        if len(candles_1h) < 2:
            return StrategyUpdate()
        current = candles_1h[-1]
        if self._last_bar_timestamp is not None and current.timestamp <= self._last_bar_timestamp:
            return StrategyUpdate()

        if (
            self._last_bar_timestamp is not None
            and current.timestamp - self._last_bar_timestamp != ONE_HOUR_MS
        ):
            self._pending_hvn.clear()
            self._pending_divergences.clear()
        self._last_bar_timestamp = current.timestamp
        self._bar_index += 1

        self._pending_hvn = [
            event for event in self._pending_hvn
            if self._bar_index - event.bar_index <= self.context_window
        ]
        self._pending_divergences = [
            event for event in self._pending_divergences
            if self._bar_index - event.bar_index <= self.context_window
        ]

        # Use only the continuous tail so gaps never become implicit signal data.
        continuous = [candles_1h[-1]]
        for candle in reversed(candles_1h[:-1]):
            if continuous[0].timestamp - candle.timestamp != ONE_HOUR_MS:
                break
            continuous.insert(0, candle)

        current_rsi = rsi([candle.close for candle in continuous], self.period)
        events: list[MarketEvent] = []
        close_timestamp = current.timestamp + ONE_HOUR_MS

        hvn_touch = detect_hvn_touch(continuous, profile)
        if hvn_touch:
            direction, reason = hvn_touch
            self._pending_hvn.append(_PendingEvent(direction, reason, self._bar_index))
            events.append(MarketEvent("hvn_touch", direction, "1h", current.close, current_rsi, profile, reason, close_timestamp))

        divergence = rsi_divergence(continuous, self.period)
        if divergence:
            reason = f"Divergencia RSI {divergence} confirmada en 1h"
            self._pending_divergences.append(_PendingEvent(divergence, reason, self._bar_index))
            events.append(MarketEvent("rsi_divergence", divergence, "1h", current.close, current_rsi, profile, reason, close_timestamp))

        signal = None
        cross = _ema_cross(continuous, self.ema_period)
        if cross:
            cross_direction, current_ema = cross
            matching_pairs = [
                (hvn, divergence_event)
                for hvn in self._pending_hvn
                for divergence_event in self._pending_divergences
                if hvn.direction == divergence_event.direction == cross_direction
                and abs(hvn.bar_index - divergence_event.bar_index) <= self.context_window
            ]
            if matching_pairs:
                hvn, divergence_event = max(
                    matching_pairs,
                    key=lambda pair: max(pair[0].bar_index, pair[1].bar_index),
                )
                direction_text = "COMPRA" if cross_direction == "alcista" else "VENTA"
                reason = f"{hvn.reason}; {divergence_event.reason}; cruce EMA({self.ema_period}) 1h"
                signal = Signal(
                    direction=direction_text,
                    timeframe="1h",
                    price=current.close,
                    rsi=current_rsi or 0.0,
                    profile=profile,
                    reason=reason,
                    timestamp=close_timestamp,
                    ema=current_ema,
                    divergence=divergence_event.direction,
                    context=hvn.reason,
                )
                # Consume matching-direction context so the same events cannot confirm twice.
                self._pending_hvn = [event for event in self._pending_hvn if event.direction != cross_direction]
                self._pending_divergences = [
                    event for event in self._pending_divergences if event.direction != cross_direction
                ]

        return StrategyUpdate(tuple(events), signal)
