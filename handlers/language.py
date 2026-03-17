from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu
from config import LANGUAGES
import logging

logger = logging.getLogger(__name__)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /language - показать выбор языка"""
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
    """Обработчик выбора языка"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = query.data.replace('lang_', '')
    
    # Сохраняем язык пользователя в БД
    db.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (lang, user.id),
        commit=True
    )
    
    # Очищаем user_data
    context.user_data.clear()
    
    # Получаем пользователя и показываем главное меню
    user_data = db.get_user(user.id)
    text = LANGUAGES[lang]['welcome'].format(name=user.first_name)
    
    await query.edit_message_text(
        text,
        reply_markup=main_menu(user.id),
        parse_mode='HTML'
    )