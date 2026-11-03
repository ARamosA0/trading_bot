import logging
import time
from datetime import datetime, timezone

from telegram import Bot

from .models import MarketEvent, Signal

LOGGER = logging.getLogger(__name__)


class AlertService:
    def __init__(self, bot: Bot | None, chat_ids: tuple[int, ...], cooldown_minutes: int):
        self.bot = bot
        self.chat_ids = chat_ids
        self.cooldown = cooldown_minutes * 60
        self.last_sent: dict[str, float] = {}
        self.last_signal: Signal | None = None

    async def send(self, signal: Signal) -> None:
        self.last_signal = signal
        key = f"signal:{signal.direction}:{signal.timeframe}"
        timestamp = datetime.fromtimestamp(signal.timestamp / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        text = (
            f"🚨 *Alerta {signal.direction}* — BTC/USDT ({signal.timeframe})\n"
            f"Cierre: `{timestamp}`\n"
            f"Precio: `{signal.price:,.2f}`\nRSI: `{signal.rsi:.2f}`\n"
            f"POC: `{signal.profile.poc:,.2f}` | VAL: `{signal.profile.val:,.2f}` | VAH: `{signal.profile.vah:,.2f}`\n"
            f"EMA confirmada en cierre 1h: `{signal.ema:,.2f}`\n"
            f"Divergencia RSI: `{signal.divergence}`\nMotivo: {signal.reason}\n\n_Solo alerta informativa; no ejecuta operaciones._"
        )
        await self._deliver(key, text)

    async def send_event(self, event: MarketEvent) -> None:
        key = f"event:{event.kind}:{event.direction}:{event.timeframe}"
        timestamp = datetime.fromtimestamp(event.timestamp / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        title = {
            "hvn_touch": "Precio llegó a un HVN",
            "rsi_divergence": "Divergencia RSI detectada",
        }.get(event.kind, "Evento de mercado")
        rsi_text = f"{event.rsi:.2f}" if event.rsi is not None else "N/D"
        text = (
            f"ℹ️ *{title}* — BTC/USDT ({event.timeframe})\n"
            f"Dirección: `{event.direction}`\nCierre: `{timestamp}`\n"
            f"Precio: `{event.price:,.2f}` | RSI: `{rsi_text}`\n"
            f"POC: `{event.profile.poc:,.2f}` | VAL: `{event.profile.val:,.2f}` | VAH: `{event.profile.vah:,.2f}`\n"
            f"Motivo: {event.reason}\n\n_Evento informativo; no ejecuta operaciones._"
        )
        await self._deliver(key, text)

    async def _deliver(self, key: str, text: str) -> None:
        now = time.time()
        if now - self.last_sent.get(key, 0) < self.cooldown:
            return
        self.last_sent[key] = now
        if not self.bot or not self.chat_ids:
            LOGGER.info("Alerta sin Telegram: %s", text.replace("*", ""))
            return
        for chat_id in self.chat_ids:
            await self.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
