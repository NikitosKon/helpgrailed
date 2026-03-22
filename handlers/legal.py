from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db
from keyboards.reply import get_text


async def _edit_or_send(query, text, reply_markup=None, parse_mode=None, **kwargs):
    try:
        return await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )


async def _send_terms_with_optional_photo(
    query,
    title: str,
    text: str,
    core_key: str,
    reply_markup=None,
    parse_mode=None,
    **kwargs,
):
    photo_file_id = (db.get_main_menu_core().get(core_key, {}) or {}).get("photo_file_id")
    if not photo_file_id:
        return await _edit_or_send(query, text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)

    try:
        await query.get_bot().send_photo(
            chat_id=query.message.chat_id,
            photo=photo_file_id,
            caption=title,
            parse_mode=parse_mode,
            **kwargs,
        )
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
    except Exception:
        return await _edit_or_send(query, text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)


async def handle_terms(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    back_callback: str = "menu",
    agree_callback: str | None = None,
):
    query = update.callback_query
    user = query.from_user
    title = f"<b>{get_text('terms_title', user.id)}</b>"
    text = f"{title}\n\n{get_text('terms_text', user.id)}"
    rows = []
    if agree_callback:
        rows.append([InlineKeyboardButton(get_text("terms_accept_button", user.id), callback_data=agree_callback)])
    rows.append([InlineKeyboardButton(get_text("back", user.id), callback_data=back_callback)])
    keyboard = InlineKeyboardMarkup(rows)

    await _send_terms_with_optional_photo(
        query,
        title,
        text,
        "terms",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def handle_terms_accept(update: Update, context: ContextTypes.DEFAULT_TYPE, back_callback: str = "profile"):
    query = update.callback_query
    user = query.from_user
    db.accept_terms(user.id)

    try:
        await query.answer(get_text("terms_accept_success", user.id), show_alert=False)
    except Exception:
        pass

    await handle_terms(update, context, back_callback=back_callback)
