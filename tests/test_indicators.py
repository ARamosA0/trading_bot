from app.indicators import rsi, volume_profile
from app.models import Candle


def candles(count: int = 40) -> list[Candle]:
    return [Candle(index * 60_000, 100 + index, 101 + index, 99 + index, 100 + index, 10) for index in range(count)]


def test_rsi_is_high_for_continuous_rise():
    assert rsi([float(index) for index in range(40)], 14) == 100.0


def test_volume_profile_has_ordered_value_area():
    profile = volume_profile(candles(), rows=10)
    assert profile is not None
    assert profile.val <= profile.poc <= profile.vah
    assert len(profile.hvns) == 5
