from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu
from config import LANGUAGES


async def send_home_screen(context: ContextTypes.DEFAULT_TYPE, user, lang: str, chat_id: int):
    home = db.get_home_content()
    template = home.get(f'text_{lang}') or LANGUAGES[lang]['welcome']
    try:
        text = template.format(name=user.first_name)
    except Exception:
        text = template.replace('{name}', user.first_name)
    photo_file_id = home.get('photo_file_id')

    if photo_file_id:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=photo_file_id,
            caption=text,
            reply_markup=main_menu(user.id),
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=main_menu(user.id),
            parse_mode='HTML'
        )


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
    
    # Получаем пользователя из БД
    existing_user = db.get_user(user.id)
    
    # Проверяем, откуда пришли (callback или новое сообщение)
    is_callback = update.callback_query is not None
    
    # Если пользователь НОВЫЙ - регистрируем и показываем выбор языка
    if not existing_user:
        db.register_user(user.id, user.username, user.first_name, referrer_id)
        
        text = "🌐 <b>Welcome! Choose your language</b>\n\n"
        text += "Оберіть мову / Choose language / Выберите язык:"
        
        keyboard = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
                InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
            ],
            [InlineKeyboardButton("🇺🇦 Українська", callback_data='lang_uk')]
        ]
        
        if is_callback:
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
        return
    
    db.sync_user_profile(user.id, user.username, user.first_name)

    # Если пользователь существует - показываем меню на его языке
    lang = existing_user.get('language', 'ru')
    
    if is_callback:
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass
        await send_home_screen(context, user, lang, update.callback_query.message.chat_id)
    else:
        await send_home_screen(context, user, lang, update.message.chat_id)
        
        # Отправляем невидимое сообщение для удаления клавиатуры
        try:
            await update.message.reply_chat_action("typing")
            await update.message.reply_text(
                "⠀",
                reply_markup=ReplyKeyboardRemove()
            )
        except:
            pass
