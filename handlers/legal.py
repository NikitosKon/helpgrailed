from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from keyboards.reply import get_text


async def handle_terms(update: Update, context: ContextTypes.DEFAULT_TYPE, back_callback: str = 'menu', agree_callback: str | None = None):
    query = update.callback_query
    user = query.from_user
    text = (
        f"<b>{get_text('terms_title', user.id)}</b>\n\n"
        f"{get_text('terms_text', user.id)}"
    )
    rows = []
    if agree_callback:
        rows.append([InlineKeyboardButton("✅ Я прочитал и согласен", callback_data=agree_callback)])
    rows.append([InlineKeyboardButton(get_text('back', user.id), callback_data=back_callback)])
    keyboard = InlineKeyboardMarkup(rows)

    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
    except Exception:
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')


async def handle_terms_accept(update: Update, context: ContextTypes.DEFAULT_TYPE, back_callback: str = 'profile'):
    query = update.callback_query
    user = query.from_user
    db.accept_terms(user.id)

    try:
        await query.answer(get_text('terms_accept_success', user.id), show_alert=False)
    except Exception:
        pass

    await handle_terms(update, context, back_callback=back_callback)
