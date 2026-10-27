from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Profile:
    poc: float
    vah: float
    val: float
    hvns: tuple[float, ...] = ()
    row_size: float = 0.0


@dataclass(frozen=True)
class Signal:
    direction: str
    timeframe: str
    price: float
    rsi: float
    profile: Profile
    reason: str
    timestamp: int
    ema: float
    divergence: str
    context: str
