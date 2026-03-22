from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db

import logging

logger = logging.getLogger(__name__)


async def _edit_or_send(query, text, reply_markup=None, parse_mode=None, **kwargs):
    try:
        return await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    except Exception as e:
        if 'There is no text in the message to edit' not in str(e):
            raise
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )

async def _edit_or_send_with_core_photo(query, text, core_key: str, reply_markup=None, parse_mode=None, **kwargs):
    photo_file_id = (db.get_main_menu_core().get(core_key, {}) or {}).get('photo_file_id')
    if not photo_file_id:
        return await _edit_or_send(query, text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)

    try:
        await query.message.delete()
    except Exception:
        pass
    return await query.get_bot().send_photo(
        chat_id=query.message.chat_id,
        photo=photo_file_id,
        caption=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        **kwargs
    )



async def handle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    db.set_pending_action(user.id, 'enter_promo')
    await _edit_or_send_with_core_photo(
        query,
        "🎫 <b>Введите промокод</b>\n\nОтправьте промокод в чат:",
        'promo_code',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='balance')
        ]]),
        parse_mode='HTML'
    )
