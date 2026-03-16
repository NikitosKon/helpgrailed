from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
import logging

logger = logging.getLogger(__name__)

async def handle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки промокода"""
    query = update.callback_query
    user = query.from_user
    
    db.set_pending_action(user.id, 'enter_promo')
    
    await query.edit_message_text(
        "🎫 <b>Введите промокод</b>\n\n"
        "Отправьте промокод в чат:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='balance')
        ]]),
        parse_mode='HTML'
    )