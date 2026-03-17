from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import LANGUAGES
import logging

logger = logging.getLogger(__name__)

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /language - показать выбор языка"""
    user = update.effective_user
    
    # Получаем текущий язык пользователя
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
    
    # Очищаем user_data при смене языка
    context.user_data.clear()
    
    # Показываем подтверждение
    text = LANGUAGES[lang]['language_changed']
    
    keyboard = [[InlineKeyboardButton(LANGUAGES[lang]['main_menu'], callback_data='menu')]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )