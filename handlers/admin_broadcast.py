from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import ADMIN_IDS
import logging
import asyncio
import html
import re
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

active_broadcasts = {}
_translation_cache = {}


async def _edit_or_send(query, text: str, reply_markup=None, parse_mode=None):
    try:
        return await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
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
            parse_mode=parse_mode
        )


def _render_broadcast_text(template: str | None, user_row) -> str | None:
    if not template:
        return template

    row = dict(user_row)
    user_id = row.get('user_id')
    first_name = row.get('first_name') or 'User'
    username = row.get('username') or ''
    mention = f'<a href="tg://user?id={user_id}">{html.escape(first_name)}</a>'

    return (
        template
        .replace('{mention}', mention)
        .replace('{first_name}', html.escape(first_name))
        .replace('{username}', html.escape(username))
        .replace('{user_id}', str(user_id))
    )


def _normalize_lang(lang: str | None) -> str:
    return lang if lang in {'ru', 'en', 'uk'} else 'ru'


def _translate_text_preserving_markup(text: str | None, source_lang: str, target_lang: str) -> str | None:
    if not text:
        return text

    source_lang = _normalize_lang(source_lang)
    target_lang = _normalize_lang(target_lang)
    if source_lang == target_lang:
        return text

    cache_key = (text, source_lang, target_lang)
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    token_map = {}

    def protect(pattern: str, current_text: str, prefix: str) -> str:
        def repl(match):
            token = f"__{prefix}_{len(token_map)}__"
            token_map[token] = match.group(0)
            return token
        return re.sub(pattern, repl, current_text)

    protected = text
    protected = protect(r'<[^>]+>', protected, 'HTML')
    protected = protect(r'\{mention\}|\{first_name\}|\{username\}|\{user_id\}', protected, 'VAR')

    try:
        translated = GoogleTranslator(source=source_lang, target=target_lang).translate(protected)
    except Exception as e:
        logger.warning(f"Broadcast translation failed {source_lang}->{target_lang}: {e}")
        translated = text
    else:
        for token, original in token_map.items():
            translated = translated.replace(token, original)

    _translation_cache[cache_key] = translated
    return translated


