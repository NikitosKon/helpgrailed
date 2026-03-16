from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import back_button, get_text
from datetime import datetime

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    query = update.callback_query
    user = query.from_user
    
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
    
    # КНОПКА ИСТОРИИ ПОКУПОК - должна быть здесь!
    keyboard = [
        [InlineKeyboardButton("📜 История покупок", callback_data='purchase_history')],
        [InlineKeyboardButton(get_text('back'), callback_data='menu')]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_purchase_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю покупок"""
    query = update.callback_query
    user = query.from_user
    
    history = db.get_purchase_history(user.id)
    
    if not history:
        await query.edit_message_text(
            "📜 <b>История покупок</b>\n\n"
            "У вас пока нет покупок.",
            reply_markup=back_button('profile'),
            parse_mode='HTML'
        )
        return
    
    text = "📜 <b>Ваши покупки:</b>\n\n"
    for item in history:
        date = datetime.fromisoformat(item['purchase_date']).strftime('%d.%m.%Y')
        text += f"• {date} - {item['product_name']} - ${item['amount']}\n"
    
    await query.edit_message_text(
        text,
        reply_markup=back_button('profile'),
        parse_mode='HTML'
    )

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реферальная программа"""
    query = update.callback_query
    user = query.from_user
    
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
    
    await query.edit_message_text(
        text,
        reply_markup=back_button('menu'),
        parse_mode='HTML'
    )