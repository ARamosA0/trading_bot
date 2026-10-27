import asyncio
import logging
from collections import defaultdict

from .alerts import AlertService
from .config import settings
from .market import MarketStream
from .strategy import evaluate
from .telegram_bot import build_application
from .profile import ProfileState, parse_define_datetime


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def run() -> None:
    config = settings()
    configure_logging(config.log_level)
    logger = logging.getLogger(__name__)
    alerts = AlertService(None, config.chat_ids, config.cooldown_minutes)
    stream = MarketStream(config.provider, config.symbol)
    buffers: dict[str, list] = defaultdict(list)
    histories: dict[str, list] = defaultdict(list)
    profile_state = ProfileState(config.profile_rows, config.profile_value_area, config.profile_hvn_count, config.profile_refresh_hours)
    latest_price = {"value": None}

    def status_text() -> str:
        price = latest_price["value"]
        provider = stream.provider
        current = f"Proveedor: {provider}\nSímbolo: {config.symbol}\n"
        current += f"Último precio: {price:,.2f}\n" if price else "Esperando datos...\n"
        current += profile_state.description(config.timezone)
        if profile_state.profile:
            profile = profile_state.profile
            hvns = ", ".join(f"{level:,.2f}" for level in profile.hvns)
            current += (
                f"\nHVN principales ({len(profile.hvns)}): {hvns}"
                f"\nPOC: {profile.poc:,.2f}"
                f"\nVAL (inicio del área de valor): {profile.val:,.2f}"
                f"\nVAH (final del área de valor): {profile.vah:,.2f}"
            )
        return current

    async def define_profile(args: list[str], chat_id: int | None) -> str:
        if config.chat_ids and chat_id not in config.chat_ids:
            return "No tienes permiso para modificar el Volume Profile."
        if len(args) != 2:
            raise ValueError("Usa: /define 22:00 26/10/26")
        start_ms = parse_define_datetime(args[0], args[1], config.timezone)
        candles = await stream.hourly_history(start_ms)
        if not candles:
            raise ValueError("No hay velas 1h cerradas disponibles desde esa fecha.")
        profile = profile_state.replace(start_ms, candles)
        histories["1h"] = candles[-config.profile_window :]
        logger.info("Volume Profile definido desde %s con %s velas 1h", start_ms, len(candles))
        return f"Volume Profile definido desde {args[0]} {args[1]} y reemplazado correctamente.\nVelas 1h cargadas: {len(candles)}\nHVN considerados: {len(profile.hvns) if profile else 0}\nSe actualizará cada {config.profile_refresh_hours}h."

    application = build_application(config.telegram_token, alerts, status_text, define_profile) if config.telegram_token else None
    if application:
        alerts.bot = application.bot
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram iniciado; chats permitidos: %s", config.chat_ids)
    else:
        logger.warning("TELEGRAM_BOT_TOKEN vacío: las alertas solo aparecerán en logs")

    try:
        async for candle in stream.candles():
            latest_price["value"] = candle.close
            for timeframe, size in (("15m", 15), ("30m", 30), ("1h", 60)):
                bucket = candle.timestamp // 60000 // size
                key = f"{timeframe}:{bucket}"
                current = buffers[key]
                current.append(candle)
                if len(current) < size:
                    continue
                aggregate = type(candle)(
                    timestamp=current[0].timestamp,
                    open=current[0].open,
                    high=max(item.high for item in current),
                    low=min(item.low for item in current),
                    close=current[-1].close,
                    volume=sum(item.volume for item in current),
                )
                histories[timeframe].append(aggregate)
                histories[timeframe] = histories[timeframe][-config.profile_window :]
                if timeframe == "1h":
                    refreshed = profile_state.add(aggregate)
                    if refreshed:
                        logger.info("Volume Profile ampliado a la derecha: bloque de %sh", config.profile_refresh_hours)
                    if profile_state.profile:
                        signal = evaluate(histories["15m"], histories["1h"], profile_state.profile, config.rsi_period, config.ema_period)
                    else:
                        signal = None
                    if signal:
                        await alerts.send(signal)
                del buffers[key]
    finally:
        if application:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
