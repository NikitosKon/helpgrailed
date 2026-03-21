import sys
import logging
import asyncio
import re
import os
from datetime import datetime, timedelta
from aiohttp import web

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from config import BOT_TOKEN, ADMIN_IDS, DB_FILE, SUPPORT_CONTACT, CRYPTO_TOKEN
from database import db
from crypto import crypto

# РРјРїРѕСЂС‚ РѕР±СЂР°Р±РѕС‚С‡РёРєРѕРІ
from handlers.start import start_command
from handlers.menu import button_handler, text_handler
from handlers.admin import handle_admin
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

# РќР°СЃС‚СЂРѕР№РєР° Р»РѕРіРёСЂРѕРІР°РЅРёСЏ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# === Healthcheck СЃРµСЂРІРµСЂ РґР»СЏ Render ===
async def healthcheck(request):
    """РџСЂРѕСЃС‚РѕР№ healthcheck РґР»СЏ Render"""
    return web.Response(text="Bot is running")

async def run_healthcheck():
    """Р—Р°РїСѓСЃРє healthcheck СЃРµСЂРІРµСЂР°"""
    app = web.Application()
    app.router.add_get('/', healthcheck)
    app.router.add_get('/health', healthcheck)
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"вњ… Healthcheck server started on port {port}")


async def set_commands(application: Application):
    """РЈСЃС‚Р°РЅРѕРІРєР° РєРѕРјР°РЅРґ Р±РѕС‚Р°"""
    commands = [
        ("start", "рџљЂ Р—Р°РїСѓСЃС‚РёС‚СЊ Р±РѕС‚Р°"),
        ("menu", "рџЏ  Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ"),
        ("profile", "рџ‘¤ РњРѕР№ РїСЂРѕС„РёР»СЊ"),
        ("balance", "рџ’° РњРѕР№ Р±Р°Р»Р°РЅСЃ"),
        ("services", "рџ›’ РЈСЃР»СѓРіРё"),
        ("referral", "рџ”— Р РµС„РµСЂР°Р»РєР°"),
        ("help", "вќ“ РџРѕРјРѕС‰СЊ"),
        ("language", "рџЊђ Р’С‹Р±СЂР°С‚СЊ СЏР·С‹Рє"),
        ("admin", "рџ‘‘ РђРґРјРёРЅ-РїР°РЅРµР»СЊ"),
    ]
    
    await application.bot.set_my_commands([
        (cmd, desc) for cmd, desc in commands
    ])
    
    logger.info("вњ… РљРѕРјР°РЅРґС‹ Р±РѕС‚Р° СѓСЃС‚Р°РЅРѕРІР»РµРЅС‹")


async def check_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """РџРµСЂРёРѕРґРёС‡РµСЃРєР°СЏ РїСЂРѕРІРµСЂРєР° Рё РѕС‡РёСЃС‚РєР° РЅРµРїРѕРґС‚РІРµСЂР¶РґС‘РЅРЅС‹С… РїР»Р°С‚РµР¶РµР№"""
    logger.info("Checking pending payments...")
    
    try:
        now = datetime.now()
        ten_minutes_ago = (now - timedelta(minutes=10)).isoformat()
        
        # РћРїСЂРµРґРµР»СЏРµРј, РёСЃРїРѕР»СЊР·СѓРµРј Р»Рё РјС‹ PostgreSQL
        use_postgres = hasattr(db, 'use_postgres') and db.use_postgres
        
        # 1. РЈРґР°Р»СЏРµРј СЃС‚Р°СЂС‹Рµ РЅРµРѕРїР»Р°С‡РµРЅРЅС‹Рµ РёРЅРІРѕР№СЃС‹ (СЃС‚Р°СЂС€Рµ 10 РјРёРЅСѓС‚)
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
        
        # 2. РџСЂРѕРІРµСЂСЏРµРј Р°РєС‚СѓР°Р»СЊРЅС‹Рµ pending С‚СЂР°РЅР·Р°РєС†РёРё (РЅРµ СЃС‚Р°СЂС€Рµ 10 РјРёРЅСѓС‚)
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
                            f"вњ… Р‘Р°Р»Р°РЅСЃ РїРѕРїРѕР»РЅРµРЅ РЅР° ${trans_dict['amount']:.2f}!\n"
                            f"рџ’° РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: ${db.get_balance(trans_dict['user_id']):.2f}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
                        
                    logger.info(f"Payment confirmed for user {trans_dict['user_id']}")
                    
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"рџ’° <b>РџРћР”РўР’Р•Р Р–Р”Р•РќРР• РћРџР›РђРўР«</b>\n\n"
                                f"рџ‘¤ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: <code>{trans_dict['user_id']}</code>\n"
                                f"рџ’µ РЎСѓРјРјР°: ${trans_dict['amount']:.2f}\n"
                                f"рџ”— Invoice: <code>{trans_dict['invoice_id']}</code>",
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
        if hasattr(db, 'conn') and hasattr(db, 'use_postgres') and db.use_postgres:
            try:
                db.conn.rollback()
                logger.info("Transaction rolled back after error")
            except:
                pass


