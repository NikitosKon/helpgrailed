from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu, get_text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    args = context.args
    
    # Проверка реферальной ссылки
    referrer_id = None
    if args and args[0].startswith('ref'):
        try:
            referrer_id = int(args[0].replace('ref', ''))
        except:
            pass
    
    # Регистрация пользователя
    db.register_user(user.id, user.username, user.first_name, referrer_id)
    db.update_activity(user.id)
    
    # Приветствие
    text = get_text('welcome', name=user.first_name)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu(user.id))
    else:
        # Отправляем меню
        await update.message.reply_text(
            text, 
            reply_markup=main_menu(user.id)
        )
        
        # Отправляем невидимое сообщение для удаления клавиатуры
        await update.message.reply_chat_action("typing")  # Показывает "печатает"
        await update.message.reply_text(
            "⠀",  # Невидимый пробел
            reply_markup=ReplyKeyboardRemove()
        )