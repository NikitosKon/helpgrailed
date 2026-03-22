import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import db

logger = logging.getLogger(__name__)


async def _edit_or_send(query, text, reply_markup=None, parse_mode=None):
    try:
        return await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        return await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


def _user_title(user: dict) -> str:
    first_name = user.get('first_name') or 'Без имени'
    username = f"@{user['username']}" if user.get('username') else 'без username'
    return f"{first_name} ({username})"


def _build_user_stats_text(user: dict) -> str:
    user_id = user['user_id']

    transactions = db.execute(
        "SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = ?",
        (user_id,),
        fetch=True
    ) or []
    purchases = db.execute(
        "SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = ? AND type = 'purchase' AND status = 'completed'",
        (user_id,),
        fetch=True
    ) or []

    tx_row = transactions[0] if transactions else {'count': 0, 'total': 0}
    purchase_row = purchases[0] if purchases else {'count': 0, 'total': 0}

    if db.use_postgres:
        tx_count = tx_row['count']
        tx_total = tx_row['total'] or 0
        purchase_count = purchase_row['count']
        purchase_total = purchase_row['total'] or 0
    else:
        tx_count = tx_row[0]
        tx_total = tx_row[1] or 0
        purchase_count = purchase_row[0]
        purchase_total = purchase_row[1] or 0

    return (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: {html.escape(user.get('first_name') or '—')}\n"
        f"Username: {html.escape('@' + user['username'] if user.get('username') else '—')}\n"
        f"Баланс: <b>${float(user.get('balance') or 0):.2f}</b>\n"
        f"Язык: {html.escape(user.get('language') or '—')}\n"
        f"Регистрация: {html.escape(str(user.get('registered_date') or '—'))}\n"
        f"Последняя активность: {html.escape(str(user.get('last_active') or '—'))}\n\n"
        f"Транзакций всего: {tx_count}\n"
        f"Оборот по транзакциям: ${float(tx_total):.2f}\n"
        f"Покупок: {purchase_count}\n"
        f"Покупок на сумму: ${float(purchase_total):.2f}"
    )


def _user_actions_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Начислить", callback_data=f'admin_balance_credit_{user_id}')],
        [InlineKeyboardButton("💸 Списать", callback_data=f'admin_balance_debit_{user_id}')],
        [InlineKeyboardButton("🔎 Новый поиск", callback_data='admin_search_user')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_balance_menu')],
    ])


