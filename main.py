import sys
import logging
import asyncio
import re
import os
from datetime import datetime, timedelta
from aiohttp import web  # Добавленный импорт
from handlers.commands import (
    menu_command, profile_command, balance_command,
    services_command, referral_command, help_command, admin_command,
    fix_categories_command  # <--- добавь эту строку
)
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


# === НОВЫЙ КОД: Healthcheck сервер для Render ===
async def healthcheck(request):
    """Простой healthcheck для Render"""
    return web.Response(text="Bot is running")

async def run_healthcheck():
    """Запуск healthcheck сервера"""
    app = web.Application()
    app.router.add_get('/', healthcheck)
    app.router.add_get('/health', healthcheck)
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Healthcheck server started on port {port}")
# ============================================


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
        
        # Определяем, используем ли мы PostgreSQL
        use_postgres = hasattr(db, 'use_postgres') and db.use_postgres
        
        # 1. Удаляем старые неоплаченные инвойсы (старше 10 минут)
        if use_postgres:
            # PostgreSQL запрос
            old_pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND created_at < %s",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            # SQLite запрос
            old_pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND datetime(created_at) < datetime('now', '-10 minutes')",
                fetch=True
            )
        
        if old_pending:
            logger.info(f"Found {len(old_pending)} expired payments")
            for trans in old_pending:
                trans_dict = dict(trans) if not isinstance(trans, dict) else trans
                # Обновляем статус на 'expired'
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
        
        # 2. Проверяем актуальные pending транзакции (не старше 10 минут)
        if use_postgres:
            # PostgreSQL запрос
            pending = db.execute(
                "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND created_at >= %s",
                (ten_minutes_ago,),
                fetch=True
            )
        else:
            # SQLite запрос
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
                        except:
                            pass
                else:
                    status = invoice.get('status') if invoice else 'unknown'
                    logger.info(f"Invoice {trans_dict['invoice_id']} status: {status}")
                    
            except Exception as e:
                logger.error(f"Error checking payment {trans_dict['id']}: {e}")
    
    except Exception as e:
        logger.error(f"Error in check_pending_payments: {e}")
        # Делаем rollback на всякий случай
        if hasattr(db, 'conn') and hasattr(db, 'use_postgres') and db.use_postgres:
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
                trans_dict = dict(trans[0])
                
                db.add_balance(trans_dict['user_id'], trans_dict['amount'])
                
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
                except:
                    pass
                
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"💰 <b>ПОДТВЕРЖДЕНИЕ ОПЛАТЫ</b>\n\n"
                            f"👤 Пользователь: <code>{trans_dict['user_id']}</code>\n"
                            f"💵 Сумма: ${trans_dict['amount']:.2f}\n"
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


# === ИЗМЕНЁННАЯ ФУНКЦИЯ main() ===
def main():
    """Запуск бота"""
    logger.info("Starting bot with healthcheck server...")
    
    # Запускаем healthcheck сервер в отдельном цикле событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_healthcheck())
    
    # Создаём приложение бота
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
    application.add_handler(CommandHandler("fixcats", fix_categories_command))

    # Регистрируем остальные обработчики
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, text_handler))
    
    # Обработчик сообщений от CryptoBot
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Entity("username"),
        payment_notification_handler
    ))

    # Запускаем бота
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )
    
    application.add_handler(CommandHandler("checkcats", check_categories_command))

if __name__ == '__main__':
    main()