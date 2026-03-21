import logging
import re
from datetime import datetime, timedelta

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from config import BOT_TOKEN, ADMIN_IDS
from database import db
from crypto import crypto
from handlers.start import start_command
from handlers.menu import button_handler, text_handler
from handlers.language import language_command, language_callback
from handlers.commands import (
    menu_command,
    profile_command,
    balance_command,
    services_command,
    referral_command,
    faq_command,
    help_command,
    admin_command,
    fix_categories_command,
    check_categories_command,
    force_add_categories,
)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def set_commands(application: Application):
    commands = [
        ("start", "🚀 Запустить бота"),
        ("menu", "🏠 Главное меню"),
        ("profile", "👤 Мой профиль"),
        ("balance", "💰 Мой баланс"),
        ("services", "🛒 Услуги"),
        ("referral", "🔗 Рефералка"),
        ("faq", "❓ FAQ"),
        ("help", "❓ Помощь"),
        ("language", "🌐 Выбрать язык"),
        ("admin", "👑 Админ-панель"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Команды бота установлены")


async def check_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Checking pending payments...")

    try:
        now = datetime.now()
        ten_minutes_ago = (now - timedelta(minutes=10)).isoformat()
        use_postgres = hasattr(db, 'use_postgres') and db.use_postgres

        if use_postgres:
            old_pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND created_at < %s",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            old_pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND datetime(created_at) < datetime('now', '-10 minutes')",
                fetch=True
            )

        if old_pending:
            logger.info(f"Found {len(old_pending)} expired payments")
            for trans in old_pending:
                trans_dict = dict(trans) if not isinstance(trans, dict) else trans
                if use_postgres:
                    db.execute(
                        "UPDATE transactions SET status = 'expired' WHERE id = %s",
                        (trans_dict['id'],),
                        commit=True
                    )
                else:
                    db.execute(
                        "UPDATE transactions SET status = 'expired' WHERE id = ?",
                        (trans_dict['id'],),
                        commit=True
                    )
                logger.info(f"Payment {trans_dict['invoice_id']} marked as expired (older than 10 min)")

        if use_postgres:
            pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND created_at >= %s",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND datetime(created_at) >= datetime('now', '-10 minutes')",
                fetch=True
            )

        if not pending:
            logger.info("No active pending payments found")
            return

        logger.info(f"Found {len(pending)} active pending payments")

        for trans in pending:
            trans_dict = dict(trans) if not isinstance(trans, dict) else trans
            try:
                logger.info(f"Checking invoice {trans_dict['invoice_id']} for user {trans_dict['user_id']}")
                invoice = await crypto.get_invoice_status(trans_dict['invoice_id'])

                if invoice and invoice.get('status') == 'paid':
                    logger.info(f"Invoice {trans_dict['invoice_id']} is paid!")
                    db.add_balance(trans_dict['user_id'], trans_dict['amount'])

                    if use_postgres:
                        db.execute(
                            "UPDATE transactions SET status = 'completed', completed_at = %s WHERE id = %s",
                            (datetime.now().isoformat(), trans_dict['id']),
                            commit=True
                        )
                    else:
                        db.execute(
                            "UPDATE transactions SET status = 'completed', completed_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), trans_dict['id']),
                            commit=True
                        )

                    try:
                        await context.bot.send_message(
                            trans_dict['user_id'],
                            f"✅ Баланс пополнен на ${trans_dict['amount']:.2f}!\n"
                            f"💰 Текущий баланс: ${db.get_balance(trans_dict['user_id']):.2f}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")

                    logger.info(f"Payment confirmed for user {trans_dict['user_id']}")

                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"💰 <b>ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>\n\n"
                                f"👤 Пользователь: <code>{trans_dict['user_id']}</code>\n"
                                f"💵 Сумма: ${trans_dict['amount']:.2f}\n"
                                f"🔗 Invoice: <code>{trans_dict['invoice_id']}</code>",
                                parse_mode='HTML'
                            )
                        except Exception:
                            pass
                else:
                    status = invoice.get('status') if invoice else 'unknown'
                    logger.info(f"Invoice {trans_dict['invoice_id']} status: {status}")

            except Exception as e:
                logger.error(f"Error checking payment {trans_dict['id']}: {e}")

    except Exception as e:
        logger.error(f"Error in check_pending payments: {e}")
        if hasattr(db, 'conn') and hasattr(db, 'use_postgres') and db.use_postgres:
            try:
                db.conn.rollback()
                logger.info("Transaction rolled back after error")
            except Exception:
                pass


async def payment_notification_handler(update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message.from_user or message.from_user.username != "CryptoBot":
        return

    text = message.text or message.caption or ""
    if "✅" in text and "оплачен" in text.lower():
        invoice_match = re.search(r'№\s*(\d+)', text)
        if invoice_match:
            invoice_id = invoice_match.group(1)
            trans = db.execute(
                "SELECT * FROM transactions WHERE invoice_id = ? AND status = 'pending'",
                (invoice_id,),
                fetch=True
            )
            if trans:
                trans_dict = dict(trans[0])
                db.add_balance(trans_dict['user_id'], trans_dict['amount'])
                db.execute(
                    "UPDATE transactions SET status = 'completed', completed_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), trans_dict['id']),
                    commit=True
                )


async def post_init(application: Application):
    await set_commands(application)
    application.job_queue.run_repeating(
        check_pending_payments,
        interval=60,
        first=10
    )
    logger.info("Bot initialized successfully")


def main():
    logger.info("Starting bot...")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("services", services_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("fixcats", fix_categories_command))
    application.add_handler(CommandHandler("checkcats", check_categories_command))
    application.add_handler(CommandHandler("forcecats", force_add_categories))

    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, text_handler))
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Entity("username"),
        payment_notification_handler
    ))

    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )


if __name__ == '__main__':
    main()