def _broadcast_keyboard(has_photo: bool = False, draft_id: int | None = None):
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить", callback_data='broadcast_send'),
            InlineKeyboardButton("✏️ Редактировать", callback_data='broadcast_edit')
        ],
        [
            InlineKeyboardButton("🖼 Обновить фото", callback_data='broadcast_add_photo'),
            InlineKeyboardButton("🗑 Удалить фото", callback_data='broadcast_remove_photo')
        ],
        [
            InlineKeyboardButton("💾 Сохранить черновик", callback_data='broadcast_save_draft'),
            InlineKeyboardButton("📚 Черновики", callback_data='broadcast_drafts')
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


async def _show_broadcast_preview(target_message, context: ContextTypes.DEFAULT_TYPE):
    text = context.user_data.get('broadcast_text')
    photo_file_id = context.user_data.get('broadcast_photo_file_id')

    if not text and not photo_file_id:
        await context.bot.send_message(target_message.chat_id, "❌ Черновик пустой.")
        return

    if text:
        preview_text = (
            text
            .replace('{mention}', '<a href="tg://user?id=123456789">User</a>')
            .replace('{first_name}', 'User')
            .replace('{username}', 'username')
            .replace('{user_id}', '123456789')
        )
        caption = (
            f"📢 <b>Предпросмотр рассылки</b>\n\n{preview_text}\n\n"
            f"<i>Так это увидят пользователи</i>"
        )
    else:
        caption = "📢 <b>Предпросмотр рассылки</b>\n\n<i>Так это увидят пользователи</i>"

    if photo_file_id:
        await context.bot.send_photo(
            chat_id=target_message.chat_id,
            photo=photo_file_id,
            caption=caption,
            reply_markup=_broadcast_keyboard(has_photo=True),
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=target_message.chat_id,
            text=caption,
            reply_markup=_broadcast_keyboard(has_photo=False),
            parse_mode='HTML'
        )


async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    if user.id not in ADMIN_IDS:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return

    drafts_count = len(db.get_broadcast_drafts())
    keyboard = [
        [InlineKeyboardButton("📢 Создать рассылку", callback_data='broadcast_create')],
        [InlineKeyboardButton(f"📚 Черновики ({drafts_count})", callback_data='broadcast_drafts')],
        [InlineKeyboardButton("📊 Статистика рассылок", callback_data='broadcast_stats')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]

    await _edit_or_send(query, 
        "📢 <b>Рассылки</b>\n\n"
        "Создавайте, сохраняйте в черновики и отправляйте позже.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def broadcast_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_row = db.get_user(user.id) or {}

    context.user_data.pop('broadcast_draft_id', None)
    context.user_data['broadcast_text'] = None
    context.user_data['broadcast_photo_file_id'] = None
    context.user_data['broadcast_source_lang'] = _normalize_lang(user_row.get('language'))
    db.set_pending_action(user.id, 'broadcast_text')

    await _edit_or_send(query, 
        "📢 <b>Создание рассылки</b>\n\n"
        "Введите текст рассылки.\n"
        "Можно использовать HTML-теги.\n"
        "После этого сможете добавить фото и сохранить черновик.\n\n"
        "Шаблоны: <code>{mention}</code>, <code>{first_name}</code>, "
        "<code>{username}</code>, <code>{user_id}</code>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]]),
        parse_mode='HTML'
    )


async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    user_row = db.get_user(user.id) or {}
    context.user_data['broadcast_text'] = text
    context.user_data['broadcast_source_lang'] = _normalize_lang(user_row.get('language'))
    db.clear_pending_action(user.id)
    await _show_broadcast_preview(update.message, context)


async def broadcast_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_row = db.get_user(user.id) or {}
    current_text = context.user_data.get('broadcast_text') or ''
    context.user_data['broadcast_source_lang'] = _normalize_lang(
        context.user_data.get('broadcast_source_lang') or user_row.get('language')
    )
    db.set_pending_action(user.id, 'broadcast_text')

    await _edit_or_send(query, 
        "✏️ <b>Редактирование рассылки</b>\n\n"
        f"Текущий текст:\n<code>{current_text[:500]}</code>\n\n"
        "Отправьте новый текст.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]]),
        parse_mode='HTML'
    )


async def broadcast_add_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    db.set_pending_action(user.id, 'broadcast_photo')
    await _edit_or_send(query, 
        "🖼 Отправьте фото для рассылки.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]])
    )


async def handle_broadcast_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте именно фото.")
        return

    context.user_data['broadcast_photo_file_id'] = update.message.photo[-1].file_id
    db.clear_pending_action(user.id)
    await update.message.reply_text("✅ Фото добавлено к рассылке.")
    await _show_broadcast_preview(update.message, context)


async def broadcast_remove_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['broadcast_photo_file_id'] = None
    await _edit_or_send(query, 
        "✅ Фото удалено из текущей рассылки.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👀 Вернуться к предпросмотру", callback_data='broadcast_preview_again')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_broadcast_menu')]
        ])
    )


async def broadcast_preview_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.message.delete()
    except Exception:
        pass
    await _show_broadcast_preview(query.message, context)


async def broadcast_save_draft_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    db.set_pending_action(user.id, 'broadcast_draft_title')
    await _edit_or_send(query, 
        "💾 Введите название черновика.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]])
    )


async def handle_broadcast_draft_title(update: Update, context: ContextTypes.DEFAULT_TYPE, title: str):
    user = update.effective_user
    draft_id = context.user_data.get('broadcast_draft_id')
    saved_id = db.save_broadcast_draft(
        title=title.strip() or f"Draft {datetime.now().strftime('%d.%m %H:%M')}",
        text=context.user_data.get('broadcast_text'),
        photo_file_id=context.user_data.get('broadcast_photo_file_id'),
        created_by=user.id,
        draft_id=draft_id
    )
    db.clear_pending_action(user.id)
    if saved_id:
        context.user_data['broadcast_draft_id'] = saved_id
        await update.message.reply_text(
            "✅ Черновик сохранён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 К черновикам", callback_data='broadcast_drafts')]])
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить черновик.")


