from app.models import Candle, Profile
from app.strategy import ONE_HOUR_MS, StrategyState, detect_hvn_touch, rsi_divergence

PROFILE = Profile(poc=100.0, vah=105.0, val=95.0, hvns=(100.0,), row_size=0.5)


def hourly(count: int = 8) -> list[Candle]:
    return [
        Candle(index * ONE_HOUR_MS, 100.0, 101.0, 99.0, 100.0 + index, 10.0)
        for index in range(count)
    ]


def test_hvn_touch_from_above_is_bullish_support():
    candles = [
        Candle(0, 101.0, 102.0, 100.0, 101.0, 10.0),
        Candle(ONE_HOUR_MS, 101.0, 101.0, 99.5, 100.0, 10.0),
    ]

    assert detect_hvn_touch(candles, PROFILE) == (
        "alcista",
        "toque de HVN 100.00 desde arriba (posible soporte)",
    )


def test_hvn_touch_from_below_is_bearish_resistance():
    candles = [
        Candle(0, 99.0, 100.0, 98.0, 99.0, 10.0),
        Candle(ONE_HOUR_MS, 99.0, 100.5, 98.0, 99.5, 10.0),
    ]

    assert detect_hvn_touch(candles, PROFILE) == (
        "bajista",
        "toque de HVN 100.00 desde abajo (posible resistencia)",
    )


def test_rsi_divergence_requires_confirmed_latest_pivot(monkeypatch):
    prices = [96.0, 97.0, 98.0, 99.0, 100.0, 95.0]
    prices += [101.0 + (index - 6) for index in range(6, 28)]
    prices += [90.0, 95.0]

    def fake_rsi(values, period=14):
        if len(values) == 6:
            return 30.0
        if len(values) == 29:
            return 40.0
        return 50.0

    monkeypatch.setattr("app.strategy.rsi", fake_rsi)
    candles = [Candle(index * ONE_HOUR_MS, price, price, price, price, 1.0) for index, price in enumerate(prices)]

    assert rsi_divergence(candles) == "alcista"


def test_rsi_divergence_ignores_stale_pivot(monkeypatch):
    prices = [96.0, 97.0, 98.0, 99.0, 100.0, 95.0]
    prices += [101.0 + (index - 6) for index in range(6, 15)]
    prices += [90.0, 95.0]
    prices += [102.0 + (index - 17) for index in range(17, 30)]

    def fake_rsi(values, period=14):
        if len(values) == 6:
            return 30.0
        if len(values) == 16:
            return 40.0
        return 50.0

    monkeypatch.setattr("app.strategy.rsi", fake_rsi)
    candles = [Candle(index * ONE_HOUR_MS, price, price, price, price, 1.0) for index, price in enumerate(prices)]

    assert rsi_divergence(candles) is None


def test_strategy_sends_partial_events_and_one_final_signal(monkeypatch):
    series = hourly(7)
    hvn_bar = series[1].timestamp
    divergence_bar = series[3].timestamp
    cross_bar = series[5].timestamp

    def fake_hvn_touch(candles, profile):
        if candles[-1].timestamp == hvn_bar:
            return "alcista", "toque de HVN 100.00 desde arriba (posible soporte)"
        return None

    def fake_divergence(candles, period=14, lookback=40):
        return "alcista" if candles[-1].timestamp == divergence_bar else None

    def fake_cross(candles, period):
        return ("alcista", 123.45) if candles[-1].timestamp == cross_bar else None

    monkeypatch.setattr("app.strategy.detect_hvn_touch", fake_hvn_touch)
    monkeypatch.setattr("app.strategy.rsi_divergence", fake_divergence)
    monkeypatch.setattr("app.strategy._ema_cross", fake_cross)

    state = StrategyState(period=14, ema_period=15, context_window=16)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]
    events = [event for update in updates for event in update.events]
    signals = [update.signal for update in updates if update.signal is not None]

    assert [(event.kind, event.direction) for event in events] == [
        ("hvn_touch", "alcista"),
        ("rsi_divergence", "alcista"),
    ]
    assert len(signals) == 1
    signal = signals[0]
    assert signal.direction == "COMPRA"
    assert signal.timeframe == "1h"
    assert signal.divergence == "alcista"
    assert "toque de HVN" in signal.reason
    assert signal.ema == 123.45
    assert signal.timestamp == cross_bar + ONE_HOUR_MS


def test_strategy_requires_hvn_context(monkeypatch):
    series = hourly(6)
    divergence_bar = series[1].timestamp
    cross_bar = series[3].timestamp

    monkeypatch.setattr("app.strategy.detect_hvn_touch", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.strategy.rsi_divergence",
        lambda candles, period=14, lookback=40: "alcista" if candles[-1].timestamp == divergence_bar else None,
    )
    monkeypatch.setattr(
        "app.strategy._ema_cross",
        lambda candles, period: ("alcista", 123.45) if candles[-1].timestamp == cross_bar else None,
    )

    state = StrategyState(period=14, ema_period=15, context_window=16)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]

    assert all(update.signal is None for update in updates)


