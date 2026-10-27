from app.indicators import rsi, volume_profile
from app.models import Candle
from app.profile import ProfileState

FOUR_HOURS_MS = 4 * 60 * 60 * 1000


def candles(count: int = 40) -> list[Candle]:
    return [
        Candle(index * FOUR_HOURS_MS, 100 + index, 101 + index, 99 + index, 100 + index, 10)
        for index in range(count)
    ]


def test_rsi_is_high_for_continuous_rise():
    assert rsi([float(index) for index in range(40)], 14) == 100.0


def test_volume_profile_has_ordered_value_area():
    candle_data = candles()
    profile = volume_profile(candle_data, rows=10, value_area_percent=70, hvn_count=5)
    assert profile is not None
    assert profile.val <= profile.poc <= profile.vah
    assert len(profile.hvns) == 5


def test_profile_description_reports_four_hour_candles():
    state = ProfileState(rows=10, value_area=70, hvn_count=5, refresh_hours=4)
    state.replace(0, candles(2))

    assert "velas 4h: 2" in state.description("UTC")
