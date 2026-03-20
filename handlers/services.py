from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import categories_menu, get_text
from config import SUPPORT_CONTACT, ADMIN_IDS
import logging
import os

logger = logging.getLogger(__name__)

async def handle_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать категории услуг"""
    query = update.callback_query
    user = query.from_user
    
    await query.edit_message_text(
        get_text('choose_category', user.id),
        reply_markup=categories_menu(user.id)
    )

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    """Показать товары в категории"""
    query = update.callback_query
    user = query.from_user
    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')
    
    logger.info(f"Категория: {category}")
    
    if category == 'support':
        text = "📞 Техническая поддержка\n\nСвяжитесь с нами:"
        keyboard = [
            [InlineKeyboardButton(SUPPORT_CONTACT, url=f"https://t.me/{SUPPORT_CONTACT.replace('@', '')}")],
            [InlineKeyboardButton(get_text('back', user.id), callback_data='services')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    try:
        items = db.get_products(category, lang=user_lang)
        
        if not items:
            categories = db.get_categories(user_lang)
            cat_name = categories.get(category, category)
            await query.edit_message_text(
                f"{get_text('no_items', user.id)}\n\n{cat_name}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data='services')]])
            )
            return
        
        categories = db.get_categories(user_lang)
        cat_name = categories.get(category, category)
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
            
            stock_str = '∞' if stock < 0 else str(stock)
            btn_text = f"{name} — ${price:.0f} ({get_text('in_stock', user.id)}: {stock_str})"
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
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка в категории {category}: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки товаров",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user.id), callback_data='services')]])
        )

async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    """Показать информацию о товаре"""
    query = update.callback_query
    user = query.from_user
    
    user_data = db.get_user(user.id) or {}
    user_lang = user_data.get('language', 'ru')
    prod = db.get_product(product_id, lang=user_lang)
    if not prod:
        await query.edit_message_text("❌ Товар не найден.")
        return
    
    if isinstance(prod, dict):
        name = prod.get('name', 'Без названия')
        cat = prod.get('category', '')
        price = prod.get('price_usd', 0)
        desc = prod.get('description', 'Описание отсутствует')
        stock = prod.get('stock', -1)
        photo_url = prod.get('photo_url')
    else:
        name = prod[2]
        cat = prod[1]
        price = prod[3]
        desc = prod[4] or 'Описание отсутствует'
        stock = prod[5]
        photo_url = prod[8] if len(prod) > 8 else None
    
    stock_str = '∞' if stock < 0 else str(stock)
    balance = db.get_balance(user.id)
    
    text = (
        f"<b>{name}</b>\n\n"
        f"{desc}\n\n"
        f"💰 Цена: <b>${price:.2f}</b>\n"
        f"📦 В наличии: {stock_str}\n"
        f"💳 Ваш баланс: <b>${balance:.2f}</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"✅ Купить за ${price:.2f}", callback_data=f'buy_{product_id}')],
        [InlineKeyboardButton("◀️ Назад к категории", callback_data=f'cat_{cat}')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]
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
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    """Обработка покупки"""
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
                [InlineKeyboardButton("◀️ Назад", callback_data=f'prod_{product_id}')]
            ]
        elif "закончился" in message:
            text = "❌ Товар закончился. Попробуйте другой товар."
            keyboard = [InlineKeyboardButton("◀️ Назад", callback_data=f'cat_{product_category}')]
        else:
            text = f"❌ Ошибка: {message}"
            keyboard = [InlineKeyboardButton("◀️ Назад", callback_data='services')]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup([keyboard] if not isinstance(keyboard[0], list) else keyboard), 
            parse_mode='HTML'
        )
    else:
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
            except:
                pass
        
        text = (
            f"✅ <b>Покупка успешно оформлена!</b>\n\n"
            f"📦 Товар: {product_name}\n"
            f"💰 Списано: ${product_price:.2f}\n\n"
            f"🔔 Напишите {SUPPORT_CONTACT} для получения услуги.\n"
            f"🆔 Ваш ID: <code>{user.id}</code>"
        )
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML'
        )
