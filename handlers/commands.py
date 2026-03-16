from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu, back_button, categories_menu
from config import SUPPORT_CONTACT, ADMIN_IDS

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /menu - главное меню"""
    user = update.effective_user
    text = "🏠 <b>Главное меню</b>\n\nВыберите нужный раздел:"
    await update.message.reply_text(
        text,
        reply_markup=main_menu(user.id),
        parse_mode='HTML'
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile - профиль пользователя"""
    user = update.effective_user
    
    purchases = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND type = 'purchase' AND status = 'completed'", 
        (user.id,), 
        fetch=True
    )[0][0] or 0
    
    total_spent = db.execute(
        "SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'purchase' AND status = 'completed'", 
        (user.id,), 
        fetch=True
    )[0][0] or 0
    
    referrals = db.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )[0][0] or 0
    
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📝 Username: @{user.username or 'нет'}\n"
        f"💰 Баланс: ${db.get_balance(user.id)}\n"
        f"📦 Покупок: {purchases}\n"
        f"💸 Всего потрачено: ${total_spent:.2f}\n"
        f"👥 Рефералов: {referrals}"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=back_button('menu'),
        parse_mode='HTML'
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance - баланс и пополнение"""
    user = update.effective_user
    balance = db.get_balance(user.id)
    
    text = (
        f"💰 <b>Баланс</b>\n\n"
        f"Текущий баланс: ${balance}\n\n"
        f"Пополнить или вывести средства?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💰 Пополнить", callback_data='deposit'),
            InlineKeyboardButton("💸 Вывести", callback_data='withdraw')
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /services - список услуг"""
    text = "📂 <b>Услуги</b>\n\nВыберите категорию:"
    await update.message.reply_text(
        text,
        reply_markup=categories_menu(),
        parse_mode='HTML'
    )

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /referral - реферальная программа"""
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref{user.id}"
    
    referrals_count = db.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )[0][0] or 0
    
    earned = db.execute(
        "SELECT SUM(bonus) FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )[0][0] or 0
    
    text = (
        f"🔗 <b>Реферальная программа</b>\n\n"
        f"Приглашайте друзей и получайте <b>10%</b> от их первой покупки!\n\n"
        f"📎 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
        f"👥 Приглашено: {referrals_count}\n"
        f"💰 Заработано: ${earned:.2f}"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=back_button('menu'),
        parse_mode='HTML'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - справка"""
    text = (
        "❓ <b>Помощь</b>\n\n"
        "🔹 <b>Доступные команды:</b>\n"
        "• /start - Запустить бота\n"
        "• /menu - Главное меню\n"
        "• /profile - Мой профиль\n"
        "• /balance - Мой баланс\n"
        "• /services - Услуги\n"
        "• /referral - Реферальная программа\n"
        "• /admin - Админ-панель (для админов)\n\n"
        f"📞 <b>Поддержка:</b> {SUPPORT_CONTACT}\n"
        f"📢 <b>Канал:</b> @helpgrailed"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=back_button('menu'),
        parse_mode='HTML'
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin - админ-панель"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет доступа к админ-панели")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        [InlineKeyboardButton("📦 Управление товарами", callback_data='admin_products')],
        [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
        [InlineKeyboardButton("📈 Продажи", callback_data='admin_sales')],
        [InlineKeyboardButton("👑 Управление админами", callback_data='admin_admins')],
        [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
    ]
    
    await update.message.reply_text(
        "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )