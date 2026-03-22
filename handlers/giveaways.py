import html
import logging
from datetime import datetime
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import db
from keyboards.reply import get_text

logger = logging.getLogger(__name__)


def _parse_dt(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _fmt_dt(value: str) -> str:
    dt = _parse_dt(value)
    return dt.strftime("%d.%m.%Y %H:%M") if dt else (value or "—")


def _normalize_channel(value: str) -> Optional[str]:
    value = (value or "").strip()
    if not value or value == "/skip":
        return None
    if "t.me/" in value:
        value = value.split("t.me/", 1)[1]
    value = value.strip("/")
    if not value.startswith("@"):
        value = f"@{value}"
    return value


def _prize_label(giveaway: dict) -> str:
    prize_type = giveaway.get("prize_type")
    prize_value = giveaway.get("prize_value") or "—"
    if prize_type == "balance":
        return f"Баланс: ${float(prize_value):.2f}" if str(prize_value).replace(".", "", 1).isdigit() else f"Баланс: {prize_value}"
    if prize_type == "product":
        return f"Товар ID: {prize_value}"
    if prize_type == "promo":
        return f"Промокод: {prize_value}"
    return f"Текст: {prize_value}"


def _giveaway_public_text(giveaway: dict, user_id: Optional[int] = None) -> str:
    giveaway_id = int(giveaway["id"])
    entries = db.get_giveaway_entries(giveaway_id)
    entered = db.has_entered_giveaway(giveaway_id, user_id) if user_id else False
    return (
        f"🎁 <b>{html.escape(giveaway.get('title') or 'Розыгрыш')}</b>\n\n"
        f"{html.escape(giveaway.get('description') or '-')}\n\n"
        f"🏁 До: {_fmt_dt(giveaway.get('ends_at'))}\n"
        f"🏆 Победителей: {giveaway.get('winners_count', 1)}\n"
        f"🎁 Приз: {_prize_label(giveaway)}\n"
        f"👥 Участников: {len(entries)}\n"
        f"Ваш статус: {'✅ участвуете' if entered else '— не участвуете'}"
    )


def _giveaway_public_keyboard(giveaway: dict, entered: bool = False, back_callback: str = "giveaways") -> InlineKeyboardMarkup:
    giveaway_id = int(giveaway["id"])
    keyboard = []
    if not entered:
        keyboard.append([InlineKeyboardButton("🎟 Участвовать", callback_data=f"giveaway_join_{giveaway_id}")])
    if giveaway.get("public_participants"):
        keyboard.append([InlineKeyboardButton("👥 Список участников", callback_data=f"giveaway_participants_{giveaway_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)


async def _publish_giveaway_preview(
    context: ContextTypes.DEFAULT_TYPE,
    giveaway: dict,
    chat_id: int,
    *,
    reply_to_message_id: Optional[int] = None,
) -> bool:
    text = _giveaway_public_text(giveaway)
    reply_markup = _giveaway_public_keyboard(giveaway, entered=False)

    try:
        if giveaway.get("photo_file_id"):
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=giveaway.get("photo_file_id"),
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
            )
        return True
    except Exception as e:
        logger.error(f"Failed to publish giveaway preview {giveaway.get('id')}: {e}")
        return False


def _giveaway_status_label(status: str) -> str:
    return {
        "active": "🟢 Активен",
        "completed": "✅ Завершён",
        "cancelled": "⛔ Остановлен",
    }.get(status, status)


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


async def _send_photo_or_text(query, text, photo_file_id=None, reply_markup=None, parse_mode=None, **kwargs):
    if not photo_file_id:
        return await _edit_or_send(query, text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)

    try:
        sent_message = await query.get_bot().send_photo(
            chat_id=query.message.chat_id,
            photo=photo_file_id,
            caption=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
        try:
            await query.message.delete()
        except Exception:
            pass
        return sent_message
    except Exception:
        return await _edit_or_send(query, text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)


def _ensure_form(context: ContextTypes.DEFAULT_TYPE) -> dict:
    form = context.user_data.get("giveaway_form")
    if not isinstance(form, dict):
        form = {}
        context.user_data["giveaway_form"] = form
    return form


def _clear_form(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("giveaway_form", None)


def _admin_card_text(giveaway: dict) -> str:
    entries = db.get_giveaway_entries(giveaway["id"])
    winners = db.get_giveaway_winners(giveaway["id"])
    return (
        f"🎁 <b>{html.escape(giveaway.get('title') or 'Без названия')}</b>\n\n"
        f"ID: <code>{giveaway['id']}</code>\n"
        f"Статус: {_giveaway_status_label(giveaway.get('status') or 'active')}\n"
        f"Заканчивается: {_fmt_dt(giveaway.get('ends_at'))}\n"
        f"Победителей: {giveaway.get('winners_count', 1)}\n"
        f"Приз: {_prize_label(giveaway)}\n"
        f"Участников: {len(entries)}\n"
        f"Победителей выбрано: {len(winners)}\n"
        f"Публикация: {'да' if giveaway.get('published') else 'нет'}\n"
        f"Кнопка в меню: {'да' if giveaway.get('published_in_menu') else 'нет'}\n"
        f"Автовыбор: {'да' if giveaway.get('auto_draw') else 'нет'}\n"
        f"Публичные участники: {'да' if giveaway.get('public_participants') else 'нет'}\n"
        f"Мин. баланс: ${float(giveaway.get('min_balance') or 0):.2f}\n"
        f"Мин. покупок: {int(giveaway.get('min_purchases') or 0)}\n"
        f"Канал: {html.escape(giveaway.get('required_channel') or 'не требуется')}\n\n"
        f"{html.escape(giveaway.get('description') or '-')}"
    )


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    for admin_id in db.get_admin_ids() or ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass


async def _award_prize(context: ContextTypes.DEFAULT_TYPE, giveaway: dict, user_id: int) -> str:
    prize_type = giveaway.get("prize_type")
    prize_value = giveaway.get("prize_value") or ""

    if prize_type == "balance":
        amount = float(prize_value or 0)
        if db.award_giveaway_balance(user_id, amount, giveaway["id"]):
            db.mark_giveaway_prize_awarded(giveaway["id"], user_id)
            return f"На ваш баланс начислено ${amount:.2f}."
        return "Не удалось автоматически начислить баланс."

    if prize_type == "product":
        try:
            product_id = int(prize_value)
        except Exception:
            return "Не удалось выдать товар: некорректный ID."
        ok, product = db.award_giveaway_product(user_id, product_id, giveaway["id"])
        if ok:
            db.mark_giveaway_prize_awarded(giveaway["id"], user_id)
            product_name = (product or {}).get("name") or f"#{product_id}"
            return f"Вам автоматически выдан товар: {product_name}."
        return "Не удалось автоматически выдать товар."

    db.mark_giveaway_prize_awarded(giveaway["id"], user_id)
    if prize_type == "promo":
        return f"Ваш приз: промокод <code>{html.escape(prize_value)}</code>."
    return html.escape(prize_value or "Поздравляем с победой!")


async def finalize_giveaway(context: ContextTypes.DEFAULT_TYPE, giveaway_id: int, forced: bool = False) -> bool:
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get("status") != "active":
        return False

    if not forced:
        ends_at = _parse_dt(giveaway.get("ends_at"))
        if ends_at and ends_at > datetime.now():
            return False

    winners = db.draw_giveaway_winners(giveaway_id, int(giveaway.get("winners_count") or 1))
    giveaway = db.get_giveaway(giveaway_id) or giveaway

    if not winners:
        await _notify_admins(
            context,
            f"🎁 <b>Розыгрыш завершён без победителей</b>\n\n<b>{html.escape(giveaway.get('title') or '')}</b>\nID: <code>{giveaway_id}</code>",
        )
        return True

    lines = []
    for winner in winners:
        user_id = int(winner["user_id"])
        reward_text = await _award_prize(context, giveaway, user_id)
        try:
            await context.bot.send_message(
                user_id,
                f"🎉 <b>Вы победили в розыгрыше!</b>\n\n"
                f"<b>{html.escape(giveaway.get('title') or '')}</b>\n"
                f"{reward_text}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify giveaway winner {user_id}: {e}")
        username = winner.get("username")
        lines.append(f"• @{username}" if username else f"• ID {user_id}")

    await _notify_admins(
        context,
        f"🎁 <b>Розыгрыш завершён</b>\n\n"
        f"<b>{html.escape(giveaway.get('title') or '')}</b>\n"
        f"ID: <code>{giveaway_id}</code>\n"
        f"Победители:\n" + "\n".join(lines),
    )
    return True


async def process_due_giveaways(context: ContextTypes.DEFAULT_TYPE):
    for giveaway in db.get_due_auto_giveaways():
        try:
            await finalize_giveaway(context, int(giveaway["id"]), forced=False)
        except Exception as e:
            logger.error(f"Failed to auto-finish giveaway {giveaway.get('id')}: {e}")


async def admin_giveaways_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    active = len(db.get_giveaways(status="active"))
    completed = len(db.get_giveaways(status="completed"))
    keyboard = [
        [InlineKeyboardButton("➕ Создать розыгрыш", callback_data="admin_giveaway_create")],
        [InlineKeyboardButton(f"🟢 Активные ({active})", callback_data="admin_giveaway_list_active")],
        [InlineKeyboardButton(f"✅ Завершённые ({completed})", callback_data="admin_giveaway_list_completed")],
        [InlineKeyboardButton("📋 Все розыгрыши", callback_data="admin_giveaway_list_all")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin")],
    ]
    await _edit_or_send(
        query,
        "🎁 <b>Розыгрыши</b>\n\nЗдесь можно создавать и управлять розыгрышами.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def admin_giveaway_list(update: Update, context: ContextTypes.DEFAULT_TYPE, status: Optional[str]):
    query = update.callback_query
    giveaways = db.get_giveaways(status=status if status != "all" else None)
    if not giveaways:
        await _edit_or_send(
            query,
            "📭 Розыгрышей пока нет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_giveaways")]]),
        )
        return

    keyboard = []
    for item in giveaways[:50]:
        status_icon = "🟢" if item.get("status") == "active" else "✅"
        keyboard.append([InlineKeyboardButton(f"{status_icon} {item.get('title')}", callback_data=f"admin_giveaway_view_{item['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_giveaways")])
    await _edit_or_send(
        query,
        "🎁 <b>Список розыгрышей</b>\n\nВыберите розыгрыш:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def admin_giveaway_view(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    query = update.callback_query
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway:
        await query.answer("Розыгрыш не найден", show_alert=True)
        return

    keyboard = [
        [
            InlineKeyboardButton("👥 Участники", callback_data=f"admin_giveaway_entries_{giveaway_id}"),
            InlineKeyboardButton("🏆 Победители", callback_data=f"admin_giveaway_winners_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton("📝 Заголовок", callback_data=f"admin_giveaway_edit_title_{giveaway_id}"),
            InlineKeyboardButton("📄 Текст", callback_data=f"admin_giveaway_edit_description_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton("🖼 Фото", callback_data=f"admin_giveaway_edit_photo_{giveaway_id}"),
            InlineKeyboardButton("🗑 Удалить фото", callback_data=f"admin_giveaway_photo_remove_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton("⏰ Дата", callback_data=f"admin_giveaway_edit_ends_at_{giveaway_id}"),
            InlineKeyboardButton("🏆 Кол-во побед.", callback_data=f"admin_giveaway_edit_winners_count_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton("🎁 Приз", callback_data=f"admin_giveaway_edit_prize_value_{giveaway_id}"),
            InlineKeyboardButton("📢 Канал", callback_data=f"admin_giveaway_edit_required_channel_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton("💰 Мин. баланс", callback_data=f"admin_giveaway_edit_min_balance_{giveaway_id}"),
            InlineKeyboardButton("🧾 Мин. покупок", callback_data=f"admin_giveaway_edit_min_purchases_{giveaway_id}"),
        ],
        [
            InlineKeyboardButton(
                "📌 В меню: да" if giveaway.get("published_in_menu") else "📌 В меню: нет",
                callback_data=f"admin_giveaway_toggle_menu_{giveaway_id}",
            ),
            InlineKeyboardButton(
                "👀 Публичный список: да" if giveaway.get("public_participants") else "👀 Публичный список: нет",
                callback_data=f"admin_giveaway_toggle_public_{giveaway_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🤖 Автовыбор: да" if giveaway.get("auto_draw") else "🤖 Автовыбор: нет",
                callback_data=f"admin_giveaway_toggle_auto_{giveaway_id}",
            ),
            InlineKeyboardButton(
                "✅ Опубликован" if giveaway.get("published") else "📝 Скрыт",
                callback_data=f"admin_giveaway_toggle_publish_{giveaway_id}",
            ),
        ],
    ]
    if giveaway.get("status") == "active":
        keyboard.append([InlineKeyboardButton("🏁 Завершить и выбрать победителей", callback_data=f"admin_giveaway_finish_{giveaway_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_giveaways")])

    await _send_photo_or_text(
        query,
        _admin_card_text(giveaway),
        photo_file_id=giveaway.get("photo_file_id"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def admin_giveaway_entries(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int, winners_only: bool = False):
    query = update.callback_query
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway:
        await query.answer("Розыгрыш не найден", show_alert=True)
        return
    entries = db.get_giveaway_winners(giveaway_id) if winners_only else db.get_giveaway_entries(giveaway_id)
    title = "Победители" if winners_only else "Участники"
    if not entries:
        text = f"📭 {title.lower()} пока нет."
    else:
        lines = []
        for idx, item in enumerate(entries[:100], start=1):
            username = item.get("username")
            label = f"@{username}" if username else f"ID {item.get('user_id')}"
            first_name = item.get("first_name")
            extra = f" ({first_name})" if first_name else ""
            lines.append(f"{idx}. {label}{extra}")
        text = f"👥 <b>{title}</b>\n\n" + "\n".join(lines)
    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_giveaway_view_{giveaway_id}")]]),
        parse_mode="HTML",
    )


async def admin_giveaway_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _clear_form(context)
    db.set_pending_action(query.from_user.id, "admin_giveaway_create_title")
    await _edit_or_send(
        query,
        "➕ <b>Создание розыгрыша</b>\n\nВведите заголовок розыгрыша:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_giveaways")]]),
        parse_mode="HTML",
    )


async def handle_admin_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user = query.from_user

    if data == "admin_giveaways":
        await admin_giveaways_menu(update, context)
        return
    if data == "admin_giveaway_create":
        await admin_giveaway_create_start(update, context)
        return
    if data == "admin_giveaway_list_active":
        await admin_giveaway_list(update, context, "active")
        return
    if data == "admin_giveaway_list_completed":
        await admin_giveaway_list(update, context, "completed")
        return
    if data == "admin_giveaway_list_all":
        await admin_giveaway_list(update, context, "all")
        return
    if data.startswith("admin_giveaway_view_"):
        await admin_giveaway_view(update, context, int(data.replace("admin_giveaway_view_", "")))
        return
    if data.startswith("admin_giveaway_entries_"):
        await admin_giveaway_entries(update, context, int(data.replace("admin_giveaway_entries_", "")), winners_only=False)
        return
    if data.startswith("admin_giveaway_winners_"):
        await admin_giveaway_entries(update, context, int(data.replace("admin_giveaway_winners_", "")), winners_only=True)
        return
    if data.startswith("admin_giveaway_finish_"):
        giveaway_id = int(data.replace("admin_giveaway_finish_", ""))
        await finalize_giveaway(context, giveaway_id, forced=True)
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_toggle_menu_"):
        giveaway_id = int(data.replace("admin_giveaway_toggle_menu_", ""))
        giveaway = db.get_giveaway(giveaway_id) or {}
        db.update_giveaway(giveaway_id, published_in_menu=0 if giveaway.get("published_in_menu") else 1)
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_toggle_public_"):
        giveaway_id = int(data.replace("admin_giveaway_toggle_public_", ""))
        giveaway = db.get_giveaway(giveaway_id) or {}
        db.update_giveaway(giveaway_id, public_participants=0 if giveaway.get("public_participants") else 1)
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_toggle_auto_"):
        giveaway_id = int(data.replace("admin_giveaway_toggle_auto_", ""))
        giveaway = db.get_giveaway(giveaway_id) or {}
        db.update_giveaway(giveaway_id, auto_draw=0 if giveaway.get("auto_draw") else 1)
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_toggle_publish_"):
        giveaway_id = int(data.replace("admin_giveaway_toggle_publish_", ""))
        giveaway = db.get_giveaway(giveaway_id) or {}
        new_published = 0 if giveaway.get("published") else 1
        db.update_giveaway(giveaway_id, published=new_published)
        if new_published:
            refreshed = db.get_giveaway(giveaway_id)
            if refreshed:
                await _publish_giveaway_preview(
                    context,
                    refreshed,
                    query.message.chat_id,
                    reply_to_message_id=query.message.message_id,
                )
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_edit_"):
        payload = data.replace("admin_giveaway_edit_", "", 1)
        field, giveaway_id = payload.rsplit("_", 1)
        db.set_pending_action(user.id, f"admin_giveaway_edit_{field}_{giveaway_id}")
        prompts = {
            "title": "Введите новый заголовок:",
            "description": "Введите новый текст розыгрыша:",
            "ends_at": "Введите новую дату окончания в формате ДД.ММ.ГГГГ ЧЧ:ММ",
            "photo": "Отправьте новое фото.",
            "winners_count": "Введите новое количество победителей:",
            "prize_value": "Введите новое значение приза.\nДля balance: сумма\nДля product: ID товара\nДля promo: код\nДля text: текст приза",
            "required_channel": "Введите @канал или ссылку. /skip чтобы убрать требование.",
            "min_balance": "Введите минимальный баланс или 0",
            "min_purchases": "Введите минимальное число покупок или 0",
        }
        await _edit_or_send(
            query,
            prompts.get(field, "Введите новое значение:"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_giveaway_view_{giveaway_id}")]]),
        )
        return
    if data.startswith("admin_giveaway_photo_remove_"):
        giveaway_id = int(data.replace("admin_giveaway_photo_remove_", ""))
        db.update_giveaway(giveaway_id, photo_file_id=None)
        await admin_giveaway_view(update, context, giveaway_id)
        return
    if data.startswith("admin_giveaway_prize_"):
        prize_type = data.replace("admin_giveaway_prize_", "", 1)
        form = _ensure_form(context)
        form["prize_type"] = prize_type
        db.set_pending_action(user.id, "admin_giveaway_create_prize_value")
        await _edit_or_send(
            query,
            "Введите значение приза.\n"
            "balance: сумма в долларах\n"
            "product: ID товара\n"
            "promo: код промокода\n"
            "text: текст приза",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_giveaways")]]),
        )
        return
    if data.startswith("admin_giveaway_public_"):
        form = _ensure_form(context)
        form["public_participants"] = 1 if data.endswith("_1") else 0
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="admin_giveaway_auto_1")],
            [InlineKeyboardButton("Нет", callback_data="admin_giveaway_auto_0")],
        ]
        await _edit_or_send(query, "Автоматически выбирать победителя по дате?", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if data.startswith("admin_giveaway_auto_"):
        form = _ensure_form(context)
        form["auto_draw"] = 1 if data.endswith("_1") else 0
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="admin_giveaway_menu_1")],
            [InlineKeyboardButton("Нет", callback_data="admin_giveaway_menu_0")],
        ]
        await _edit_or_send(query, "Показывать розыгрыш в главном меню?", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if data.startswith("admin_giveaway_menu_"):
        form = _ensure_form(context)
        form["published_in_menu"] = 1 if data.endswith("_1") else 0
        giveaway_id = db.create_giveaway(
            title=form.get("title") or "Розыгрыш",
            description=form.get("description") or "",
            ends_at=form.get("ends_at"),
            prize_type=form.get("prize_type") or "text",
            prize_value=form.get("prize_value"),
            created_by=user.id,
            photo_file_id=form.get("photo_file_id"),
            required_channel=form.get("required_channel"),
            min_balance=float(form.get("min_balance") or 0),
            min_purchases=int(form.get("min_purchases") or 0),
            winners_count=int(form.get("winners_count") or 1),
            public_participants=int(form.get("public_participants") or 0),
            auto_draw=int(form.get("auto_draw") or 0),
            published=1,
            published_in_menu=int(form.get("published_in_menu") or 0),
        )
        _clear_form(context)
        db.clear_pending_action(user.id)
        if giveaway_id:
            giveaway = db.get_giveaway(giveaway_id)
            if giveaway:
                await _publish_giveaway_preview(
                    context,
                    giveaway,
                    query.message.chat_id,
                    reply_to_message_id=query.message.message_id,
                )
            await admin_giveaway_view(update, context, giveaway_id)
        else:
            await _edit_or_send(query, "❌ Не удалось создать розыгрыш.")


async def process_admin_giveaway_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    message = update.message
    form = _ensure_form(context)

    if action == "admin_giveaway_create_title":
        form["title"] = text
        db.set_pending_action(user.id, "admin_giveaway_create_description")
        await message.reply_text("Введите текст розыгрыша:")
        return
    if action == "admin_giveaway_create_description":
        form["description"] = text
        db.set_pending_action(user.id, "admin_giveaway_create_photo")
        await message.reply_text("Отправьте фото для розыгрыша или напишите /skip")
        return
    if action == "admin_giveaway_create_photo":
        if text == "/skip":
            form["photo_file_id"] = None
            db.set_pending_action(user.id, "admin_giveaway_create_ends_at")
            await message.reply_text("Введите дату окончания в формате ДД.ММ.ГГГГ ЧЧ:ММ")
            return
        await message.reply_text("Ожидается фото или /skip.")
        return
    if action == "admin_giveaway_create_ends_at":
        dt = _parse_dt(text)
        if not dt:
            await message.reply_text("Некорректная дата. Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
            return
        form["ends_at"] = dt.isoformat()
        db.set_pending_action(user.id, "admin_giveaway_create_winners_count")
        await message.reply_text("Введите количество победителей:")
        return
    if action == "admin_giveaway_create_winners_count":
        try:
            form["winners_count"] = max(1, int(text))
        except Exception:
            await message.reply_text("Введите число больше или равное 1.")
            return
        db.clear_pending_action(user.id)
        keyboard = [
            [InlineKeyboardButton("💰 Баланс", callback_data="admin_giveaway_prize_balance")],
            [InlineKeyboardButton("📦 Товар", callback_data="admin_giveaway_prize_product")],
            [InlineKeyboardButton("🎫 Промокод", callback_data="admin_giveaway_prize_promo")],
            [InlineKeyboardButton("📝 Текст", callback_data="admin_giveaway_prize_text")],
        ]
        await message.reply_text("Выберите тип приза:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if action == "admin_giveaway_create_prize_value":
        form["prize_value"] = text if text != "/skip" else None
        db.set_pending_action(user.id, "admin_giveaway_create_required_channel")
        await message.reply_text("Введите @канал или ссылку для обязательной подписки, либо /skip")
        return
    if action == "admin_giveaway_create_required_channel":
        form["required_channel"] = _normalize_channel(text)
        db.set_pending_action(user.id, "admin_giveaway_create_min_balance")
        await message.reply_text("Введите минимальный баланс для участия или 0")
        return
    if action == "admin_giveaway_create_min_balance":
        try:
            form["min_balance"] = max(0, float(text))
        except Exception:
            await message.reply_text("Введите число 0 или больше.")
            return
        db.set_pending_action(user.id, "admin_giveaway_create_min_purchases")
        await message.reply_text("Введите минимальное число покупок или 0")
        return
    if action == "admin_giveaway_create_min_purchases":
        try:
            form["min_purchases"] = max(0, int(text))
        except Exception:
            await message.reply_text("Введите целое число 0 или больше.")
            return
        db.clear_pending_action(user.id)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="admin_giveaway_public_1")],
            [InlineKeyboardButton("Нет", callback_data="admin_giveaway_public_0")],
        ]
        await message.reply_text("Показывать участников пользователям?", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if action.startswith("admin_giveaway_edit_"):
        payload = action.replace("admin_giveaway_edit_", "", 1)
        field, giveaway_id = payload.rsplit("_", 1)
        giveaway_id = int(giveaway_id)
        if field == "ends_at":
            dt = _parse_dt(text)
            if not dt:
                await message.reply_text("Некорректная дата. Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
                return
            value = dt.isoformat()
        elif field == "required_channel":
            value = _normalize_channel(text)
        elif field == "min_balance":
            try:
                value = max(0, float(text))
            except Exception:
                await message.reply_text("Введите число 0 или больше.")
                return
        elif field in {"min_purchases", "winners_count"}:
            try:
                value = max(0 if field == "min_purchases" else 1, int(text))
            except Exception:
                await message.reply_text("Введите корректное число.")
                return
        elif field == "photo":
            await message.reply_text("Send a photo instead of text.")
            return
        else:
            value = text if text != "/skip" else None
        db.update_giveaway(giveaway_id, **{field: value})
        db.clear_pending_action(user.id)
        await message.reply_text(
            "✅ Обновлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_giveaway_view_{giveaway_id}")]]),
        )


