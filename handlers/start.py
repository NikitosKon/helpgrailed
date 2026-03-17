from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu
from config import LANGUAGES

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start - всегда показывает выбор языка"""
    user = update.effective_user
    args = context.args
    
    # Проверка реферальной ссылки
    referrer_id = None
    if args and args[0].startswith('ref'):
        try:
            referrer_id = int(args[0].replace('ref', ''))
        except:
            pass
    
    # Проверяем, есть ли пользователь в БД
    existing_user = db.get_user(user.id)
    
    # Если пользователь НОВЫЙ - регистрируем
    if not existing_user:
        db.register_user(user.id, user.username, user.first_name, referrer_id)
    
    # ВСЕГДА показываем выбор языка (и новым, и старым)
    text = "🌐 <b>Вітаємо! / Welcome! / Добро пожаловать!</b>\n\n"
    text += "Оберіть мову:\nChoose language:\nВыберите язык:"
    
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
            InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
        ],
        [InlineKeyboardButton("🇺🇦 Українська", callback_data='lang_uk')]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        # Отправляем невидимое сообщение для удаления клавиатуры
        await update.message.reply_chat_action("typing")
        await update.message.reply_text(
            "⠀",
            reply_markup=ReplyKeyboardRemove()
        )