async def payment_notification_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """РћР±СЂР°Р±РѕС‚С‡РёРє СЃРѕРѕР±С‰РµРЅРёР№ РѕС‚ CryptoPay Р±РѕС‚Р°"""
    message = update.message
    
    if not message.from_user or message.from_user.username != "CryptoBot":
        return
    
    text = message.text or message.caption or ""
    
    if "вњ…" in text and "РѕРїР»Р°С‡РµРЅ" in text.lower():
        invoice_match = re.search(r'в„–\s*(\d+)', text)
        
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
                        f"вњ… Р‘Р°Р»Р°РЅСЃ РїРѕРїРѕР»РЅРµРЅ РЅР° ${trans_dict['amount']:.2f}!\n"
                        f"рџ’° РўРµРєСѓС‰РёР№ Р±Р°Р»Р°РЅСЃ: ${db.get_balance(trans_dict['user_id']):.2f}"
                    )
                except:
                    pass
                
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"рџ’° <b>РџРћР”РўР’Р•Р Р–Р”Р•РќРР• РћРџР›РђРўР«</b>\n\n"
                            f"рџ‘¤ РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: <code>{trans_dict['user_id']}</code>\n"
                            f"рџ’µ РЎСѓРјРјР°: ${trans_dict['amount']:.2f}\n"
                            f"рџ”— Invoice: <code>{invoice_id}</code>",
                            parse_mode='HTML'
                        )
                    except:
                        pass


async def post_init(application: Application):
    """Р”РµР№СЃС‚РІРёСЏ РїРѕСЃР»Рµ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё Р±РѕС‚Р°"""
    await run_healthcheck()
    await set_commands(application)
    
    # РџСЂРѕРІРµСЂРєР° РїР»Р°С‚РµР¶РµР№ РєР°Р¶РґС‹Рµ 60 СЃРµРєСѓРЅРґ
    application.job_queue.run_repeating(
        check_pending_payments,
        interval=60,
        first=10
    )
    
    logger.info("Bot initialized successfully")


async def set_commands(application: Application):
    """РЈСЃС‚Р°РЅРѕРІРєР° РєРѕРјР°РЅРґ Р±РѕС‚Р°."""
    commands = [
        ("start", "рџљЂ Р—Р°РїСѓСЃС‚РёС‚СЊ Р±РѕС‚Р°"),
        ("menu", "рџЏ  Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ"),
        ("profile", "рџ‘¤ РњРѕР№ РїСЂРѕС„РёР»СЊ"),
        ("balance", "рџ’° РњРѕР№ Р±Р°Р»Р°РЅСЃ"),
        ("services", "рџ›’ РЈСЃР»СѓРіРё"),
        ("referral", "рџ”— Р РµС„РµСЂР°Р»РєР°"),
        ("faq", "вќ“ FAQ"),
        ("help", "вќ“ РџРѕРјРѕС‰СЊ"),
        ("language", "рџЊђ Р’С‹Р±СЂР°С‚СЊ СЏР·С‹Рє"),
        ("admin", "рџ‘‘ РђРґРјРёРЅ-РїР°РЅРµР»СЊ"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("вњ… РљРѕРјР°РЅРґС‹ Р±РѕС‚Р° СѓСЃС‚Р°РЅРѕРІР»РµРЅС‹")


def main():
    """Р—Р°РїСѓСЃРє Р±РѕС‚Р°"""
    logger.info("Starting bot with healthcheck server...")
    
    
    # РЎРѕР·РґР°С‘Рј РїСЂРёР»РѕР¶РµРЅРёРµ Р±РѕС‚Р°
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РѕР±СЂР°Р±РѕС‚С‡РёРєРё РєРѕРјР°РЅРґ
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

    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РѕР±СЂР°Р±РѕС‚С‡РёРєРё callback-Р·Р°РїСЂРѕСЃРѕРІ
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РѕР±СЂР°Р±РѕС‚С‡РёРєРё СЃРѕРѕР±С‰РµРЅРёР№
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, text_handler))
    
    # РћР±СЂР°Р±РѕС‚С‡РёРє СЃРѕРѕР±С‰РµРЅРёР№ РѕС‚ CryptoBot
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Entity("username"),
        payment_notification_handler
    ))

    # Р—Р°РїСѓСЃРєР°РµРј Р±РѕС‚Р°
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )
     

if __name__ == '__main__':
    main()
