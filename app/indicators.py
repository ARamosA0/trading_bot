from .models import Candle, Profile


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def ema(values: list[float], period: int = 15) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def volume_profile(candles: list[Candle], rows: int = 500, value_area_percent: float = 70.0, hvn_count: int = 5) -> Profile | None:
    """Build a fixed-row profile from the selected closed 1h history."""
    if not candles or rows < 2 or not 0 < value_area_percent <= 100:
        return None
    low = min(candle.low for candle in candles)
    high = max(candle.high for candle in candles)
    if high <= low:
        return Profile(low, low, low, (low,), 0.0)
    row_size = (high - low) / rows
    volumes = [0.0] * rows
    for candle in candles:
        typical = (candle.high + candle.low + candle.close) / 3
        index = min(rows - 1, max(0, int((typical - low) / row_size)))
        volumes[index] += candle.volume

    poc_index = max(range(rows), key=volumes.__getitem__)
    target = sum(volumes) * value_area_percent / 100
    selected = {poc_index}
    while sum(volumes[index] for index in selected) < target and len(selected) < rows:
        candidates = [index for index in range(rows) if index not in selected]
        selected.add(max(candidates, key=volumes.__getitem__))
    hvn_indices = sorted(range(rows), key=volumes.__getitem__, reverse=True)[:max(1, hvn_count)]
    return Profile(
        poc=low + (poc_index + 0.5) * row_size,
        vah=low + (max(selected) + 1) * row_size,
        val=low + min(selected) * row_size,
        hvns=tuple(low + (index + 0.5) * row_size for index in hvn_indices),
        row_size=row_size,
    )
