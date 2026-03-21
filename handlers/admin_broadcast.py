from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import ADMIN_IDS
import logging
import asyncio

logger = logging.getLogger(__name__)

active_broadcasts = {}


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
        await target_message.reply_text("❌ Черновик пустой.")
        return

    caption = None
    if text:
        caption = f"📢 <b>Предпросмотр рассылки</b>\n\n{text}\n\n<i>Так это увидят пользователи</i>"
    else:
        caption = "📢 <b>Предпросмотр рассылки</b>\n\n<i>Так это увидят пользователи</i>"

    if photo_file_id:
        await target_message.reply_photo(
            photo=photo_file_id,
            caption=caption,
            reply_markup=_broadcast_keyboard(has_photo=True),
            parse_mode='HTML'
        )
    else:
        await target_message.reply_text(
            caption,
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

    await query.edit_message_text(
        "📢 <b>Рассылки</b>\n\n"
        "Создавайте, сохраняйте в черновики и отправляйте позже.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def broadcast_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    context.user_data.pop('broadcast_draft_id', None)
    context.user_data['broadcast_text'] = None
    context.user_data['broadcast_photo_file_id'] = None
    db.set_pending_action(user.id, 'broadcast_text')

    await query.edit_message_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Введите текст рассылки.\n"
        "Можно использовать HTML-теги.\n"
        "После этого сможете добавить фото и сохранить черновик.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]]),
        parse_mode='HTML'
    )


async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    context.user_data['broadcast_text'] = text
    db.clear_pending_action(user.id)
    await _show_broadcast_preview(update.message, context)


async def broadcast_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    current_text = context.user_data.get('broadcast_text') or ''
    db.set_pending_action(user.id, 'broadcast_text')

    await query.edit_message_text(
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
    await query.edit_message_text(
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
    await query.edit_message_text(
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
    await query.edit_message_text(
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

    await query.edit_message_text(
        "📚 <b>Черновики рассылок</b>\n\nВыберите черновик для открытия или удаления.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def broadcast_load_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, draft_id: int):
    query = update.callback_query
    draft = db.get_broadcast_draft(draft_id)
    if not draft:
        await query.answer("Черновик не найден", show_alert=True)
        return

    context.user_data['broadcast_draft_id'] = draft['id']
    context.user_data['broadcast_text'] = draft.get('text')
    context.user_data['broadcast_photo_file_id'] = draft.get('photo_file_id')

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

    text = context.user_data.get('broadcast_text')
    photo_file_id = context.user_data.get('broadcast_photo_file_id')
    if not text and not photo_file_id:
        await query.edit_message_text("❌ Ошибка: рассылка пустая")
        return

    await query.edit_message_text(
        "📢 <b>Рассылка началась!</b>\n\n"
        "⏳ Идет отправка...",
        parse_mode='HTML'
    )

    users = db.execute("SELECT user_id FROM users", fetch=True) or []
    total = len(users)
    success = 0
    failed = 0
    blocked = 0

    broadcast_id = str(user.id) + '_' + str(datetime.now().timestamp())
    active_broadcasts[broadcast_id] = {'active': True, 'cancelled': False}

    for i, user_row in enumerate(users):
        if broadcast_id in active_broadcasts and active_broadcasts[broadcast_id].get('cancelled'):
            break

        user_id = user_row['user_id'] if db.use_postgres else user_row[0]
        try:
            if photo_file_id:
                await context.bot.send_photo(
                    user_id,
                    photo=photo_file_id,
                    caption=text or None,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    user_id,
                    text,
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
                await query.edit_message_text(
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
            await query.edit_message_text("✅ Рассылка отменена")
            return

    context.user_data.clear()
    db.clear_pending_action(user.id)
    await query.edit_message_text("✅ Создание рассылки отменено")


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
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
