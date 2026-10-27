from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .alerts import AlertService


def build_application(token: str, alerts: AlertService, status_text, define_profile) -> Application:
    application = Application.builder().token(token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text("Bot activo. Usa /status para ver el proveedor y /last para la última señal.")

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(status_text())

    async def last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message:
            return
        signal = alerts.last_signal
        if signal is None:
            await update.effective_message.reply_text("Todavía no hay señales.")
        else:
            await update.effective_message.reply_text(f"Última señal: {signal.direction} {signal.timeframe} a {signal.price:,.2f} | RSI {signal.rsi:.2f}")

    async def define(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_message:
            return
        try:
            message = await define_profile(context.args, update.effective_chat.id if update.effective_chat else None)
        except ValueError as exc:
            message = f"Error: {exc}"
        except Exception:
            message = "No se pudo cargar el histórico. Revisa los logs e inténtalo de nuevo."
        await update.effective_message.reply_text(message)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("last", last))
    application.add_handler(CommandHandler("define", define))
    return application
