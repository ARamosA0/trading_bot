from app.candles import aggregate_candles
from app.market import FOUR_HOURS_MS, _closed
from app.models import Candle


def test_aggregate_four_hour_candle_from_240_minutes():
    minutes = [
        Candle(
            timestamp=index * 60_000,
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100.5 + index,
            volume=2,
        )
        for index in range(240)
    ]

    candle = aggregate_candles(minutes)

    assert candle.timestamp == minutes[0].timestamp
    assert candle.open == minutes[0].open
    assert candle.high == minutes[-1].high
    assert candle.low == minutes[0].low
    assert candle.close == minutes[-1].close
    assert candle.volume == 480


def test_history_filters_closed_four_hour_candles_from_start(monkeypatch):
    monkeypatch.setattr("app.market._now_ms", lambda: 12 * FOUR_HOURS_MS)
    history = [
        Candle(timestamp, 100, 110, 90, 105, 1)
        for timestamp in (0, 4 * FOUR_HOURS_MS, 8 * FOUR_HOURS_MS, 12 * FOUR_HOURS_MS)
    ]

    closed = _closed(history, FOUR_HOURS_MS, start_ms=3 * FOUR_HOURS_MS)

    assert [candle.timestamp for candle in closed] == [
        4 * FOUR_HOURS_MS,
        8 * FOUR_HOURS_MS,
    ]