def test_strategy_requires_ema_cross(monkeypatch):
    series = hourly(6)
    hvn_bar = series[1].timestamp
    divergence_bar = series[2].timestamp

    monkeypatch.setattr(
        "app.strategy.detect_hvn_touch",
        lambda candles, profile: (
            ("alcista", "toque de HVN 100.00 desde arriba (posible soporte)")
            if candles[-1].timestamp == hvn_bar
            else None
        ),
    )
    monkeypatch.setattr(
        "app.strategy.rsi_divergence",
        lambda candles, period=14, lookback=40: "alcista" if candles[-1].timestamp == divergence_bar else None,
    )
    monkeypatch.setattr("app.strategy._ema_cross", lambda *args, **kwargs: None)

    state = StrategyState(period=14, ema_period=15, context_window=16)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]

    assert all(update.signal is None for update in updates)


def test_strategy_does_not_pair_opposite_directions(monkeypatch):
    series = hourly(6)
    hvn_bar = series[1].timestamp
    divergence_bar = series[2].timestamp
    cross_bar = series[4].timestamp

    def fake_hvn_touch(candles, profile):
        if candles[-1].timestamp == hvn_bar:
            return "alcista", "toque de HVN 100.00 desde arriba (posible soporte)"
        return None

    def fake_divergence(candles, period=14, lookback=40):
        return "bajista" if candles[-1].timestamp == divergence_bar else None

    def fake_cross(candles, period):
        return ("alcista", 123.45) if candles[-1].timestamp == cross_bar else None

    monkeypatch.setattr("app.strategy.detect_hvn_touch", fake_hvn_touch)
    monkeypatch.setattr("app.strategy.rsi_divergence", fake_divergence)
    monkeypatch.setattr("app.strategy._ema_cross", fake_cross)

    state = StrategyState(period=14, ema_period=15, context_window=16)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]

    assert all(update.signal is None for update in updates)


def test_strategy_expires_context_after_configured_window(monkeypatch):
    series = hourly(7)
    hvn_bar = series[1].timestamp
    divergence_bar = series[4].timestamp
    cross_bar = series[5].timestamp

    def fake_hvn_touch(candles, profile):
        if candles[-1].timestamp == hvn_bar:
            return "alcista", "toque de HVN 100.00 desde arriba (posible soporte)"
        return None

    def fake_divergence(candles, period=14, lookback=40):
        return "alcista" if candles[-1].timestamp == divergence_bar else None

    def fake_cross(candles, period):
        return ("alcista", 123.45) if candles[-1].timestamp == cross_bar else None

    monkeypatch.setattr("app.strategy.detect_hvn_touch", fake_hvn_touch)
    monkeypatch.setattr("app.strategy.rsi_divergence", fake_divergence)
    monkeypatch.setattr("app.strategy._ema_cross", fake_cross)

    state = StrategyState(period=14, ema_period=15, context_window=2)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]

    assert all(update.signal is None for update in updates)


def test_strategy_does_not_reuse_the_same_context(monkeypatch):
    series = hourly(8)
    hvn_bar = series[1].timestamp
    divergence_bar = series[3].timestamp
    first_cross = series[5].timestamp

    def fake_hvn_touch(candles, profile):
        if candles[-1].timestamp == hvn_bar:
            return "alcista", "toque de HVN 100.00 desde arriba (posible soporte)"
        return None

    def fake_divergence(candles, period=14, lookback=40):
        return "alcista" if candles[-1].timestamp == divergence_bar else None

    def fake_cross(candles, period):
        if candles[-1].timestamp in {first_cross, series[6].timestamp}:
            return "alcista", 123.45
        return None

    monkeypatch.setattr("app.strategy.detect_hvn_touch", fake_hvn_touch)
    monkeypatch.setattr("app.strategy.rsi_divergence", fake_divergence)
    monkeypatch.setattr("app.strategy._ema_cross", fake_cross)

    state = StrategyState(period=14, ema_period=15, context_window=16)
    updates = [state.update(series[:end], PROFILE) for end in range(2, len(series) + 1)]

    assert updates[-3].signal is not None
    assert updates[-2].signal is None
    assert updates[-1].signal is None


def test_strategy_ignores_repeated_or_older_closed_candles(monkeypatch):
    series = hourly(4)
    calls = {"count": 0}

    def fake_cross(candles, period):
        calls["count"] += 1
        return None

    monkeypatch.setattr("app.strategy._ema_cross", fake_cross)
    state = StrategyState(period=14, ema_period=15, context_window=16)

    state.update(series[:2], PROFILE)
    state.update(series[:2], PROFILE)

    assert calls["count"] == 1


def test_strategy_reset_discards_pending_context(monkeypatch):
    series = hourly(6)

    def fake_hvn_touch(candles, profile):
        return "alcista", "toque de HVN 100.00 desde arriba (posible soporte)"

    monkeypatch.setattr("app.strategy.detect_hvn_touch", fake_hvn_touch)
    monkeypatch.setattr("app.strategy.rsi_divergence", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.strategy._ema_cross", lambda *args, **kwargs: None)

    state = StrategyState(period=14, ema_period=15, context_window=16)
    state.update(series[:2], PROFILE)
    state.reset()

    assert state._pending_hvn == []
    assert state._pending_divergences == []
