import logging
import time

from telegram import Bot

from .models import Signal

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
        key = f"{signal.direction}:{signal.timeframe}"
        now = time.time()
        if now - self.last_sent.get(key, 0) < self.cooldown:
            return
        text = (
            f"🚨 *Alerta {signal.direction}* — BTC/USDT ({signal.timeframe})\n"
            f"Precio: `{signal.price:,.2f}`\nRSI: `{signal.rsi:.2f}`\n"
            f"POC: `{signal.profile.poc:,.2f}` | VAL: `{signal.profile.val:,.2f}` | VAH: `{signal.profile.vah:,.2f}`\n"
            f"EMA confirmada en cierre 1h: `{signal.ema:,.2f}`\n"
            f"Divergencia RSI: `{signal.divergence}`\nMotivo: {signal.reason}\n\n_Solo alerta informativa; no ejecuta operaciones._"
        )
        self.last_sent[key] = now
        if not self.bot or not self.chat_ids:
            LOGGER.info("Alerta sin Telegram: %s", text.replace("*", ""))
            return
        for chat_id in self.chat_ids:
            await self.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
