from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import main_menu, back_button, categories_menu
from config import SUPPORT_CONTACT, ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

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
    
    # Получаем количество покупок
    purchases_result = db.execute(
        "SELECT COUNT(*) as count FROM transactions WHERE user_id = ? AND type = 'purchase' AND status = 'completed'", 
        (user.id,), 
        fetch=True
    )
    if purchases_result:
        if db.use_postgres:
            purchases = purchases_result[0]['count'] or 0
        else:
            purchases = purchases_result[0][0] or 0
    else:
        purchases = 0
    
    # Получаем сумму потраченного
    spent_result = db.execute(
        "SELECT SUM(amount) as total FROM transactions WHERE user_id = ? AND type = 'purchase' AND status = 'completed'", 
        (user.id,), 
        fetch=True
    )
    if spent_result and spent_result[0]:
        if db.use_postgres:
            total_spent = spent_result[0]['total'] or 0
        else:
            total_spent = spent_result[0][0] or 0
    else:
        total_spent = 0
    
    # Получаем количество рефералов
    referrals_result = db.execute(
        "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )
    if referrals_result:
        if db.use_postgres:
            referrals = referrals_result[0]['count'] or 0
        else:
            referrals = referrals_result[0][0] or 0
    else:
        referrals = 0
    
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📝 Username: @{user.username or 'нет'}\n"
        f"💰 Баланс: ${db.get_balance(user.id):.2f}\n"
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
        f"Текущий баланс: ${balance:.2f}\n\n"
        f"Выберите действие:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📥 Пополнить", callback_data='deposit'),
            InlineKeyboardButton("📤 Вывести", callback_data='withdraw')
        ],
        [InlineKeyboardButton("🎫 Промокод", callback_data='promo_code')],
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
    
    # Получаем количество рефералов
    referrals_result = db.execute(
        "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )
    if referrals_result:
        if db.use_postgres:
            referrals_count = referrals_result[0]['count'] or 0
        else:
            referrals_count = referrals_result[0][0] or 0
    else:
        referrals_count = 0
    
    # Получаем сумму заработка
    earned_result = db.execute(
        "SELECT SUM(bonus) as total FROM referrals WHERE referrer_id = ?", 
        (user.id,), 
        fetch=True
    )
    if earned_result and earned_result[0]:
        if db.use_postgres:
            earned = earned_result[0]['total'] or 0
        else:
            earned = earned_result[0][0] or 0
    else:
        earned = 0
    
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

async def check_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка категорий в БД (только для админов)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        return
    
    # Проверяем через config
    from config import config
    config_cats = config.CATEGORIES
    
    # Проверяем напрямую из БД
    db_cats = db.get_categories()
    
    text = f"📊 <b>Диагностика категорий</b>\n\n"
    
    text += "📂 <b>Из config.CATEGORIES:</b>\n"
    if config_cats:
        for cat_id, cat_name in config_cats.items():
            text += f"• {cat_id}: {cat_name}\n"
    else:
        text += "❌ Пусто!\n"
    
    text += f"\n📂 <b>Из БД (db.get_categories()):</b>\n"
    if db_cats:
        for cat_id, cat_name in db_cats.items():
            text += f"• {cat_id}: {cat_name}\n"
    else:
        text += "❌ Пусто!\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def fix_categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фикс категорий (только для админов)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        return
    
    default_categories = {
        'grailed_accounts': "📱 Grailed account's",
        'paypal': "💳 PayPal",
        'call_service': "📞 Прозвон сервис",
        'grailed_likes': "❤️ Накрутка лайков на Grailed",
        'ebay': "🏷 eBay",
        'support': "🆘 Тех поддержка",
    }
    
    text = "🔄 <b>Добавляю категории:</b>\n\n"
    
    for cat_id, cat_name in default_categories.items():
        try:
            # Проверяем, есть ли уже
            existing = db.get_categories()
            if cat_id in existing:
                text += f"🔄 {cat_name} - уже есть\n"
                # Обновляем на всякий случай
                db.update_category(cat_id, cat_name)
            else:
                db.add_category(cat_id, cat_name)
                text += f"✅ {cat_name} - добавлено\n"
        except Exception as e:
            text += f"❌ {cat_name} - ошибка: {e}\n"
    
    await update.message.reply_text(text, parse_mode='HTML')