async def handle_admin_giveaway_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    pending = db.get_pending_action(user.id)
    if not pending or not message.photo:
        return

    action = pending[0]
    photo_file_id = message.photo[-1].file_id

    if action == "admin_giveaway_create_photo":
        form = _ensure_form(context)
        form["photo_file_id"] = photo_file_id
        db.set_pending_action(user.id, "admin_giveaway_create_ends_at")
        await message.reply_text("✅ Фото сохранено.\nВведите дату окончания в формате ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    if action.startswith("admin_giveaway_edit_photo_"):
        giveaway_id = int(action.replace("admin_giveaway_edit_photo_", ""))
        db.update_giveaway(giveaway_id, photo_file_id=photo_file_id)
        db.clear_pending_action(user.id)
        await message.reply_text(
            "✅ Фото обновлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_giveaway_view_{giveaway_id}")]]),
        )


async def handle_giveaways(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    giveaways = db.get_giveaways(status="active", published_only=True, menu_only=True)
    if not giveaways:
        await _edit_or_send(
            query,
            "🎁 Сейчас активных розыгрышей нет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", query.from_user.id), callback_data="menu")]]),
        )
        return
    keyboard = [[InlineKeyboardButton(item.get("title") or "Розыгрыш", callback_data=f"giveaway_{item['id']}")] for item in giveaways[:30]]
    keyboard.append([InlineKeyboardButton(get_text("back", query.from_user.id), callback_data="menu")])
    await _edit_or_send(
        query,
        "🎁 <b>Розыгрыши</b>\n\nВыберите розыгрыш:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def handle_giveaway_view(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    query = update.callback_query
    user = query.from_user
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get("status") != "active" or not giveaway.get("published"):
        await _edit_or_send(query, "Этот розыгрыш недоступен.")
        return
    entered = db.has_entered_giveaway(giveaway_id, user.id)
    await _send_photo_or_text(
        query,
        _giveaway_public_text(giveaway, user.id),
        photo_file_id=giveaway.get("photo_file_id"),
        reply_markup=_giveaway_public_keyboard(giveaway, entered=entered, back_callback="giveaways"),
        parse_mode="HTML",
    )


async def handle_giveaway_participants(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    query = update.callback_query
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway or not giveaway.get("public_participants"):
        await query.answer("Список участников скрыт", show_alert=True)
        return
    entries = db.get_giveaway_entries(giveaway_id)
    text = "👥 Участников пока нет." if not entries else "👥 <b>Участники</b>\n\n" + "\n".join(
        [f"{idx}. @{item.get('username')}" if item.get("username") else f"{idx}. ID {item.get('user_id')}" for idx, item in enumerate(entries[:100], start=1)]
    )
    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", query.from_user.id), callback_data=f"giveaway_{giveaway_id}")]]),
        parse_mode="HTML",
    )


async def handle_giveaway_join(update: Update, context: ContextTypes.DEFAULT_TYPE, giveaway_id: int):
    query = update.callback_query
    user = query.from_user
    giveaway = db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get("status") != "active":
        await query.answer("Розыгрыш недоступен", show_alert=True)
        return
    ends_at = _parse_dt(giveaway.get("ends_at"))
    if ends_at and ends_at <= datetime.now():
        await query.answer("Розыгрыш уже завершён", show_alert=True)
        return
    if db.has_entered_giveaway(giveaway_id, user.id):
        await query.answer("Вы уже участвуете", show_alert=True)
        return
    min_balance = float(giveaway.get("min_balance") or 0)
    if db.get_balance(user.id) < min_balance:
        await query.answer(f"Нужен баланс от ${min_balance:.2f}", show_alert=True)
        return
    min_purchases = int(giveaway.get("min_purchases") or 0)
    if db.count_user_purchases(user.id) < min_purchases:
        await query.answer(f"Нужно минимум покупок: {min_purchases}", show_alert=True)
        return
    required_channel = _normalize_channel(giveaway.get("required_channel") or "")
    if required_channel:
        try:
            member = await context.bot.get_chat_member(required_channel, user.id)
            if getattr(member, "status", "") in {"left", "kicked"}:
                await query.answer(f"Нужна подписка на {required_channel}", show_alert=True)
                return
        except Exception:
            await query.answer(f"Не удалось проверить подписку на {required_channel}", show_alert=True)
            return
    if not db.enter_giveaway(giveaway_id, user.id, user.username):
        await query.answer("Не удалось записать участие", show_alert=True)
        return
    await query.answer("Вы участвуете!", show_alert=True)
    await handle_giveaway_view(update, context, giveaway_id)
