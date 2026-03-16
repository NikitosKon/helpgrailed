from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import categories_menu, get_text, back_button
from config import CATEGORIES, ADMIN_IDS, SUPPORT_CONTACT
import logging

logger = logging.getLogger(__name__)

async def handle_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать категории услуг"""
    query = update.callback_query
    await query.edit_message_text(
        get_text('choose_category'),
        reply_markup=categories_menu()
    )

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    """Показать товары в категории"""
    query = update.callback_query
    user = query.from_user
    
    logger.info(f"Категория: {category}")
    
    if category == 'support':
        text = "📞 Техническая поддержка\n\nСвяжитесь с нами:"
        keyboard = [
            [InlineKeyboardButton(SUPPORT_CONTACT, url=f"https://t.me/{SUPPORT_CONTACT.replace('@', '')}")],
            [InlineKeyboardButton(get_text('back'), callback_data='services')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    try:
        items = db.get_products(category)
        
        if not items:
            await query.edit_message_text(
                f"😕 В категории {CATEGORIES.get(category, category)} пока нет товаров.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back'), callback_data='services')]])
            )
            return
        
        text = f"{CATEGORIES.get(category, category)}\n\nВыберите товар:"
        keyboard = []
        
        for item in items:
            # Проверяем, что item это словарь
            if isinstance(item, dict):
                pid = item.get('id')
                name = item.get('name', 'Без названия')
                price = item.get('price_usd', 0)
                stock = item.get('stock', -1)
            else:
                # Если вдруг кортеж
                pid = item[0]
                name = item[2]
                price = item[3]
                stock = item[5]
            
            stock_str = '∞' if stock < 0 else str(stock)
            btn_text = f"{name} — ${price:.0f} (в наличии: {stock_str})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'prod_{pid}')])
        
        keyboard.append([InlineKeyboardButton(get_text('back'), callback_data='services')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка в категории {category}: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки товаров",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back'), callback_data='services')]])
        )

async def handle_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    """Показать информацию о товаре"""
    query = update.callback_query
    user = query.from_user
    
    prod = db.get_product(product_id)
    if not prod:
        await query.edit_message_text("❌ Товар не найден.")
        return
    
    # Проверяем тип prod (словарь или кортеж)
    if isinstance(prod, dict):
        name = prod.get('name', 'Без названия')
        cat = prod.get('category', '')
        price = prod.get('price_usd', 0)
        desc = prod.get('description', 'Описание отсутствует')
        stock = prod.get('stock', -1)
    else:
        name = prod[2]
        cat = prod[1]
        price = prod[3]
        desc = prod[4] or 'Описание отсутствует'
        stock = prod[5]
    
    stock_str = '∞' if stock < 0 else str(stock)
    
    text = (
        f"<b>{name}</b>\n\n"
        f"{desc}\n\n"
        f"💰 Цена: <b>${price:.2f}</b>\n"
        f"📦 В наличии: {stock_str}\n"
        f"💳 Ваш баланс: <b>${db.get_balance(user.id)}</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton(get_text('buy', price=price), callback_data=f'buy_{product_id}')],
        [InlineKeyboardButton(get_text('back'), callback_data=f'cat_{cat}')],
        [InlineKeyboardButton(get_text('back'), callback_data='menu')]
    ]
    
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='HTML'
    )

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    """Обработка покупки"""
    query = update.callback_query
    user = query.from_user
    
    prod = db.get_product(product_id)
    if not prod:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    # Получаем данные товара
    if isinstance(prod, dict):
        product_name = prod.get('name', 'Товар')
        product_price = prod.get('price_usd', 0)
        product_category = prod.get('category', '')
    else:
        product_name = prod[2]
        product_price = prod[3]
        product_category = prod[1]
    
    # Используем атомарную транзакцию
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
                [InlineKeyboardButton(get_text('deposit'), callback_data='deposit')],
                [InlineKeyboardButton(get_text('back'), callback_data=f'prod_{product_id}')]
            ]
        elif "закончился" in message:
            text = "❌ Товар закончился. Попробуйте другой товар."
            keyboard = [InlineKeyboardButton(get_text('back'), callback_data=f'cat_{product_category}')]
        else:
            text = f"❌ Ошибка: {message}"
            keyboard = [InlineKeyboardButton(get_text('back'), callback_data='services')]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup([keyboard] if not isinstance(keyboard[0], list) else keyboard), 
            parse_mode='HTML'
        )
    else:
        # Уведомление админам
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
        keyboard = [[InlineKeyboardButton(get_text('menu'), callback_data='menu')]]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML'
        )