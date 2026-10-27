import time

from .indicators import ema, rsi
from .models import Candle, Profile, Signal


def _pivots(values: list[float]) -> tuple[list[int], list[int]]:
    lows = [i for i in range(1, len(values) - 1) if values[i] <= values[i - 1] and values[i] <= values[i + 1]]
    highs = [i for i in range(1, len(values) - 1) if values[i] >= values[i - 1] and values[i] >= values[i + 1]]
    return lows, highs


def rsi_divergence(candles: list[Candle], period: int = 14, lookback: int = 40) -> str | None:
    prices = [candle.close for candle in candles[-lookback:]]
    if len(prices) < period + 8:
        return None
    rsi_values = [rsi(prices[: i + 1], period) for i in range(len(prices))]
    lows, highs = _pivots(prices)
    valid_lows = [i for i in lows if rsi_values[i] is not None]
    valid_highs = [i for i in highs if rsi_values[i] is not None]
    if len(valid_lows) >= 2:
        first, second = valid_lows[-2:]
        if prices[second] < prices[first] and rsi_values[second] > rsi_values[first]:
            return "alcista"
    if len(valid_highs) >= 2:
        first, second = valid_highs[-2:]
        if prices[second] > prices[first] and rsi_values[second] < rsi_values[first]:
            return "bajista"
    return None


def _market_context(candles: list[Candle], profile: Profile) -> tuple[str, str] | None:
    if len(candles) < 2:
        return None
    # Keep the context alive while divergence and the 1h confirmation form.
    for index in range(len(candles) - 1, max(0, len(candles) - 17), -1):
        previous, current = candles[index - 1], candles[index]
        tolerance = max(profile.row_size, current.close * 0.0002)
        for hvn in profile.hvns:
            if previous.close >= hvn and current.low <= hvn + tolerance:
                return "bullish", f"toque de HVN {hvn:,.2f} desde arriba (soporte)"
            if previous.close <= hvn and current.high >= hvn - tolerance:
                return "bearish", f"toque de HVN {hvn:,.2f} desde abajo (resistencia)"
        if previous.close < profile.val <= current.close:
            return "bullish", "cruce alcista de VAL"
        if previous.close > profile.vah >= current.close:
            return "bearish", "cruce bajista de VAH"
    return None


def evaluate(candles_15m: list[Candle], candles_1h: list[Candle], profile: Profile, period: int = 14, ema_period: int = 15) -> Signal | None:
    """Confirm context + RSI divergence + closed 1h EMA cross."""
    if len(candles_15m) < period + 10 or len(candles_1h) < ema_period + 2:
        return None
    context = _market_context(candles_15m, profile)
    divergence = rsi_divergence(candles_15m, period)
    closes = [candle.close for candle in candles_1h]
    ema_values = ema(closes, ema_period)
    previous_close, current_close = closes[-2:]
    previous_ema, current_ema = ema_values[-2:]
    bullish_cross = previous_close <= previous_ema and current_close > current_ema
    bearish_cross = previous_close >= previous_ema and current_close < current_ema
    if context is None or divergence is None:
        return None
    direction, reason = context
    if direction == "bullish" and divergence == "alcista" and bullish_cross:
        return Signal("COMPRA", "1h", current_close, rsi([c.close for c in candles_15m], period) or 0, profile, reason, int(time.time() * 1000), current_ema, divergence, reason)
    if direction == "bearish" and divergence == "bajista" and bearish_cross:
        return Signal("VENTA", "1h", current_close, rsi([c.close for c in candles_15m], period) or 0, profile, reason, int(time.time() * 1000), current_ema, divergence, reason)
    return None
