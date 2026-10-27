import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    chat_ids: tuple[int, ...]
    provider: str
    symbol: str
    timezone: str
    rsi_period: int
    profile_rows: int
    profile_value_area: float
    profile_hvn_count: int
    profile_refresh_hours: int
    ema_period: int
    profile_window: int
    cooldown_minutes: int
    log_level: str


def settings() -> Settings:
    provider = os.getenv("MARKET_PROVIDER", "bitget").lower()
    if provider not in {"bitget", "binance"}:
        raise ValueError("MARKET_PROVIDER debe ser 'bitget' o 'binance'")
    return Settings(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_ids=_csv_ints(os.getenv("TELEGRAM_CHAT_IDS", "")),
        provider=provider,
        symbol=os.getenv("SYMBOL", "BTCUSDT").upper(),
        timezone=os.getenv("TIMEZONE", "America/Lima"),
        rsi_period=int(os.getenv("RSI_PERIOD", "14")),
        profile_rows=int(os.getenv("VOLUME_PROFILE_ROWS", "500")),
        profile_value_area=float(os.getenv("VOLUME_PROFILE_VALUE_AREA", "70")),
        profile_hvn_count=int(os.getenv("VOLUME_PROFILE_HVN_COUNT", "5")),
        profile_refresh_hours=int(os.getenv("VOLUME_PROFILE_REFRESH_HOURS", "4")),
        ema_period=int(os.getenv("EMA_PERIOD", "15")),
        profile_window=int(os.getenv("VOLUME_PROFILE_WINDOW", "240")),
        cooldown_minutes=int(os.getenv("ALERT_COOLDOWN_MINUTES", "15")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
