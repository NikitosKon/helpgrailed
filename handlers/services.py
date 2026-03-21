from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS, SUPPORT_CONTACT
from database import db
from keyboards.reply import categories_menu, get_text

import logging
import os


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


def _stock_str(stock: int) -> str:
    return '∞' if stock < 0 else str(stock)


async def handle_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    await _edit_or_send_with_core_photo(
        query,
        get_text('choose_category', user.id),
        'services',
        reply_markup=categories_menu(user.id)
    )


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    query = update.callback_query
    user = query.from_user
    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')

    logger.info(f"Category selected: {category}")

    if category == 'support':
        text = "🆘 Technical support\n\nContact us here:"
        keyboard = [
            [InlineKeyboardButton(SUPPORT_CONTACT, url=f"https://t.me/{SUPPORT_CONTACT.replace('@', '')}")],
            [InlineKeyboardButton(get_text('back', user.id), callback_data='services')]
        ]
        await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    try:
        subcats = db.get_subcategories(category, lang=user_lang)
        if subcats:
            categories = db.get_categories(user_lang)
            cat_name = categories.get(category, category)
            text = f"{cat_name}\n\n{get_text('choose_subcategory', user.id)}"

            keyboard = [
                [InlineKeyboardButton(subcat_name, callback_data=f"subcat|{category}|{subcat_id}")]
                for subcat_id, subcat_name in subcats.items()
            ]
            keyboard.append([InlineKeyboardButton(get_text('back', user.id), callback_data='services')])

            await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        items = db.get_products(category, lang=user_lang)
        categories = db.get_categories(user_lang)
        cat_name = categories.get(category, category)

        if not items:
            await _edit_or_send(
                query,
                f"{get_text('no_items', user.id)}\n\n{cat_name}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data='services')]])
            )
            return

        text = f"{cat_name}\n\n{get_text('choose_item', user.id)}"
        keyboard = []
        for item in items:
            if isinstance(item, dict):
                pid = item.get('id')
                name = item.get('name', 'Без названия')
                price = item.get('price_usd', 0)
                stock = item.get('stock', -1)
            else:
                pid = item[0]
                name = item[2]
                price = item[3]
                stock = item[5]

            btn_text = f"{name} — ${price:.0f} ({get_text('in_stock', user.id)}: {_stock_str(stock)})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'prod_{pid}')])

        keyboard.append([InlineKeyboardButton(get_text('back', user.id), callback_data='services')])
        category_info = db.get_category(category)
        category_photo = category_info.get('photo_url') if category_info else None

        if category_photo and os.path.exists(category_photo):
            with open(category_photo, 'rb') as photo_file:
                await query.message.reply_photo(
                    photo=photo_file,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error in category {category}: {e}")
        await _edit_or_send(
            query,
            "❌ Error loading products",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data='services')]])
        )


async def handle_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, subcategory: str):
    query = update.callback_query
    user = query.from_user

    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')

    try:
        items = db.get_products(category, subcategory=subcategory, lang=user_lang)
        categories = db.get_categories(user_lang)
        cat_name = categories.get(category, category)
        subcats = db.get_subcategories(category, lang=user_lang)
        sub_name = subcats.get(subcategory, subcategory)

        if not items:
            await _edit_or_send(
                query,
                f"{get_text('no_items', user.id)}\n\n{cat_name} / {sub_name}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data=f'cat_{category}')]])
            )
            return

        text = f"{cat_name} / {sub_name}\n\n{get_text('choose_item', user.id)}"
        keyboard = []

        for item in items:
            if isinstance(item, dict):
                pid = item.get('id')
                name = item.get('name', 'Без названия')
                price = item.get('price_usd', 0)
                stock = item.get('stock', -1)
            else:
                pid = item[0]
                name = item[2]
                price = item[3]
                stock = item[5]

            btn_text = f"{name} — ${price:.0f} ({get_text('in_stock', user.id)}: {_stock_str(stock)})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'prod_{pid}')])

        keyboard.append([InlineKeyboardButton(get_text('back', user.id), callback_data=f'cat_{category}')])
        await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in subcategory {category}/{subcategory}: {e}")
        await _edit_or_send(
            query,
            "❌ Error loading products",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data=f'cat_{category}')]])
        )


