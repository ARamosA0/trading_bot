from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .indicators import volume_profile
from .models import Candle, Profile


def parse_define_datetime(time_text: str, date_text: str, timezone_name: str = "America/Lima") -> int:
    """Parse /define HH:MM DD/MM/YY using the configured timezone."""
    parsed = None
    for date_format in ("%H:%M %d/%m/%y", "%H:%M %d/%m/%Y"):
        try:
            parsed = datetime.strptime(f"{time_text} {date_text}", date_format)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError("Formato inválido. Usa /define HH:MM DD/MM/YY, por ejemplo /define 22:00 26/10/26")
    try:
        local = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    except Exception as exc:
        raise ValueError(f"Zona horaria inválida: {timezone_name}") from exc
    moment = local.astimezone(timezone.utc)
    if moment.timestamp() * 1000 >= datetime.now(timezone.utc).timestamp() * 1000:
        raise ValueError("El punto inicial debe estar en el pasado")
    return int(moment.timestamp() * 1000)


class ProfileState:
    def __init__(self, rows: int, value_area: float, hvn_count: int, refresh_hours: int):
        self.rows = rows
        self.value_area = value_area
        self.hvn_count = hvn_count
        self.refresh_hours = refresh_hours
        self.start_ms: int | None = None
        self.candles: list[Candle] = []
        self.profile: Profile | None = None
        self.last_refresh_bucket: int | None = None

    def replace(self, start_ms: int, candles: list[Candle]) -> Profile | None:
        self.start_ms = start_ms
        self.candles = list(candles)
        self.last_refresh_bucket = None
        self.profile = self._build()
        if self.candles:
            self.last_refresh_bucket = self._bucket(self.candles[-1].timestamp)
        return self.profile

    def add(self, candle: Candle) -> bool:
        if self.start_ms is None or candle.timestamp < self.start_ms:
            return False
        if not self.candles or candle.timestamp > self.candles[-1].timestamp:
            self.candles.append(candle)
        bucket = self._bucket(candle.timestamp)
        if bucket != self.last_refresh_bucket:
            self.profile = self._build()
            self.last_refresh_bucket = bucket
            return True
        return False

    def _bucket(self, timestamp: int) -> int:
        return timestamp // (self.refresh_hours * 60 * 60 * 1000)

    def _build(self) -> Profile | None:
        return volume_profile(self.candles, self.rows, self.value_area, self.hvn_count) if self.candles else None

    def description(self, timezone_name: str = "UTC") -> str:
        if self.start_ms is None:
            return "Perfil: no definido. Usa /define HH:MM DD/MM/YY"
        value = datetime.fromtimestamp(self.start_ms / 1000, timezone.utc).astimezone(ZoneInfo(timezone_name))
        return f"Perfil desde: {value:%H:%M %d/%m/%y} ({timezone_name}) | velas 1h: {len(self.candles)} | HVN: {self.hvn_count}"
