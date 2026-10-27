from .models import Candle


def aggregate_candles(candles: list[Candle]) -> Candle:
    if not candles:
        raise ValueError("Se necesita al menos una vela para agregar")
    return Candle(
        timestamp=candles[0].timestamp,
        open=candles[0].open,
        high=max(candle.high for candle in candles),
        low=min(candle.low for candle in candles),
        close=candles[-1].close,
        volume=sum(candle.volume for candle in candles),
    )