async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    query = update.callback_query
    user = query.from_user

    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')
    prod = db.get_product(product_id, lang=user_lang)
    if not prod:
        await _edit_or_send(query, "❌ Product not found.")
        return

    if isinstance(prod, dict):
        name = prod.get('name', 'Без названия')
        cat = prod.get('category', '')
        subcat = prod.get('subcategory')
        price = prod.get('price_usd', 0)
        desc = prod.get('description', 'Описание отсутствует')
        stock = prod.get('stock', -1)
        photo_url = prod.get('photo_url')
    else:
        name = prod[2]
        cat = prod[1]
        subcat = None
        price = prod[3]
        desc = prod[4] or 'Описание отсутствует'
        stock = prod[5]
        photo_url = prod[8] if len(prod) > 8 else None

    balance = db.get_balance(user.id)
    categories = db.get_categories(user_lang)
    category_name = categories.get(cat, cat)
    subcategory_name = None
    if subcat:
        subcategory_name = db.get_subcategories(cat, lang=user_lang).get(subcat, subcat)

    path_line = f"📂 {category_name}"
    if subcategory_name:
        path_line += f" / {subcategory_name}"

    text = (
        f"{path_line}\n\n"
        f"<b>{name}</b>\n\n"
        f"{desc}\n\n"
        f"💰 Price: <b>${price:.2f}</b>\n"
        f"📦 Stock: {_stock_str(stock)}\n"
        f"💳 Your balance: <b>${balance:.2f}</b>\n\n"
        f"Tap the button below to purchase this service."
    )

    back_cb = f"subcat|{cat}|{subcat}" if subcat else f"cat_{cat}"
    keyboard = [
        [InlineKeyboardButton(get_text('buy', user.id, price=price), callback_data=f'buy_{product_id}')],
        [InlineKeyboardButton(get_text('back', user.id), callback_data=back_cb)],
        [InlineKeyboardButton(get_text('main_menu', user.id), callback_data='menu')],
    ]

    if photo_url and os.path.exists(photo_url):
        with open(photo_url, 'rb') as photo_file:
            await query.message.reply_photo(
                photo=photo_file,
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
    else:
        await _edit_or_send(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    query = update.callback_query
    user = query.from_user

    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')
    prod = db.get_product(product_id, lang=user_lang)
    if not prod:
        await query.answer("❌ Товар не найден", show_alert=True)
        return

    if isinstance(prod, dict):
        product_name = prod.get('name', 'Товар')
        product_price = prod.get('price_usd', 0)
        product_category = prod.get('category', '')
    else:
        product_name = prod[2]
        product_price = prod[3]
        product_category = prod[1]

    success, message, product_data = db.purchase(user.id, product_id)

    if not success:
        if "Недостаточно средств" in message:
            balance = db.get_balance(user.id)
            need = product_price - balance
            text = (
                f"❌ Недостаточно средств\n\n"
                f"💰 Нужно: ${product_price:.2f}\n"
                f"💳 Ваш баланс: ${balance:.2f}\n"
                f"❌ Не хватает: ${need:.2f}"
            )
            keyboard = [
                [InlineKeyboardButton("💰 Пополнить", callback_data='deposit')],
                [InlineKeyboardButton(get_text('back', user.id), callback_data=f'prod_{product_id}')]
            ]
        elif "закончился" in message:
            text = "❌ Товар закончился. Попробуйте другой товар."
            keyboard = [[InlineKeyboardButton(get_text('back', user.id), callback_data=f'cat_{product_category}')]]
        else:
            text = f"❌ Ошибка: {message}"
            keyboard = [[InlineKeyboardButton(get_text('back', user.id), callback_data='services')]]

        await _edit_or_send(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🛒 <b>НОВАЯ ПОКУПКА</b>\n\n"
                f"👤 Пользователь: @{user.username or 'нет'}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"📦 Товар: {product_name}\n"
                f"💰 Сумма: ${product_price:.2f}\n\n"
                f"🔔 Свяжитесь с покупателем!",
                parse_mode='HTML'
            )
        except Exception:
            pass

    text = (
        f"✅ <b>{get_text('purchase_success', user.id)}</b>\n\n"
        f"📦 Товар: {product_name}\n"
        f"💰 Списано: ${product_price:.2f}\n\n"
        f"🔔 Напишите {SUPPORT_CONTACT} для получения услуги.\n"
        f"🆔 Ваш ID: <code>{user.id}</code>"
    )
    keyboard = [[InlineKeyboardButton(get_text('main_menu', user.id), callback_data='menu')]]

    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