async def admin_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    if user.id not in ADMIN_IDS:
        await query.answer("Доступ запрещен", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("🔎 Найти пользователя", callback_data='admin_search_user')],
        [InlineKeyboardButton("💰 Начислить баланс", callback_data='admin_add_balance')],
        [InlineKeyboardButton("📊 Топ пользователей", callback_data='admin_top_users')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')],
    ]
    await _edit_or_send(
        query,
        "💰 <b>Управление балансами</b>\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_add_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    context.user_data.pop('target_user', None)
    context.user_data['admin_balance_flow'] = 'credit'
    context.user_data['admin_balance_step'] = 'user'
    db.set_pending_action(user.id, 'admin_add_balance_user')
    await _edit_or_send(
        query,
        "💰 <b>Начисление баланса</b>\n\nВведите ID пользователя, @username или имя:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')]]),
        parse_mode='HTML'
    )


async def admin_search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    context.user_data.pop('target_user', None)
    context.user_data['admin_balance_flow'] = 'search'
    context.user_data['admin_balance_step'] = 'user'
    db.set_pending_action(user.id, 'admin_add_balance_user')
    await _edit_or_send(
        query,
        "🔎 <b>Поиск пользователя</b>\n\nВведите ID пользователя, @username или имя:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')]]),
        parse_mode='HTML'
    )


async def admin_show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    users = db.execute(
        "SELECT user_id, username, first_name, balance FROM users ORDER BY balance DESC, user_id DESC LIMIT 10",
        fetch=True
    ) or []

    if not users:
        await _edit_or_send(
            query,
            "📭 Пользователей нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_balance_menu')]])
        )
        return

    text = "📊 <b>Топ пользователей по балансу</b>\n\n"
    keyboard = []
    for row in users:
        user = dict(row) if isinstance(row, dict) else {
            'user_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'balance': row[3],
        }
        text += f"• <code>{user['user_id']}</code> | {html.escape(_user_title(user))} | ${float(user.get('balance') or 0):.2f}\n"
        keyboard.append([InlineKeyboardButton(f"👤 {_user_title(user)}", callback_data=f"admin_balance_user_{user['user_id']}")])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_balance_menu')])
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_show_user_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    query = update.callback_query
    user = db.find_user_by_identifier(str(user_id))
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return
    context.user_data['target_user'] = user
    await _edit_or_send(query, _build_user_stats_text(user), reply_markup=_user_actions_keyboard(user_id), parse_mode='HTML')


async def admin_balance_change_start(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, mode: str):
    query = update.callback_query
    user = db.find_user_by_identifier(str(user_id))
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    admin = query.from_user
    context.user_data['target_user'] = user
    context.user_data['admin_balance_flow'] = mode
    context.user_data['admin_balance_step'] = 'amount'
    db.set_pending_action(admin.id, 'admin_add_balance_amount')

    verb = "начисления" if mode == 'credit' else "списания"
    await _edit_or_send(
        query,
        f"{'💰' if mode == 'credit' else '💸'} <b>{verb.title()} баланса</b>\n\n"
        f"Пользователь: {html.escape(_user_title(user))}\n"
        f"Текущий баланс: ${float(user.get('balance') or 0):.2f}\n\n"
        f"Введите сумму для {verb}:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"admin_balance_user_{user_id}")]]),
        parse_mode='HTML'
    )


async def process_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    admin = update.effective_user
    step = context.user_data.get('admin_balance_step', 'user')
    flow = context.user_data.get('admin_balance_flow', 'credit')

    if step == 'user':
        query_text = text.replace('@', '').strip()
        users = db.search_users(query_text)
        if not users:
            await update.message.reply_text(
                "❌ Пользователь не найден. Попробуйте ещё раз.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')]])
            )
            return

        if len(users) == 1:
            user = users[0]
            context.user_data['target_user'] = user
            if flow == 'search':
                db.clear_pending_action(admin.id)
                await update.message.reply_text(
                    _build_user_stats_text(user),
                    reply_markup=_user_actions_keyboard(user['user_id']),
                    parse_mode='HTML'
                )
                return

            context.user_data['admin_balance_step'] = 'amount'
            db.set_pending_action(admin.id, 'admin_add_balance_amount')
            await update.message.reply_text(
                f"👤 Пользователь: {html.escape(_user_title(user))}\n"
                f"Текущий баланс: ${float(user.get('balance') or 0):.2f}\n\n"
                f"Введите сумму для {'начисления' if flow == 'credit' else 'списания'}:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_balance_menu')]]),
                parse_mode='HTML'
            )
            return

        keyboard = []
        for user in users[:10]:
            keyboard.append([InlineKeyboardButton(
                f"{_user_title(user)} | ${float(user.get('balance') or 0):.2f}",
                callback_data=f"admin_balance_user_{user['user_id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_balance_menu')])
        db.clear_pending_action(admin.id)
        await update.message.reply_text(
            "Найдено несколько пользователей. Выберите нужного:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if step == 'amount':
        target_user = context.user_data.get('target_user')
        if not target_user:
            db.clear_pending_action(admin.id)
            context.user_data.clear()
            await update.message.reply_text("❌ Сессия сброшена. Начните заново.")
            return

        try:
            amount = float(text.replace(',', '.'))
        except ValueError:
            await update.message.reply_text("❌ Введите корректную сумму.")
            return

        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0.")
            return

        if flow == 'debit':
            current_balance = float(db.get_balance(target_user['user_id']) or 0)
            if current_balance < amount:
                await update.message.reply_text(
                    f"❌ Недостаточно средств для списания.\nТекущий баланс: ${current_balance:.2f}"
                )
                return
            success = db.admin_add_balance(target_user['user_id'], -amount, "Списание админом")
        else:
            success = db.admin_add_balance(target_user['user_id'], amount, "Начисление админом")

        if success:
            new_user = db.find_user_by_identifier(str(target_user['user_id'])) or target_user
            context.user_data['target_user'] = new_user
            db.clear_pending_action(admin.id)
            context.user_data['admin_balance_step'] = 'user'
            await update.message.reply_text(
                f"✅ Баланс {'списан' if flow == 'debit' else 'начислен'}.\n\n{_build_user_stats_text(new_user)}",
                reply_markup=_user_actions_keyboard(new_user['user_id']),
                parse_mode='HTML'
            )
            return

        await update.message.reply_text("❌ Не удалось изменить баланс.")
