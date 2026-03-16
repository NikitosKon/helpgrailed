import sys
import logging
import asyncio
import re
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from config import BOT_TOKEN, ADMIN_IDS, DB_FILE, SUPPORT_CONTACT, CRYPTO_TOKEN
from database import db
from crypto import crypto

# Импорт обработчиков
from handlers.start import start_command
from handlers.menu import button_handler, text_handler
from handlers.admin import handle_admin
from handlers.commands import (
    menu_command, profile_command, balance_command,
    services_command, referral_command, help_command, admin_command
)

# Настройка логирования
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
    """Установка команд бота"""
    commands = [
        ("start", "🚀 Запустить бота"),
        ("menu", "🏠 Главное меню"),
        ("profile", "👤 Мой профиль"),
        ("balance", "💰 Мой баланс"),
        ("services", "🛒 Услуги"),
        ("referral", "🔗 Рефералка"),
        ("help", "❓ Помощь"),
        ("admin", "👑 Админ-панель"),
    ]
    
    await application.bot.set_my_commands([
        (cmd, desc) for cmd, desc in commands
    ])
    
    logger.info("✅ Команды бота установлены")


async def check_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка и очистка неподтверждённых платежей"""
    logger.info("Checking pending payments...")
    
    try:
        now = datetime.now()
        ten_minutes_ago = (now - timedelta(minutes=10)).isoformat()
        
        # 1. Удаляем старые неоплаченные инвойсы (старше 10 минут)
        if db.use_postgres:
            # PostgreSQL запрос
            old_pending = db.execute(
                """SELECT * FROM transactions 
                   WHERE status = 'pending' 
                   AND type = 'deposit'
                   AND created_at < %s""",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            # SQLite запрос
            old_pending = db.execute(
                """SELECT * FROM transactions 
                   WHERE status = 'pending' 
                   AND type = 'deposit'
                   AND datetime(created_at) < datetime('now', '-10 minutes')""",
                fetch=True
            )
        
        if old_pending:
            logger.info(f"Found {len(old_pending)} expired payments")
            for trans in old_pending:
                trans = dict(trans)
                # Обновляем статус на 'expired'
                db.execute(
                    "UPDATE transactions SET status = 'expired' WHERE id = %s" if db.use_postgres else "UPDATE transactions SET status = 'expired' WHERE id = ?",
                    (trans['id'],),
                    commit=True
                )
                logger.info(f"Payment {trans['invoice_id']} marked as expired (older than 10 min)")
        
        # 2. Проверяем актуальные pending транзакции (не старше 10 минут)
        if db.use_postgres:
            # PostgreSQL запрос
            pending = db.execute(
                """SELECT * FROM transactions 
                   WHERE status = 'pending' 
                   AND type = 'deposit'
                   AND created_at >= %s""",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            # SQLite запрос
            pending = db.execute(
                """SELECT * FROM transactions 
                   WHERE status = 'pending' 
                   AND type = 'deposit'
                   AND datetime(created_at) >= datetime('now', '-10 minutes')""",
                fetch=True
            )
        
        if not pending:
            logger.info("No active pending payments found")
            return
        
        logger.info(f"Found {len(pending)} active pending payments")
        
        for trans in pending:
            trans = dict(trans)
            try:
                logger.info(f"Checking invoice {trans['invoice_id']} for user {trans['user_id']}")
                
                invoice = await crypto.get_invoice_status(trans['invoice_id'])
                
                if invoice and invoice.get('status') == 'paid':
                    logger.info(f"Invoice {trans['invoice_id']} is paid!")
                    
                    db.add_balance(trans['user_id'], trans['amount'])
                    
                    db.execute(
                        "UPDATE transactions SET status = 'completed', completed_at = %s WHERE id = %s" if db.use_postgres else "UPDATE transactions SET status = 'completed', completed_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), trans['id']),
                        commit=True
                    )
                    
                    try:
                        await context.bot.send_message(
                            trans['user_id'],
                            f"✅ Баланс пополнен на ${trans['amount']:.2f}!\n"
                            f"💰 Текущий баланс: ${db.get_balance(trans['user_id']):.2f}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
                        
                    logger.info(f"Payment confirmed for user {trans['user_id']}")
                    
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"💰 <b>ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>\n\n"
                                f"👤 Пользователь: <code>{trans['user_id']}</code>\n"
                                f"💵 Сумма: ${trans['amount']:.2f}\n"
                                f"🔗 Invoice: <code>{trans['invoice_id']}</code>",
                                parse_mode='HTML'
                            )
                        except:
                            pass
                else:
                    status = invoice.get('status') if invoice else 'unknown'
                    logger.info(f"Invoice {trans['invoice_id']} status: {status}")
                    
            except Exception as e:
                logger.error(f"Error checking payment {trans['id']}: {e}")
    
    except Exception as e:
        logger.error(f"Error in check_pending_payments: {e}")
        # Делаем rollback на всякий случай
        if hasattr(db, 'conn') and db.use_postgres:
            try:
                db.conn.rollback()
                logger.info("Transaction rolled back after error")
            except:
                pass


async def payment_notification_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений от CryptoPay бота"""
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
                trans = dict(trans[0])
                
                db.add_balance(trans['user_id'], trans['amount'])
                
                db.execute(
                    """UPDATE transactions 
                       SET status = 'completed', completed_at = ? 
                       WHERE id = ?""",
                    (datetime.now().isoformat(), trans['id']),
                    commit=True
                )
                
                try:
                    await context.bot.send_message(
                        trans['user_id'],
                        f"✅ Баланс пополнен на ${trans['amount']:.2f}!\n"
                        f"💰 Текущий баланс: ${db.get_balance(trans['user_id']):.2f}"
                    )
                except:
                    pass
                
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"💰 <b>ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>\n\n"
                            f"👤 Пользователь: <code>{trans['user_id']}</code>\n"
                            f"💵 Сумма: ${trans['amount']:.2f}\n"
                            f"🔗 Invoice: <code>{invoice_id}</code>",
                            parse_mode='HTML'
                        )
                    except:
                        pass


async def post_init(application: Application):
    """Действия после инициализации бота"""
    await set_commands(application)
    
    # Проверка платежей каждые 60 секунд
    application.job_queue.run_repeating(
        check_pending_payments,
        interval=60,  # Каждую минуту
        first=10
    )
    
    logger.info("Bot initialized successfully")


def main():
    """Запуск бота"""
    logger.info("Starting bot in polling mode...")
    
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("services", services_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Регистрируем остальные обработчики
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, text_handler))
    
    # Обработчик сообщений от CryptoBot
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