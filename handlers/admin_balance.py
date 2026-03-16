from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

async def admin_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления балансами"""
    query = update.callback_query
    user = query.from_user
    
    if user.id not in ADMIN_IDS:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Начислить баланс", callback_data='admin_add_balance')],
        [InlineKeyboardButton("🔍 Поиск пользователя", callback_data='admin_search_user')],
        [InlineKeyboardButton("📊 Топ пользователей", callback_data='admin_top_users')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]
    
    await query.edit_message_text(
        "💰 <b>Управление балансами</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def admin_add_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало начисления баланса"""
    query = update.callback_query
    user = query.from_user
    
    db.set_pending_action(user.id, 'admin_add_balance_user')
    
    await query.edit_message_text(
        "💰 <b>Начисление баланса</b>\n\n"
        "Введите ID пользователя или username (с @):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')
        ]]),
        parse_mode='HTML'
    )

async def process_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    """Обработка начисления баланса"""
    admin = update.effective_user
    
    action = context.user_data.get('admin_balance_step', 'user')
    
    if action == 'user':
        # Ищем пользователя
        query = text.replace('@', '')
        users = db.search_users(query)
        
        if not users:
            await update.message.reply_text(
                "❌ Пользователь не найден. Попробуйте ещё раз:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')
                ]])
            )
            return
        
        if len(users) > 1:
            # Показываем список найденных пользователей
            keyboard = []
            for u in users[:5]:
                btn_text = f"{u['first_name']} (@{u['username']}) - ${u['balance']}"
                keyboard.append([InlineKeyboardButton(
                    btn_text, 
                    callback_data=f"admin_select_user_{u['user_id']}"
                )])
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_balance_menu')])
            
            await update.message.reply_text(
                "Найдено несколько пользователей. Выберите:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            db.clear_pending_action(admin.id)
            return
        
        # Один пользователь
        user = users[0]
        context.user_data['target_user'] = user
        context.user_data['admin_balance_step'] = 'amount'
        
        await update.message.reply_text(
            f"👤 Пользователь: {user['first_name']} (@{user['username']})\n"
            f"💰 Текущий баланс: ${user['balance']}\n\n"
            f"Введите сумму для начисления:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')
            ]])
        )
        
    elif action == 'amount':
        try:
            amount = float(text)
            user = context.user_data.get('target_user')
            
            if not user:
                await update.message.reply_text("❌ Ошибка. Начните заново.")
                db.clear_pending_action(admin.id)
                return
            
            reason = context.user_data.get('balance_reason', 'Начисление админом')
            
            # Начисляем баланс
            success = db.admin_add_balance(user['user_id'], amount, reason)
            
            if success:
                await update.message.reply_text(
                    f"✅ Баланс успешно начислен!\n\n"
                    f"👤 Пользователь: {user['first_name']}\n"
                    f"💰 Сумма: ${amount}\n"
                    f"💳 Новый баланс: ${db.get_balance(user['user_id'])}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ В меню", callback_data='admin_balance_menu')
                    ]])
                )
            else:
                await update.message.reply_text("❌ Ошибка при начислении баланса")
            
            db.clear_pending_action(admin.id)
            context.user_data.clear()
            
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число")