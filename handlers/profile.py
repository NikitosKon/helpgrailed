from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import back_button, get_text
from datetime import datetime

async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    query = update.callback_query
    user = query.from_user
    
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
        f"👤 <b>{get_text('profile_title', user.id)}</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📝 {get_text('username_label', user.id)}: @{user.username or get_text('not_set', user.id)}\n"
        f"💰 {get_text('balance_title', user.id)}: ${db.get_balance(user.id)}\n"
        f"📦 {get_text('purchases_label', user.id)}: {purchases}\n"
        f"💸 {get_text('total_spent_label', user.id)}: ${total_spent:.2f}\n"
        f"👥 {get_text('referrals_label', user.id)}: {referrals}"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"📜 {get_text('purchase_history', user.id)}", callback_data='purchase_history')],
        [InlineKeyboardButton(get_text('back', user.id), callback_data='menu')]
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
            f"📜 <b>{get_text('purchase_history', user.id)}</b>\n\n"
            f"{get_text('no_purchases', user.id)}",
            reply_markup=back_button('profile', user.id),
            parse_mode='HTML'
        )
        return
    
    text = f"📜 <b>{get_text('your_purchases', user.id)}:</b>\n\n"
    for item in history:
        date = datetime.fromisoformat(item['purchase_date']).strftime('%d.%m.%Y')
        text += f"• {date} - {item['product_name']} - ${item['amount']}\n"
    
    await query.edit_message_text(
        text,
        reply_markup=back_button('profile', user.id),
        parse_mode='HTML'
    )

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реферальная программа"""
    query = update.callback_query
    user = query.from_user
    
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref{user.id}"
    
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
    
    # Используем get_text для перевода
    text = (
        f"🔗 <b>{get_text('referral', user.id)}</b>\n\n"
        f"{get_text('referral_description', user.id)}\n\n"
        f"📎 {get_text('your_link', user.id)}:\n<code>{ref_link}</code>\n\n"
        f"👥 {get_text('invited', user.id)}: {referrals_count}\n"
        f"💰 {get_text('earned', user.id)}: ${earned:.2f}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=back_button('menu', user.id),
        parse_mode='HTML'
    )