async def broadcast_drafts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    drafts = db.get_broadcast_drafts()
    keyboard = []

    for draft in drafts:
        title = draft.get('title') or f"Draft #{draft['id']}"
        keyboard.append([
            InlineKeyboardButton(f"📄 {title}", callback_data=f"broadcast_load_draft_{draft['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"broadcast_delete_draft_{draft['id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_broadcast_menu')])

    await _edit_or_send(query, 
        "📚 <b>Черновики рассылок</b>\n\nВыберите черновик для открытия или удаления.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def broadcast_load_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, draft_id: int):
    query = update.callback_query
    user_row = db.get_user(query.from_user.id) or {}
    draft = db.get_broadcast_draft(draft_id)
    if not draft:
        await query.answer("Черновик не найден", show_alert=True)
        return

    context.user_data['broadcast_draft_id'] = draft['id']
    context.user_data['broadcast_text'] = draft.get('text')
    context.user_data['broadcast_photo_file_id'] = draft.get('photo_file_id')
    context.user_data['broadcast_source_lang'] = _normalize_lang(user_row.get('language'))

    try:
        await query.message.delete()
    except Exception:
        pass
    await _show_broadcast_preview(query.message, context)


async def broadcast_delete_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, draft_id: int):
    query = update.callback_query
    ok = db.delete_broadcast_draft(draft_id)
    await query.answer("Черновик удалён" if ok else "Не удалось удалить", show_alert=True)
    await broadcast_drafts_menu(update, context)


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    sender_row = db.get_user(user.id) or {}

    text = context.user_data.get('broadcast_text')
    photo_file_id = context.user_data.get('broadcast_photo_file_id')
    source_lang = _normalize_lang(context.user_data.get('broadcast_source_lang') or sender_row.get('language'))
    if not text and not photo_file_id:
        await _edit_or_send(query, "❌ Ошибка: рассылка пустая")
        return

    await _edit_or_send(query, 
        "📢 <b>Рассылка началась!</b>\n\n"
        "⏳ Идет отправка...",
        parse_mode='HTML'
    )

    users = db.execute("SELECT user_id, username, first_name, language FROM users", fetch=True) or []
    total = len(users)
    success = 0
    failed = 0
    blocked = 0

    broadcast_id = str(user.id) + '_' + str(datetime.now().timestamp())
    active_broadcasts[broadcast_id] = {'active': True, 'cancelled': False}

    for i, user_row in enumerate(users):
        if broadcast_id in active_broadcasts and active_broadcasts[broadcast_id].get('cancelled'):
            break

        row = dict(user_row)
        user_id = row['user_id']
        translated_text = _translate_text_preserving_markup(text, source_lang, row.get('language'))
        rendered_text = _render_broadcast_text(translated_text, row)
        try:
            if photo_file_id:
                await context.bot.send_photo(
                    user_id,
                    photo=photo_file_id,
                    caption=rendered_text or None,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    user_id,
                    rendered_text,
                    parse_mode='HTML'
                )
            success += 1
        except Exception as e:
            if "blocked" in str(e).lower():
                blocked += 1
            else:
                failed += 1
                logger.error(f"Broadcast send failed for {user_id}: {e}")

        await asyncio.sleep(0.05)

        if i % 100 == 0 and i > 0:
            try:
                await _edit_or_send(query, 
                    f"📢 <b>Рассылка...</b>\n\n"
                    f"📊 Прогресс: {i}/{total}\n"
                    f"✅ Успешно: {success}\n"
                    f"🚫 Заблокировали: {blocked}\n"
                    f"❌ Ошибок: {failed}",
                    parse_mode='HTML'
                )
            except Exception:
                pass

    if broadcast_id in active_broadcasts:
        del active_broadcasts[broadcast_id]

    delivered_pct = (success / total * 100) if total else 0
    report = (
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"📊 Всего пользователей: {total}\n"
        f"✅ Успешно доставлено: {success}\n"
        f"🚫 Заблокировали бота: {blocked}\n"
        f"❌ Ошибок отправки: {failed}\n\n"
        f"📈 Доставлено: {success}/{total} ({delivered_pct:.1f}%)"
    )

    await context.bot.send_message(user.id, report, parse_mode='HTML')
    context.user_data.clear()
    db.clear_pending_action(user.id)


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    for bid, data in active_broadcasts.items():
        if bid.startswith(str(user.id)):
            data['cancelled'] = True
            await _edit_or_send(query, "✅ Рассылка отменена")
            return

    context.user_data.clear()
    db.clear_pending_action(user.id)
    await _edit_or_send(query, "✅ Создание рассылки отменено")


async def broadcast_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    total_row = db.execute("SELECT COUNT(*) as count FROM users", fetch=True)[0]
    total_users = total_row['count'] if db.use_postgres else total_row[0]

    active_today_row = db.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(last_active) = DATE(?)",
        (datetime.now().date().isoformat(),),
        fetch=True
    )[0]
    active_today = active_today_row['count'] if db.use_postgres else active_today_row[0]

    drafts_count = len(db.get_broadcast_drafts())
    text = (
        f"📊 <b>Статистика рассылок</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🟢 Активных сегодня: {active_today}\n"
        f"💾 Черновиков: {drafts_count}\n"
        f"📈 Процент активности: {(active_today / total_users * 100) if total_users else 0:.1f}%"
    )

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_broadcast_menu')]]
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
