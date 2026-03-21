from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from config import LANGUAGES
from handlers.start import send_home_screen

import logging

logger = logging.getLogger(__name__)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    user_data = db.get_user(user.id)
    current_lang = user_data.get('language', 'ru') if user_data else 'ru'
    text = LANGUAGES[current_lang]['choose_language']

    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
            InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
        ],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data='lang_uk')],
        [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    lang = query.data.replace('lang_', '')
    if lang not in LANGUAGES:
        await query.answer("❌ Unsupported language", show_alert=True)
        return

    db.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (lang, user.id),
        commit=True
    )

    context.user_data.clear()

    try:
        await query.message.delete()
    except Exception:
        pass

    await send_home_screen(context, user, lang, query.message.chat_id)
