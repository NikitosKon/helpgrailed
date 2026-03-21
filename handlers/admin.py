import os
import json
import logging
import html
from uuid import uuid4
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from config import config
from database import db

logger = logging.getLogger(__name__)


async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Главный обработчик админ-панели"""
    query = update.callback_query
    user = query.from_user

    logger.info(f"🔍 ADMIN CALLBACK: {data} from user {user.id}")

    if user.id not in ADMIN_IDS:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return

    if data == 'admin':
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
            [InlineKeyboardButton("📦 Управление товарами", callback_data='admin_products')],
            [InlineKeyboardButton("🏠 Главная страница", callback_data='admin_home_menu')],
            [InlineKeyboardButton("🔘 Главное меню", callback_data='admin_menu_editor')],
            [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
            [InlineKeyboardButton("📈 Продажи", callback_data='admin_sales')],
            [InlineKeyboardButton("👑 Управление админами", callback_data='admin_admins')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
        ]
        await query.edit_message_text(
            "👑 <b>Админ-панель</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data == 'admin_stats':
        await admin_stats(update, context)

    elif data == 'admin_products':
        await admin_products_menu(update, context)

    elif data == 'admin_home_menu':
        await admin_home_menu(update, context)
    elif data == 'admin_home_edit_text':
        await admin_home_edit_text_start(update, context)
    elif data == 'admin_home_edit_photo':
        await admin_home_edit_photo_start(update, context)
    elif data == 'admin_home_remove_photo':
        await admin_home_remove_photo(update, context)
    elif data == 'admin_home_preview':
        await admin_home_preview(update, context)

    elif data == 'admin_menu_editor':
        await admin_menu_editor(update, context)
    elif data == 'admin_menu_core':
        await admin_menu_core_menu(update, context)
    elif data.startswith('admin_menu_core_edit_'):
        await admin_menu_core_edit_start(update, context, data.replace('admin_menu_core_edit_', ''))
    elif data.startswith('admin_menu_core_field_'):
        payload = data.replace('admin_menu_core_field_', '', 1)
        key, lang = payload.rsplit('_', 1)
        await admin_menu_core_edit_field_start(update, context, key, lang)
    elif data == 'admin_menu_custom':
        await admin_menu_custom_menu(update, context)
    elif data == 'admin_menu_custom_add':
        await admin_menu_custom_add_start(update, context)
    elif data == 'admin_menu_custom_type_url':
        await admin_menu_custom_choose_type(update, context, 'url')
    elif data == 'admin_menu_custom_type_callback':
        await admin_menu_custom_choose_type(update, context, 'callback')
    elif data.startswith('admin_menu_custom_target_'):
        await admin_menu_custom_choose_target(update, context, data.replace('admin_menu_custom_target_', ''))
    elif data.startswith('admin_menu_custom_edit_'):
        await admin_menu_custom_edit_start(update, context, data.replace('admin_menu_custom_edit_', ''))
    elif data.startswith('admin_menu_custom_field_'):
        payload = data.replace('admin_menu_custom_field_', '', 1)
        button_id, field = payload.rsplit('_', 1)
        await admin_menu_custom_edit_field_start(update, context, button_id, field)
    elif data.startswith('admin_menu_custom_delete_'):
        await admin_menu_custom_delete(update, context, data.replace('admin_menu_custom_delete_', ''))

    # Управление категориями
    elif data == 'admin_categories_menu':
        await admin_categories_menu(update, context)

    elif data == 'admin_list_categories':
        await admin_list_categories(update, context)

    elif data == 'admin_add_category':
        await admin_add_category_start(update, context)

    elif data == 'admin_edit_category':
        await admin_edit_category_list(update, context)

    elif data.startswith('admin_edit_cat_'):
        cat_id = data[15:]  # обрезаем 'admin_edit_cat_'
        await admin_edit_category_start(update, context, cat_id)

    elif data == 'admin_delete_category':
        await admin_delete_category_list(update, context)

    elif data.startswith('admin_delete_cat_'):
        cat_id = data[16:]  # обрезаем 'admin_delete_cat_'
        await admin_delete_category_confirm(update, context, cat_id)

    elif data == 'admin_balance_menu':
        from handlers.admin_balance import admin_balance_menu
        await admin_balance_menu(update, context)

    elif data == 'admin_add_balance':
        from handlers.admin_balance import admin_add_balance_start
        await admin_add_balance_start(update, context)

    elif data == 'admin_promo_menu':
        from handlers.admin_promo import admin_promo_menu
        await admin_promo_menu(update, context)

    elif data == 'admin_create_promo':
        from handlers.admin_promo import admin_create_promo_start
        await admin_create_promo_start(update, context)

    elif data == 'promo_generate':
        from handlers.admin_promo import handle_promo_creation_method
        await handle_promo_creation_method(update, context, data)

    elif data == 'promo_manual':
        from handlers.admin_promo import handle_promo_creation_method
        await handle_promo_creation_method(update, context, data)

    elif data.startswith('promo_type_'):
        from handlers.admin_promo import handle_promo_type_selection
        await handle_promo_type_selection(update, context, data)

    elif data.startswith('promo_target_product_') or data.startswith('promo_target_category_'):
        from handlers.admin_promo import handle_promo_target_selection
        await handle_promo_target_selection(update, context, data)

    elif data == 'bonus_discount' or data == 'bonus_balance':
        logger.info(f"📢 Выбор типа бонуса: {data}")
        await query.answer()

    # Управление товарами
    elif data == 'admin_list_products':
        await admin_list_products(update, context)

    elif data == 'admin_add_product':
        await admin_add_product_start(update, context)

    elif data == 'admin_edit_product':
        await admin_edit_product_list(update, context)

    elif data.startswith('admin_edit_') and len(data.split('_')) == 3:
        try:
            pid = int(data.split('_')[2])
            await admin_edit_product_start(update, context, pid)
        except ValueError:
            await query.answer("Некорректный ID товара", show_alert=True)

    elif data == 'admin_delete_product':
        await admin_delete_product_list(update, context)

    elif data.startswith('admin_delete_'):
        try:
            pid = int(data.split('_')[2])
            await admin_delete_product_confirm(update, context, pid)
        except ValueError:
            await query.answer("Некорректный ID товара", show_alert=True)

    elif data == 'admin_debug':
        await admin_debug(update, context)

    elif data == 'admin_users':
        await admin_users(update, context)

    elif data == 'admin_sales':
        await admin_sales(update, context)

    elif data == 'admin_admins':
        await admin_manage_admins(update, context)

    elif data == 'admin_add_admin':
        await admin_add_admin_start(update, context)

    elif data == 'admin_remove_admin':
        await admin_remove_admin(update, context)

    elif data.startswith('admin_remove_'):
        try:
            admin_id = int(data.split('_')[2])
            await admin_remove_confirm(update, context, admin_id)
        except ValueError:
            await query.answer("Некорректный ID администратора", show_alert=True)

    # Рассылки
    elif data == 'admin_broadcast_menu':
        from handlers.admin_broadcast import admin_broadcast_menu
        await admin_broadcast_menu(update, context)

    elif data == 'broadcast_create':
        from handlers.admin_broadcast import broadcast_create_start
        await broadcast_create_start(update, context)

    elif data == 'broadcast_stats':
        from handlers.admin_broadcast import broadcast_stats
        await broadcast_stats(update, context)

    elif data == 'broadcast_send':
        from handlers.admin_broadcast import broadcast_send
        await broadcast_send(update, context)

    elif data == 'broadcast_edit':
        from handlers.admin_broadcast import broadcast_edit_start
        await broadcast_edit_start(update, context)

    elif data == 'broadcast_add_photo':
        from handlers.admin_broadcast import broadcast_add_photo_start
        await broadcast_add_photo_start(update, context)

    elif data == 'broadcast_remove_photo':
        from handlers.admin_broadcast import broadcast_remove_photo
        await broadcast_remove_photo(update, context)

    elif data == 'broadcast_preview_again':
        from handlers.admin_broadcast import broadcast_preview_again
        await broadcast_preview_again(update, context)

    elif data == 'broadcast_save_draft':
        from handlers.admin_broadcast import broadcast_save_draft_start
        await broadcast_save_draft_start(update, context)

    elif data == 'broadcast_drafts':
        from handlers.admin_broadcast import broadcast_drafts_menu
        await broadcast_drafts_menu(update, context)

    elif data.startswith('broadcast_load_draft_'):
        from handlers.admin_broadcast import broadcast_load_draft
        await broadcast_load_draft(update, context, int(data.replace('broadcast_load_draft_', '')))

    elif data.startswith('broadcast_delete_draft_'):
        from handlers.admin_broadcast import broadcast_delete_draft
        await broadcast_delete_draft(update, context, int(data.replace('broadcast_delete_draft_', '')))

    elif data == 'broadcast_cancel':
        from handlers.admin_broadcast import broadcast_cancel
        await broadcast_cancel(update, context)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    users_result = db.execute("SELECT COUNT(*) as count FROM users", fetch=True)
    if users_result:
        if db.use_postgres:
            users_total = users_result[0]['count']
        else:
            users_total = users_result[0][0]
    else:
        users_total = 0
    
    users_today_result = db.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(registered_date) = DATE(?)",
        (datetime.now().date().isoformat(),),
        fetch=True
    )
    if users_today_result:
        if db.use_postgres:
            users_today = users_today_result[0]['count']
        else:
            users_today = users_today_result[0][0]
    else:
        users_today = 0
    
    purchases_result = db.execute(
        "SELECT COUNT(*) as count FROM transactions WHERE type = 'purchase' AND status = 'completed'",
        fetch=True
    )
    if purchases_result:
        if db.use_postgres:
            purchases_total = purchases_result[0]['count']
        else:
            purchases_total = purchases_result[0][0]
    else:
        purchases_total = 0
    
    revenue_result = db.execute(
        "SELECT SUM(amount) as total FROM transactions WHERE type = 'purchase' AND status = 'completed'",
        fetch=True
    )
    if revenue_result and revenue_result[0]:
        if db.use_postgres:
            revenue = revenue_result[0]['total'] or 0
        else:
            revenue = revenue_result[0][0] or 0
    else:
        revenue = 0
    
    revenue_today_result = db.execute(
        "SELECT SUM(amount) as total FROM transactions WHERE type = 'purchase' AND status = 'completed' AND DATE(completed_at) = DATE(?)",
        (datetime.now().date().isoformat(),),
        fetch=True
    )
    if revenue_today_result and revenue_today_result[0]:
        if db.use_postgres:
            revenue_today = revenue_today_result[0]['total'] or 0
        else:
            revenue_today = revenue_today_result[0][0] or 0
    else:
        revenue_today = 0
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {users_total}\n"
        f"➕ Новых сегодня: {users_today}\n\n"
        f"📦 Всего покупок: {purchases_total}\n"
        f"💰 Общий доход: ${revenue:.2f}\n"
        f"📈 Доход сегодня: ${revenue_today:.2f}"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    keyboard = [
        [InlineKeyboardButton("📂 Управление категориями", callback_data='admin_categories_menu')],
        [InlineKeyboardButton("➕ Добавить товар", callback_data='admin_add_product')],
        [InlineKeyboardButton("✏️ Редактировать товар", callback_data='admin_edit_product')],
        [InlineKeyboardButton("❌ Удалить товар", callback_data='admin_delete_product')],
        [InlineKeyboardButton("📋 Список товаров", callback_data='admin_list_products')],
        [InlineKeyboardButton("💰 Управление балансами", callback_data='admin_balance_menu')],
        [InlineKeyboardButton("🎫 Промокоды", callback_data='admin_promo_menu')],
        [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast_menu')],
        [InlineKeyboardButton("🐛 Отладка", callback_data='admin_debug')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]

    await query.edit_message_text(
        "📦 <b>Управление товарами и категориями</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.get_products(show_all=True)
    if not products:
        await query.edit_message_text("📭 Товаров нет")
        return

    text = "📋 <b>Список товаров:</b>\n\n"
    for prod in products:
        if isinstance(prod, dict):
            pid = prod.get('id')
            cat = prod.get('category')
            name = prod.get('name')
            price = prod.get('price_usd')
            stock = prod.get('stock', -1)
            is_active = prod.get('is_active', 1)
        else:
            pid = prod[0]
            cat = prod[1]
            name = prod[2]
            price = prod[3]
            stock = prod[5]
            is_active = prod[7]
        
        status = "✅" if is_active else "❌"
        stock_str = '∞' if stock < 0 else str(stock)
        text += f"{status} ID {pid}: {name}\n   Кат: {cat}, ${price:.2f}, {stock_str} шт.\n"

    if len(text) > 4000:
        text = text[:3970] + "..."

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_products')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    for k in list(context.user_data.keys()):
        if k.startswith('add_prod_'):
            del context.user_data[k]

    db.set_pending_action(user.id, 'admin_add_product_name')

    await query.edit_message_text(
        "➕ <b>Добавление товара</b>\n\nВведите название товара:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_products')]]),
        parse_mode='HTML'
    )


async def download_telegram_photo(file_id: str, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    try:
        file = await context.bot.get_file(file_id)
        os.makedirs('product_photos', exist_ok=True)
        ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg'
        filename = f"product_photos/{uuid4()}.{ext}"
        await file.download_to_drive(filename)
        return filename
    except Exception as e:
        logger.error(f"Ошибка скачивания фото: {e}")
        return None


async def handle_admin_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending = db.get_pending_action(user.id)
    if not pending or pending[0] != 'admin_add_product_photo_waiting':
        return

    if update.message.photo:
        photo = update.message.photo[-1]
        photo_path = await download_telegram_photo(photo.file_id, context)

        if photo_path:
            context.user_data['add_prod_photo_url'] = photo_path
            db.set_pending_action(user.id, 'admin_add_product_stock')
            await update.message.reply_text(
                "✅ Фото сохранено\n\n"
                "Введите количество на складе:\n"
                "• Число (например: 10)\n"
                "• -1 для бесконечного запаса"
            )
        else:
            await update.message.reply_text("❌ Ошибка сохранения фото. Попробуйте ещё раз или /skip")

    elif update.message.text == '/skip':
        context.user_data['add_prod_photo_url'] = None
        db.set_pending_action(user.id, 'admin_add_product_stock')
        await update.message.reply_text(
            "✅ Фото пропущено\n\n"
            "Введите количество на складе:\n"
            "• Число (например: 10)\n"
            "• -1 для бесконечного запаса"
        )
    else:
        await update.message.reply_text("❌ Отправьте фото или напишите /skip")


async def handle_admin_add_product_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    text = text.strip()

    if action == 'admin_add_product_name':
        context.user_data['add_prod_name'] = text
        db.set_pending_action(user.id, 'admin_add_product_category')
        
        categories = config.CATEGORIES
        await update.message.reply_text(
            f"✅ Название: {text}\n\n"
            f"Введите категорию товара:\n"
            f"Доступные: {', '.join(categories.keys())}"
        )
        return

    elif action == 'admin_add_product_category':
        categories = config.CATEGORIES
        if text not in categories:
            await update.message.reply_text(f"❌ Неверная категория. Доступны: {', '.join(categories.keys())}")
            return
        context.user_data['add_prod_category'] = text
        db.set_pending_action(user.id, 'admin_add_product_price')
        await update.message.reply_text("✅ Категория сохранена\n\nВведите цену в $ (например 45.99):")
        return

    elif action == 'admin_add_product_price':
        try:
            price = float(text.replace(',', '.'))
            context.user_data['add_prod_price'] = price
            db.set_pending_action(user.id, 'admin_add_product_desc')
            await update.message.reply_text("✅ Цена сохранена\n\nВведите описание (или /skip):")
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число (например 45.99)")
        return

    elif action == 'admin_add_product_desc':
        desc = None if text == '/skip' else text
        context.user_data['add_prod_desc'] = desc
        db.set_pending_action(user.id, 'admin_add_product_photo_waiting')
        await update.message.reply_text(
            "✅ Описание сохранено\n\n"
            "📸 Отправьте фото товара\n"
            "(или /skip для пропуска)",
            parse_mode='HTML'
        )
        return

    elif action == 'admin_add_product_photo_waiting':
        if text == '/skip':
            context.user_data['add_prod_photo_url'] = None
            db.set_pending_action(user.id, 'admin_add_product_stock')
            await update.message.reply_text(
                "✅ Фото пропущено\n\n"
                "Введите количество на складе:\n"
                "• Число (например: 10)\n"
                "• -1 для бесконечного запаса"
            )
        else:
            await update.message.reply_text("❌ Отправьте фото товара или /skip")
        return

    elif action == 'admin_add_product_stock':
        try:
            stock = int(text)
            context.user_data['add_prod_stock'] = stock
            db.set_pending_action(user.id, 'admin_add_product_sort')
            await update.message.reply_text(
                "✅ Запас сохранён\n\n"
                "Введите порядок сортировки (целое число, меньше = выше в списке):"
            )
        except ValueError:
            await update.message.reply_text("❌ Введите целое число (например 10 или -1)")
        return

    elif action == 'admin_add_product_sort':
        try:
            sort_order = int(text)

            required = ['add_prod_name', 'add_prod_category', 'add_prod_price', 'add_prod_stock']
            if not all(k in context.user_data for k in required):
                await update.message.reply_text("❌ Данные потеряны. Начните заново.")
                db.clear_pending_action(user.id)
                context.user_data.clear()
                return

            admin_user = db.get_user(user.id) or {}
            input_lang = admin_user.get('language', 'ru')
            db.add_product(
                category=context.user_data['add_prod_category'],
                name=context.user_data['add_prod_name'],
                price=float(context.user_data['add_prod_price']),
                description=context.user_data.get('add_prod_desc'),
                stock=int(context.user_data['add_prod_stock']),
                sort_order=sort_order,
                photo_url=context.user_data.get('add_prod_photo_url'),
                input_lang=input_lang
            )

            db.clear_pending_action(user.id)
            context.user_data.clear()

            await update.message.reply_text(
                "🎉 Товар успешно добавлен!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Добавить ещё", callback_data="admin_add_product")],
                    [InlineKeyboardButton("К списку товаров", callback_data="admin_list_products")],
                    [InlineKeyboardButton("Админ-меню", callback_data="admin")]
                ])
            )

        except ValueError:
            await update.message.reply_text("❌ Порядок сортировки — целое число")
        except Exception as e:
            logger.exception("Ошибка сохранения товара")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        return


async def admin_edit_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.get_products(show_all=True)
    if not products:
        await query.edit_message_text("📭 Нет товаров для редактирования")
        return

    keyboard = []
    for prod in products[:10]:
        if isinstance(prod, dict):
            pid = prod.get('id')
            name = prod.get('name', 'Без названия')
        else:
            pid = prod[0]
            name = prod[2]
        
        keyboard.append([InlineKeyboardButton(f"✏️ {name}", callback_data=f'admin_edit_{pid}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_products')])

    await query.edit_message_text(
        "Выберите товар для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_edit_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query

    prod = db.get_product(product_id)
    if not prod:
        await query.edit_message_text("❌ Товар не найден")
        return

    db.set_pending_action(query.from_user.id, f'admin_edit_{product_id}_name')

    if isinstance(prod, dict):
        current_name = prod.get('name', 'Без названия')
        current_price = prod.get('price_usd', 0)
        current_desc = prod.get('description', 'нет')
        current_stock = prod.get('stock', -1)
    else:
        current_name = prod[2]
        current_price = prod[3]
        current_desc = prod[4] or 'нет'
        current_stock = prod[5]

    stock_str = '∞' if current_stock < 0 else str(current_stock)

    text = (
        f"✏️ <b>Редактирование товара ID {product_id}</b>\n\n"
        f"Текущее название: {current_name}\n"
        f"Текущая цена: ${current_price}\n"
        f"Текущее описание: {current_desc}\n"
        f"Текущий запас: {stock_str}\n\n"
        f"Введите новое название товара (или /skip для пропуска):"
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='admin_products')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_delete_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.get_products(show_all=True)
    if not products:
        await query.edit_message_text("📭 Нет товаров для удаления")
        return

    keyboard = []
    for prod in products[:10]:
        if isinstance(prod, dict):
            pid = prod.get('id')
            name = prod.get('name', 'Без названия')
        else:
            pid = prod[0]
            name = prod[2]
        
        keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f'admin_delete_{pid}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_products')])

    await query.edit_message_text(
        "Выберите товар для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_delete_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query

    db.delete_product(product_id)
    await query.edit_message_text(f"✅ Товар ID {product_id} удален")

    import asyncio
    await asyncio.sleep(1)
    await admin_products_menu(update, context)


async def admin_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.execute("SELECT * FROM products", fetch=True)
    text = "📦 <b>Товары в БД:</b>\n\n"
    for p in products:
        if db.use_postgres:
            text += f"ID: {p['id']}, Кат: {p['category']}, {p['name']}, Цена: ${p['price_usd']}, Активен: {p['is_active']}\n"
        else:
            text += f"ID: {p[0]}, Кат: {p[1]}, {p[2]}, Цена: ${p[3]}, Активен: {p[7]}\n"

    if len(text) > 4000:
        text = text[:4000] + "..."

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_products')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    stats = db.execute("SELECT COUNT(*) as count, SUM(balance) as total FROM users", fetch=True)[0]
    
    if db.use_postgres:
        total_users = stats['count'] if stats else 0
        total_balance = stats['total'] or 0
    else:
        total_users = stats[0] if stats else 0
        total_balance = stats[1] or 0
    
    text = (
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: {total_users}\n"
        f"Общий баланс: ${total_balance:.2f}\n\n"
        f"Функции в разработке..."
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    sales = db.execute(
        "SELECT COUNT(*) as count, SUM(amount) as total FROM transactions WHERE type = 'purchase' AND status = 'completed'",
        fetch=True
    )[0]
    
    if db.use_postgres:
        total_sales = sales['count'] if sales else 0
        total_revenue = sales['total'] or 0
    else:
        total_sales = sales[0] if sales else 0
        total_revenue = sales[1] or 0
    
    by_category = db.execute(
        "SELECT p.category, COUNT(*), SUM(t.amount) FROM transactions t "
        "JOIN products p ON t.product_id = p.id "
        "WHERE t.type = 'purchase' AND t.status = 'completed' "
        "GROUP BY p.category",
        fetch=True
    )
    
    text = f"📈 <b>Продажи</b>\n\nВсего продаж: {total_sales}\nОбщая выручка: ${total_revenue:.2f}\n\n"
    if by_category:
        text += "По категориям:\n"
        for row in by_category:
            if db.use_postgres:
                cat = row['category']
                count = row['count']
                amount = row['sum'] or 0
            else:
                cat = row[0]
                count = row[1]
                amount = row[2] or 0
            categories = db.get_categories()
            cat_name = categories.get(cat, cat)
            text += f" • {cat_name}: {count} шт. (${amount:.2f})\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        with open('admins.json', 'r') as f:
            current_admins = json.load(f)
    except FileNotFoundError:
        current_admins = ADMIN_IDS.copy()

    admins_list = ""
    for i, admin_id in enumerate(current_admins, 1):
        user = db.get_user(admin_id)
        if user and user.get('username'):
            username = f"@{user['username']}"
        else:
            username = f"ID: {admin_id}"
        admins_list += f"{i}. {username}\n"

    text = (
        f"👑 <b>Управление администраторами</b>\n\n"
        f"Текущие админы:\n{admins_list}\n\n"
        f"Чтобы добавить нового админа, нажмите кнопку ниже"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Добавить админа", callback_data='admin_add_admin')],
        [InlineKeyboardButton("❌ Удалить админа", callback_data='admin_remove_admin')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    db.set_pending_action(user.id, 'admin_add_admin')

    await query.edit_message_text(
        "➕ <b>Добавление администратора</b>\n\n"
        "Отправьте Telegram ID нового администратора:\n"
        "Пример: <code>123456789</code>\n\n"
        "ID можно узнать у бота @userinfobot",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_admins')]]),
        parse_mode='HTML'
    )


async def admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        with open('admins.json', 'r') as f:
            current_admins = json.load(f)
    except FileNotFoundError:
        current_admins = ADMIN_IDS.copy()

    if len(current_admins) <= 1:
        await query.answer("❌ Нельзя удалить последнего админа!", show_alert=True)
        return

    keyboard = []
    for admin_id in current_admins:
        if admin_id == query.from_user.id:
            continue
        user = db.get_user(admin_id)
        username = f"@{user[1]}" if user and len(user) > 1 and user[1] else f"ID: {admin_id}"
        keyboard.append([InlineKeyboardButton(f"❌ {username}", callback_data=f'admin_remove_{admin_id}')])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_admins')])

    await query.edit_message_text(
        "Выберите администратора для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int):
    query = update.callback_query

    if admin_id == query.from_user.id:
        await query.answer("❌ Нельзя удалить самого себя!", show_alert=True)
        return

    try:
        with open('admins.json', 'r') as f:
            current_admins = json.load(f)
    except FileNotFoundError:
        current_admins = ADMIN_IDS.copy()

    if admin_id not in current_admins:
        await query.answer("❌ Администратор не найден!", show_alert=True)
        return

    current_admins.remove(admin_id)

    with open('admins.json', 'w') as f:
        json.dump(current_admins, f)

    await query.edit_message_text(
        f"✅ Администратор с ID {admin_id} удален!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_admins')]])
    )


# ===== УПРАВЛЕНИЕ КАТЕГОРИЯМИ (МУЛЬТИЯЗЫЧНАЯ ВЕРСИЯ) =====

async def admin_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления категориями"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📋 Список категорий", callback_data='admin_list_categories')],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data='admin_add_category')],
        [InlineKeyboardButton("✏️ Редактировать категорию", callback_data='admin_edit_category')],
        [InlineKeyboardButton("❌ Удалить категорию", callback_data='admin_delete_category')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]
    
    await query.edit_message_text(
        "📂 <b>Управление категориями</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список категорий из БД на всех языках"""
    query = update.callback_query
    
    # Получаем категории из БД
    categories_ru = db.get_categories('ru')
    categories_uk = db.get_categories('uk')
    categories_en = db.get_categories('en')
    
    text = "📋 <b>Список категорий:</b>\n\n"
    
    # Собираем все уникальные ID
    all_ids = set(categories_ru.keys()) | set(categories_uk.keys()) | set(categories_en.keys())
    
    for cat_id in sorted(all_ids):
        text += f"• <b>{cat_id}</b>\n"
        text += f"  🇷🇺 {categories_ru.get(cat_id, '—')}\n"
        text += f"  🇺🇦 {categories_uk.get(cat_id, '—')}\n"
        text += f"  🇬🇧 {categories_en.get(cat_id, '—')}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления категории"""
    query = update.callback_query
    user = query.from_user
    
    # Сохраняем шаги для ввода переводов
    context.user_data['add_category_step'] = 'id'
    db.set_pending_action(user.id, 'admin_add_category_id')
    
    await query.edit_message_text(
        "➕ <b>Добавление категории</b>\n\n"
        "Введите <b>ID категории</b> (английскими буквами, без пробелов):\n"
        "Пример: <code>new_category</code>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_categories_menu')]]),
        parse_mode='HTML'
    )


async def handle_admin_add_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Обработка ввода при добавлении категории"""
    user = update.effective_user
    text = text.strip()
    
    step = context.user_data.get('add_category_step', 'id')
    
    if step == 'id':
        import re
        if not re.match(r'^[a-z0-9_]+$', text):
            await update.message.reply_text(
                "❌ ID должен содержать только английские буквы, цифры и подчеркивания!\n"
                "Попробуйте ещё раз:"
            )
            return
        
        existing = db.get_categories()
        if text in existing:
            await update.message.reply_text(
                f"❌ Категория с ID <b>{text}</b> уже существует!\n"
                "Введите другой ID:",
                parse_mode='HTML'
            )
            return
        
        context.user_data['new_category_id'] = text
        context.user_data['add_category_step'] = 'name_ru'
        db.set_pending_action(user.id, 'admin_add_category_name_ru')
        
        await update.message.reply_text(
            f"✅ ID категории: <b>{text}</b>\n\n"
            "Введите <b>название на русском</b>:",
            parse_mode='HTML'
        )
        return
    
    elif step == 'name_ru':
        context.user_data['new_category_name_ru'] = text
        context.user_data['add_category_step'] = 'name_uk'
        db.set_pending_action(user.id, 'admin_add_category_name_uk')
        
        await update.message.reply_text(
            "✅ Название на русском сохранено\n\n"
            "Введите <b>название на украинском</b> (или /skip чтобы пропустить):",
            parse_mode='HTML'
        )
        return
    
    elif step == 'name_uk':
        if text != '/skip':
            context.user_data['new_category_name_uk'] = text
        else:
            context.user_data['new_category_name_uk'] = None
        
        context.user_data['add_category_step'] = 'name_en'
        db.set_pending_action(user.id, 'admin_add_category_name_en')
        
        await update.message.reply_text(
            "✅ Название на украинском сохранено\n\n"
            "Введите <b>название на английском</b> (или /skip чтобы пропустить):",
            parse_mode='HTML'
        )
        return
    
    elif step == 'name_en':
        if text != '/skip':
            context.user_data['new_category_name_en'] = text
        else:
            context.user_data['new_category_name_en'] = None
        
        # Сохраняем категорию
        cat_id = context.user_data['new_category_id']
        name_ru = context.user_data['new_category_name_ru']
        name_uk = context.user_data.get('new_category_name_uk')
        name_en = context.user_data.get('new_category_name_en')
        
        if db.add_category(cat_id, name_ru, name_uk, name_en):
            await update.message.reply_text(
                f"✅ Категория успешно добавлена!\n\n"
                f"ID: <b>{cat_id}</b>\n"
                f"🇷🇺 Русский: <b>{name_ru}</b>\n"
                f"🇺🇦 Українська: <b>{name_uk or 'не указан'}</b>\n"
                f"🇬🇧 English: <b>{name_en or 'not specified'}</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку категорий", callback_data='admin_list_categories')],
                    [InlineKeyboardButton("➕ Добавить ещё", callback_data='admin_add_category')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]
                ]),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении категории")
        
        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


async def admin_edit_category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список категорий для редактирования"""
    query = update.callback_query
    
    categories = db.get_categories('ru')  # Показываем русские названия в списке
    keyboard = []
    for cat_id, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(f"✏️ {cat_name}", callback_data=f'admin_edit_cat_{cat_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')])
    
    await query.edit_message_text(
        "Выберите категорию для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_edit_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    """Начало редактирования категории"""
    query = update.callback_query
    user = query.from_user
    
    # Получаем текущие названия
    categories_ru = db.get_categories('ru')
    categories_uk = db.get_categories('uk')
    categories_en = db.get_categories('en')
    
    if cat_id not in categories_ru:
        await query.edit_message_text("❌ Категория не найдена")
        return
    
    context.user_data['edit_cat_id'] = cat_id
    context.user_data['edit_cat_ru'] = categories_ru.get(cat_id, '')
    context.user_data['edit_cat_uk'] = categories_uk.get(cat_id, '')
    context.user_data['edit_cat_en'] = categories_en.get(cat_id, '')
    context.user_data['edit_step'] = 'ru'
    
    db.set_pending_action(user.id, f'admin_edit_category_ru_{cat_id}')
    
    await query.edit_message_text(
        f"✏️ <b>Редактирование категории {cat_id}</b>\n\n"
        f"Текущее русское название: {categories_ru.get(cat_id, '')}\n\n"
        f"Введите новое название на русском (или /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_categories_menu')]]),
        parse_mode='HTML'
    )


async def handle_admin_edit_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Обработка ввода при редактировании категории"""
    user = update.effective_user
    
    if action.startswith('admin_edit_category_ru_'):
        cat_id = action.replace('admin_edit_category_ru_', '')
        
        if text != '/skip':
            context.user_data['edit_cat_ru_new'] = text
        
        context.user_data['edit_step'] = 'uk'
        db.set_pending_action(user.id, f'admin_edit_category_uk_{cat_id}')
        
        await update.message.reply_text(
            f"Текущее украинское название: {context.user_data.get('edit_cat_uk', '')}\n\n"
            f"Введите новое название на украинском (или /skip для пропуска):",
            parse_mode='HTML'
        )
        return
    
    elif action.startswith('admin_edit_category_uk_'):
        cat_id = action.replace('admin_edit_category_uk_', '')
        
        if text != '/skip':
            context.user_data['edit_cat_uk_new'] = text
        
        context.user_data['edit_step'] = 'en'
        db.set_pending_action(user.id, f'admin_edit_category_en_{cat_id}')
        
        await update.message.reply_text(
            f"Текущее английское название: {context.user_data.get('edit_cat_en', '')}\n\n"
            f"Введите новое название на английском (или /skip для пропуска):",
            parse_mode='HTML'
        )
        return
    
    elif action.startswith('admin_edit_category_en_'):
        cat_id = action.replace('admin_edit_category_en_', '')
        
        if text != '/skip':
            context.user_data['edit_cat_en_new'] = text
        
        # Собираем все изменения
        name_ru = context.user_data.get('edit_cat_ru_new', context.user_data.get('edit_cat_ru'))
        name_uk = context.user_data.get('edit_cat_uk_new', context.user_data.get('edit_cat_uk'))
        name_en = context.user_data.get('edit_cat_en_new', context.user_data.get('edit_cat_en'))
        
        if db.update_category(cat_id, name_ru, name_uk, name_en):
            await update.message.reply_text(
                f"✅ Категория успешно обновлена!\n\n"
                f"ID: <b>{cat_id}</b>\n"
                f"🇷🇺 {name_ru}\n"
                f"🇺🇦 {name_uk}\n"
                f"🇬🇧 {name_en}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку категорий", callback_data='admin_list_categories')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]
                ]),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении категории")
        
        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


async def admin_delete_category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список категорий для удаления"""
    query = update.callback_query
    
    categories = db.get_categories('ru')
    keyboard = []
    for cat_id, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(f"❌ {cat_name}", callback_data=f'admin_delete_cat_{cat_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')])
    
    await query.edit_message_text(
        "Выберите категорию для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_delete_category_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    """Подтверждение удаления категории"""
    query = update.callback_query
    
    categories = db.get_categories('ru')
    if cat_id not in categories:
        await query.edit_message_text("❌ Категория не найдена")
        return
    
    success, message = db.delete_category(cat_id)
    if success:
        await query.edit_message_text(
            f"✅ Категория <b>{cat_id}</b> успешно удалена!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]]),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            f"❌ {message}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]]),
            parse_mode='HTML'
        )
# ===== Overrides and extended admin flows =====

async def handle_admin_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Universal photo handler for admin wizards."""
    user = update.effective_user
    pending = db.get_pending_action(user.id)
    if not pending:
        return

    action = pending[0]
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото или используйте /skip")
        return

    photo = update.message.photo[-1]
    photo_path = await download_telegram_photo(photo.file_id, context)
    if not photo_path:
        await update.message.reply_text("❌ Не удалось сохранить фото. Попробуйте ещё раз.")
        return

    if action == 'admin_add_product_photo_waiting':
        context.user_data['add_prod_photo_url'] = photo_path
        db.set_pending_action(user.id, 'admin_add_product_stock')
        await update.message.reply_text(
            "✅ Фото сохранено\n\nВведите количество на складе:\n• Число (например: 10)\n• -1 для бесконечного запаса"
        )
        return

    if action.startswith('admin_edit_') and action.endswith('_photo_waiting'):
        try:
            product_id = int(action.split('_')[2])
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Некорректный ID товара")
            db.clear_pending_action(user.id)
            return

        prod = db.get_product(product_id)
        if not prod:
            await update.message.reply_text("❌ Товар не найден")
            db.clear_pending_action(user.id)
            context.user_data.clear()
            return

        if isinstance(prod, dict):
            updates = {
                'name': context.user_data.get('edit_prod_name', prod.get('name')),
                'category': context.user_data.get('edit_prod_category', prod.get('category')),
                'price_usd': context.user_data.get('edit_prod_price', prod.get('price_usd')),
                'description': context.user_data.get('edit_prod_desc', prod.get('description')),
                'stock': context.user_data.get('edit_prod_stock', prod.get('stock')),
                'sort_order': context.user_data.get('edit_prod_sort', prod.get('sort_order')),
                'photo_url': photo_path,
            }
        else:
            updates = {
                'name': context.user_data.get('edit_prod_name', prod[2]),
                'category': context.user_data.get('edit_prod_category', prod[1]),
                'price_usd': context.user_data.get('edit_prod_price', prod[3]),
                'description': context.user_data.get('edit_prod_desc', prod[4]),
                'stock': context.user_data.get('edit_prod_stock', prod[5]),
                'sort_order': context.user_data.get('edit_prod_sort', prod[7]),
                'photo_url': photo_path,
            }

        if db.update_product(product_id, input_lang='auto', **updates):
            await update.message.reply_text(
                f"✅ Товар ID {product_id} обновлён!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку товаров", callback_data='admin_list_products')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_products')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении товара")

        db.clear_pending_action(user.id)
        context.user_data.clear()
        return

    await update.message.reply_text("❌ Сейчас фото не ожидается в этом шаге.")


async def handle_admin_add_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Add category flow: id -> ru -> uk -> en."""
    user = update.effective_user
    text = text.strip()
    step = context.user_data.get('add_category_step', 'id')

    if step == 'id':
        import re
        if not re.match(r'^[a-z0-9_]+$', text):
            await update.message.reply_text("❌ ID может содержать только a-z, 0-9 и _. Попробуйте ещё раз:")
            return
        existing = db.get_categories()
        if text in existing:
            await update.message.reply_text(f"❌ Категория с ID <b>{text}</b> уже существует. Введите другой ID:", parse_mode='HTML')
            return
        context.user_data['new_category_id'] = text
        context.user_data['add_category_step'] = 'name_ru'
        db.set_pending_action(user.id, 'admin_add_category_name_ru')
        await update.message.reply_text("Введите название на русском:")
        return

    if step == 'name_ru':
        context.user_data['new_category_name_ru'] = text
        context.user_data['add_category_step'] = 'name_uk'
        db.set_pending_action(user.id, 'admin_add_category_name_uk')
        await update.message.reply_text("Введите название на украинском (или /skip):")
        return

    if step == 'name_uk':
        context.user_data['new_category_name_uk'] = None if text == '/skip' else text
        context.user_data['add_category_step'] = 'name_en'
        db.set_pending_action(user.id, 'admin_add_category_name_en')
        await update.message.reply_text("Введите название на английском (или /skip):")
        return

    if step == 'name_en':
        context.user_data['new_category_name_en'] = None if text == '/skip' else text
        cat_id = context.user_data['new_category_id']
        name_ru = context.user_data['new_category_name_ru']
        name_uk = context.user_data.get('new_category_name_uk')
        name_en = context.user_data.get('new_category_name_en')

        if db.add_category(cat_id, name_ru, name_uk, name_en):
            await update.message.reply_text(
                "✅ Категория успешно добавлена!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку категорий", callback_data='admin_list_categories')],
                    [InlineKeyboardButton("➕ Добавить ещё", callback_data='admin_add_category')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении категории")
        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


async def handle_admin_edit_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Edit category flow: ru -> uk -> en."""
    user = update.effective_user

    if action.startswith('admin_edit_category_ru_'):
        cat_id = action.replace('admin_edit_category_ru_', '')
        if text != '/skip':
            context.user_data['edit_cat_ru_new'] = text
        db.set_pending_action(user.id, f'admin_edit_category_uk_{cat_id}')
        await update.message.reply_text("Введите новое название на украинском (или /skip):")
        return

    if action.startswith('admin_edit_category_uk_'):
        cat_id = action.replace('admin_edit_category_uk_', '')
        if text != '/skip':
            context.user_data['edit_cat_uk_new'] = text
        db.set_pending_action(user.id, f'admin_edit_category_en_{cat_id}')
        await update.message.reply_text("Введите новое название на английском (или /skip):")
        return

    if action.startswith('admin_edit_category_en_'):
        cat_id = action.replace('admin_edit_category_en_', '')
        if text != '/skip':
            context.user_data['edit_cat_en_new'] = text
        name_ru = context.user_data.get('edit_cat_ru_new', context.user_data.get('edit_cat_ru'))
        name_uk = context.user_data.get('edit_cat_uk_new', context.user_data.get('edit_cat_uk'))
        name_en = context.user_data.get('edit_cat_en_new', context.user_data.get('edit_cat_en'))
        if db.update_category(cat_id, name_ru, name_uk, name_en):
            await update.message.reply_text(
                "✅ Категория обновлена!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку категорий", callback_data='admin_list_categories')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении категории")
        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


async def handle_admin_edit_product_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Edit product flow: name -> category -> price -> desc -> stock -> sort -> photo."""
    user = update.effective_user
    text = text.strip()
    parts = action.split('_')
    if len(parts) < 4:
        db.clear_pending_action(user.id)
        return

    try:
        product_id = int(parts[2])
    except ValueError:
        db.clear_pending_action(user.id)
        await update.message.reply_text("❌ Некорректный ID товара")
        return

    field = "_".join(parts[3:])
    prod = db.get_product(product_id)
    if not prod:
        db.clear_pending_action(user.id)
        await update.message.reply_text("❌ Товар не найден")
        return

    if isinstance(prod, dict):
        current = {
            'name': prod.get('name'),
            'category': prod.get('category'),
            'price': prod.get('price_usd'),
            'desc': prod.get('description'),
            'stock': prod.get('stock'),
            'sort': prod.get('sort_order', 0),
            'photo': prod.get('photo_url'),
        }
    else:
        current = {
            'name': prod[2],
            'category': prod[1],
            'price': prod[3],
            'desc': prod[4],
            'stock': prod[5],
            'sort': prod[7] if len(prod) > 7 else 0,
            'photo': prod[8] if len(prod) > 8 else None,
        }

    if field == 'name':
        context.user_data['edit_prod_name'] = current['name'] if text == '/skip' else text
        db.set_pending_action(user.id, f'admin_edit_{product_id}_category')
        await update.message.reply_text("Введите новую категорию (или /skip):")
        return

    if field == 'category':
        categories = config.CATEGORIES
        new_category = current['category'] if text == '/skip' else text
        if text != '/skip' and new_category not in categories:
            await update.message.reply_text(f"❌ Неверная категория. Доступные: {', '.join(categories.keys())}")
            return
        context.user_data['edit_prod_category'] = new_category
        db.set_pending_action(user.id, f'admin_edit_{product_id}_price')
        await update.message.reply_text("Введите новую цену (или /skip):")
        return

    if field == 'price':
        if text == '/skip':
            context.user_data['edit_prod_price'] = current['price']
        else:
            try:
                context.user_data['edit_prod_price'] = float(text.replace(',', '.'))
            except ValueError:
                await update.message.reply_text("❌ Введите корректную цену, например 45.99")
                return
        db.set_pending_action(user.id, f'admin_edit_{product_id}_desc')
        await update.message.reply_text("Введите новое описание (или /skip):")
        return

    if field == 'desc':
        context.user_data['edit_prod_desc'] = current['desc'] if text == '/skip' else text
        db.set_pending_action(user.id, f'admin_edit_{product_id}_stock')
        await update.message.reply_text("Введите новый запас (или /skip):")
        return

    if field == 'stock':
        if text == '/skip':
            context.user_data['edit_prod_stock'] = current['stock']
        else:
            try:
                context.user_data['edit_prod_stock'] = int(text)
            except ValueError:
                await update.message.reply_text("❌ Запас должен быть целым числом")
                return
        db.set_pending_action(user.id, f'admin_edit_{product_id}_sort')
        await update.message.reply_text("Введите новый sort order (или /skip):")
        return

    if field == 'sort':
        if text == '/skip':
            context.user_data['edit_prod_sort'] = current['sort']
        else:
            try:
                context.user_data['edit_prod_sort'] = int(text)
            except ValueError:
                await update.message.reply_text("❌ sort order должен быть целым числом")
                return
        db.set_pending_action(user.id, f'admin_edit_{product_id}_photo_waiting')
        await update.message.reply_text("Отправьте новое фото товара или /skip:")
        return

    if field == 'photo_waiting' and text == '/skip':
        updates = {
            'name': context.user_data.get('edit_prod_name', current['name']),
            'category': context.user_data.get('edit_prod_category', current['category']),
            'price_usd': context.user_data.get('edit_prod_price', current['price']),
            'description': context.user_data.get('edit_prod_desc', current['desc']),
            'stock': context.user_data.get('edit_prod_stock', current['stock']),
            'sort_order': context.user_data.get('edit_prod_sort', current['sort']),
            'photo_url': current['photo'],
        }
        if db.update_product(product_id, input_lang='auto', **updates):
            await update.message.reply_text(
                f"✅ Товар ID {product_id} обновлён!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку товаров", callback_data='admin_list_products')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_products')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении товара")
        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


def _menu_target_options():
    return {
        'services': '🛒 Services',
        'balance': '💰 Balance',
        'profile': '👤 Profile',
        'referral': '🔗 Referral',
        'promo_code': '🎫 Promo code',
        'menu': '🏠 Main menu',
    }


async def admin_home_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    home = db.get_home_content()
    preview = (home.get('text_ru') or config.get_text('welcome', 'ru', name='{name}'))[:120]
    photo_state = "есть" if home.get('photo_file_id') else "нет"

    keyboard = [
        [InlineKeyboardButton("📝 Редактировать тексты", callback_data='admin_home_edit_text')],
        [InlineKeyboardButton("🖼 Обновить фото", callback_data='admin_home_edit_photo')],
        [InlineKeyboardButton("🗑 Удалить фото", callback_data='admin_home_remove_photo')],
        [InlineKeyboardButton("👀 Предпросмотр", callback_data='admin_home_preview')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')],
    ]
    await query.edit_message_text(
        f"🏠 <b>Главная страница</b>\n\n"
        f"Фото: {photo_state}\n"
        f"RU preview: <code>{preview}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_home_edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    home = db.get_home_content()

    context.user_data['home_text_ru'] = home.get('text_ru')
    context.user_data['home_text_uk'] = home.get('text_uk')
    context.user_data['home_text_en'] = home.get('text_en')
    db.set_pending_action(user.id, 'admin_home_text_ru')

    await query.edit_message_text(
        "📝 <b>Редактирование текстов главной страницы</b>\n\n"
        "Введите текст на русском.\n"
        "Можно использовать <code>{name}</code> для имени пользователя.\n"
        "Или отправьте /skip, чтобы оставить текущий.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_home_menu')]]),
        parse_mode='HTML'
    )


async def handle_admin_home_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    text = text.strip()

    if action == 'admin_home_text_ru':
        if text != '/skip':
            context.user_data['home_text_ru'] = text
        db.set_pending_action(user.id, 'admin_home_text_uk')
        await update.message.reply_text("Введите текст на украинском (или /skip):")
        return

    if action == 'admin_home_text_uk':
        if text != '/skip':
            context.user_data['home_text_uk'] = text
        db.set_pending_action(user.id, 'admin_home_text_en')
        await update.message.reply_text("Введите текст на английском (или /skip):")
        return

    if action == 'admin_home_text_en':
        if text != '/skip':
            context.user_data['home_text_en'] = text

        ok = db.save_home_content({
            'text_ru': context.user_data.get('home_text_ru'),
            'text_uk': context.user_data.get('home_text_uk'),
            'text_en': context.user_data.get('home_text_en'),
        })
        db.clear_pending_action(user.id)
        context.user_data.clear()

        if ok:
            await update.message.reply_text(
                "✅ Тексты главной страницы обновлены.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_menu')]])
            )
        else:
            await update.message.reply_text("❌ Не удалось сохранить тексты главной страницы.")


async def admin_home_edit_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    db.set_pending_action(user.id, 'admin_home_photo')
    await query.edit_message_text(
        "🖼 Отправьте фото для главной страницы.\n\n"
        "Оно будет показываться над приветственным текстом после выбора языка.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_home_menu')]])
    )


async def handle_admin_home_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте именно фото.")
        return

    photo_file_id = update.message.photo[-1].file_id
    ok = db.save_home_content({'photo_file_id': photo_file_id})
    db.clear_pending_action(user.id)

    if ok:
        await update.message.reply_text(
            "✅ Фото главной страницы обновлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_menu')]])
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить фото главной страницы.")


async def admin_home_remove_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ok = db.save_home_content({'photo_file_id': None})
    await query.edit_message_text(
        "✅ Фото главной страницы удалено." if ok else "❌ Не удалось удалить фото.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_menu')]])
    )


async def admin_home_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Отправляю предпросмотр")
    from handlers.start import send_home_screen
    user = query.from_user
    lang = (db.get_user(user.id) or {}).get('language', 'ru')
    await send_home_screen(context, user, lang, query.message.chat_id)


async def admin_menu_editor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("✏️ Core кнопки", callback_data='admin_menu_core')],
        [InlineKeyboardButton("➕ Кастомные кнопки", callback_data='admin_menu_custom')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')],
    ]
    await query.edit_message_text(
        "🔘 <b>Редактор главного меню</b>\n\n"
        "Здесь можно менять подписи стандартных кнопок и управлять дополнительными кнопками.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_menu_core_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("🛒 Services", callback_data='admin_menu_core_edit_services')],
        [InlineKeyboardButton("💰 Balance", callback_data='admin_menu_core_edit_balance')],
        [InlineKeyboardButton("👤 Profile", callback_data='admin_menu_core_edit_profile')],
        [InlineKeyboardButton("🔗 Referral", callback_data='admin_menu_core_edit_referral')],
        [InlineKeyboardButton("💸 Transfer", callback_data='admin_menu_core_edit_transfer')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_editor')],
    ]
    await query.edit_message_text(
        "✏️ <b>Core кнопки</b>\n\n"
        "Для Balance можно использовать шаблон <code>{balance}</code>.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_menu_core_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    query = update.callback_query
    core = db.get_main_menu_core()
    labels = core.get(key, {})

    await query.edit_message_text(
        "✏️ <b>Редактирование core-кнопки</b>\n\n"
        f"Ключ: <code>{html.escape(key)}</code>\n"
        f"RU: {html.escape(labels.get('ru') or '-')}\n"
        f"UK: {html.escape(labels.get('uk') or '-')}\n"
        f"EN: {html.escape(labels.get('en') or '-')}\n\n"
        "Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("RU", callback_data=f'admin_menu_core_field_{key}_ru')],
            [InlineKeyboardButton("UK", callback_data=f'admin_menu_core_field_{key}_uk')],
            [InlineKeyboardButton("EN", callback_data=f'admin_menu_core_field_{key}_en')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_core')],
        ]),
        parse_mode='HTML'
    )


async def admin_menu_core_edit_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, lang_code: str):
    query = update.callback_query
    labels = db.get_main_menu_core().get(key, {})
    context.user_data['menu_core_key'] = key
    db.set_pending_action(query.from_user.id, f'admin_menu_core_label_{lang_code}')

    await query.edit_message_text(
        f"✏️ <b>Кнопка {html.escape(key)}</b>\n\n"
        f"Текущее значение {lang_code.upper()}: {html.escape(labels.get(lang_code) or '-')}\n\n"
        "Введите новый текст или /skip, чтобы оставить текущее значение.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_core_edit_{key}')]
        ]),
        parse_mode='HTML'
    )


async def handle_admin_menu_core_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    key = context.user_data.get('menu_core_key')
    if not key:
        db.clear_pending_action(user.id)
        context.user_data.clear()
        await update.message.reply_text("❌ Сессия редактирования кнопки сброшена.")
        return

    lang_code = action.replace('admin_menu_core_label_', '')
    current = db.get_main_menu_core().get(key, {})
    if text != '/skip':
        current[lang_code] = text

    ok = db.save_main_menu_core({key: current})
    db.clear_pending_action(user.id)
    context.user_data.pop('menu_core_key', None)

    if ok:
        await update.message.reply_text(
            "✅ Core кнопка обновлена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_core_edit_{key}')]])
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить кнопку.")


def _build_custom_buttons_text() -> str:
    buttons = db.get_custom_menu_buttons()
    if not buttons:
        return "➕ <b>Кастомные кнопки</b>\n\nПока кнопок нет."

    lines = ["➕ <b>Кастомные кнопки</b>", ""]
    for button in buttons:
        lines.append(
            f"• <code>{button['id']}</code> | {button.get('type', 'callback')} | "
            f"{button.get('label_ru') or button.get('label_en') or 'Button'}"
        )
    return "\n".join(lines)


async def admin_menu_custom_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("➕ Добавить кнопку", callback_data='admin_menu_custom_add')]]

    for button in db.get_custom_menu_buttons():
        button_id = button['id']
        label = button.get('label_ru') or button.get('label_en') or 'Button'
        keyboard.append([
            InlineKeyboardButton(f"✏️ {label}", callback_data=f'admin_menu_custom_edit_{button_id}'),
            InlineKeyboardButton("🗑", callback_data=f'admin_menu_custom_delete_{button_id}')
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_editor')])
    await query.edit_message_text(
        _build_custom_buttons_text(),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_menu_custom_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['custom_menu_mode'] = 'add'
    context.user_data['custom_menu_button'] = {'id': uuid4().hex[:10], 'enabled': True}
    keyboard = [
        [InlineKeyboardButton("🔗 URL кнопка", callback_data='admin_menu_custom_type_url')],
        [InlineKeyboardButton("⚙️ Кнопка действия", callback_data='admin_menu_custom_type_callback')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_custom')],
    ]
    await query.edit_message_text(
        "Выберите тип новой кнопки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_menu_custom_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE, button_id: str):
    query = update.callback_query
    buttons = db.get_custom_menu_buttons()
    button = next((b for b in buttons if b.get('id') == button_id), None)
    if not button:
        await query.answer("Кнопка не найдена", show_alert=True)
        return

    context.user_data['custom_menu_mode'] = 'edit'
    context.user_data['custom_menu_button'] = dict(button)
    context.user_data['custom_menu_edit_id'] = button_id
    await query.edit_message_text(
        "✏️ <b>Редактирование кастомной кнопки</b>\n\n"
        f"ID: <code>{html.escape(button_id)}</code>\n"
        f"Тип: <code>{html.escape(button.get('type', 'callback'))}</code>\n"
        f"RU: {html.escape(button.get('label_ru') or '-')}\n"
        f"UK: {html.escape(button.get('label_uk') or '-')}\n"
        f"EN: {html.escape(button.get('label_en') or '-')}\n"
        f"Target: <code>{html.escape(button.get('target') or '-')}</code>\n\n"
        "Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("RU", callback_data=f'admin_menu_custom_field_{button_id}_ru')],
            [InlineKeyboardButton("UK", callback_data=f'admin_menu_custom_field_{button_id}_uk')],
            [InlineKeyboardButton("EN", callback_data=f'admin_menu_custom_field_{button_id}_en')],
            [InlineKeyboardButton("Target", callback_data=f'admin_menu_custom_field_{button_id}_target')],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f'admin_menu_custom_delete_{button_id}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_custom')],
        ]),
        parse_mode='HTML'
    )


async def admin_menu_custom_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE, button_type: str):
    query = update.callback_query
    button = context.user_data.get('custom_menu_button', {})
    button['type'] = button_type
    context.user_data['custom_menu_button'] = button
    db.set_pending_action(query.from_user.id, 'admin_menu_custom_label_ru')
    await query.edit_message_text(
        "Введите текст кнопки для RU:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_menu_custom')]])
    )


async def admin_menu_custom_edit_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, button_id: str, field: str):
    query = update.callback_query
    buttons = db.get_custom_menu_buttons()
    button = next((b for b in buttons if b.get('id') == button_id), None)
    if not button:
        await query.answer("Кнопка не найдена", show_alert=True)
        return

    context.user_data['custom_menu_mode'] = 'edit'
    context.user_data['custom_menu_button'] = dict(button)
    context.user_data['custom_menu_edit_id'] = button_id

    if field == 'target':
        if button.get('type') != 'url':
            await query.edit_message_text(
                "Выберите новое действие для кнопки:",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(label, callback_data=f'admin_menu_custom_target_{target}')]
                     for target, label in _menu_target_options().items()] +
                    [[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_custom_edit_{button_id}')]]
                )
            )
            return

        action = 'admin_menu_custom_url'
        current_value = button.get('target') or '-'
        hint = "Введите новый URL"
    else:
        action = f'admin_menu_custom_label_{field}'
        current_value = button.get(f'label_{field}') or '-'
        hint = "Введите новый текст"

    db.set_pending_action(query.from_user.id, action)
    await query.edit_message_text(
        "✏️ <b>Редактирование кастомной кнопки</b>\n\n"
        f"Текущее значение: {html.escape(current_value)}\n\n"
        f"{hint} или /skip, чтобы оставить текущее.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_custom_edit_{button_id}')]
        ]),
        parse_mode='HTML'
    )


def _save_custom_menu_button(button: dict, edit_id: str = None) -> bool:
    button.setdefault('sort_order', len(db.get_custom_menu_buttons()))
    button.setdefault('created_at', datetime.now().isoformat())

    buttons = db.get_custom_menu_buttons()
    if edit_id:
        buttons = [b for b in buttons if b.get('id') != edit_id]
    buttons.append(button)
    return db.save_custom_menu_buttons(buttons)


async def handle_admin_menu_custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    button = context.user_data.get('custom_menu_button')
    if not button:
        db.clear_pending_action(user.id)
        context.user_data.clear()
        await update.message.reply_text("❌ Сессия редактирования кнопки сброшена.")
        return

    if action == 'admin_menu_custom_label_ru':
        if text != '/skip' or context.user_data.get('custom_menu_mode') == 'add':
            button['label_ru'] = text
        if context.user_data.get('custom_menu_mode') == 'edit':
            ok = _save_custom_menu_button(button, context.user_data.get('custom_menu_edit_id'))
            db.clear_pending_action(user.id)
            await update.message.reply_text(
                "✅ Кастомная кнопка обновлена." if ok else "❌ Не удалось сохранить кастомную кнопку.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_menu_custom_edit_{button['id']}")]])
            )
            return
        db.set_pending_action(user.id, 'admin_menu_custom_label_uk')
        await update.message.reply_text("Введите текст кнопки для UK (или /skip):")
        return

    if action == 'admin_menu_custom_label_uk':
        if text != '/skip':
            button['label_uk'] = text
        if context.user_data.get('custom_menu_mode') == 'edit':
            ok = _save_custom_menu_button(button, context.user_data.get('custom_menu_edit_id'))
            db.clear_pending_action(user.id)
            await update.message.reply_text(
                "✅ Кастомная кнопка обновлена." if ok else "❌ Не удалось сохранить кастомную кнопку.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_menu_custom_edit_{button['id']}")]])
            )
            return
        db.set_pending_action(user.id, 'admin_menu_custom_label_en')
        await update.message.reply_text("Введите текст кнопки для EN (или /skip):")
        return

    if action == 'admin_menu_custom_label_en':
        if text != '/skip':
            button['label_en'] = text
        if context.user_data.get('custom_menu_mode') == 'edit':
            ok = _save_custom_menu_button(button, context.user_data.get('custom_menu_edit_id'))
            db.clear_pending_action(user.id)
            await update.message.reply_text(
                "✅ Кастомная кнопка обновлена." if ok else "❌ Не удалось сохранить кастомную кнопку.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"admin_menu_custom_edit_{button['id']}")]])
            )
            return

        if button.get('type') == 'url':
            db.set_pending_action(user.id, 'admin_menu_custom_url')
            await update.message.reply_text("Введите URL кнопки (или /skip, чтобы оставить текущий):")
        else:
            db.clear_pending_action(user.id)
            await update.message.reply_text(
                "Выберите действие для кнопки:",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(label, callback_data=f'admin_menu_custom_target_{target}')]
                     for target, label in _menu_target_options().items()] +
                    [[InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_custom')]]
                )
            )
        return

    if action in {'admin_menu_custom_url', 'admin_menu_custom_target_text'}:
        if text != '/skip':
            if action == 'admin_menu_custom_url' and not (text.startswith('http://') or text.startswith('https://')):
                await update.message.reply_text("❌ URL должен начинаться с http:// или https://")
                return
            button['target'] = text
        elif not button.get('target'):
            await update.message.reply_text("❌ Для новой кнопки нужно указать target.")
            return
        ok = _save_custom_menu_button(button, context.user_data.get('custom_menu_edit_id'))
        db.clear_pending_action(user.id)

        if ok:
            await update.message.reply_text(
                "✅ Кастомная кнопка сохранена.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                    "◀️ Назад",
                    callback_data=f"admin_menu_custom_edit_{button['id']}" if context.user_data.get('custom_menu_mode') == 'edit' else 'admin_menu_custom'
                )]])
            )
        else:
            await update.message.reply_text("❌ Не удалось сохранить кастомную кнопку.")


async def admin_menu_custom_choose_target(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    query = update.callback_query
    button = context.user_data.get('custom_menu_button')
    if not button:
        await query.answer("Сессия редактирования кнопки потеряна", show_alert=True)
        return

    button['target'] = target
    ok = _save_custom_menu_button(button, context.user_data.get('custom_menu_edit_id'))
    db.clear_pending_action(query.from_user.id)

    await query.edit_message_text(
        "✅ Кастомная кнопка сохранена." if ok else "❌ Не удалось сохранить кастомную кнопку.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            "◀️ Назад",
            callback_data=f"admin_menu_custom_edit_{button['id']}" if context.user_data.get('custom_menu_mode') == 'edit' else 'admin_menu_custom'
        )]])
    )


async def admin_menu_custom_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, button_id: str):
    query = update.callback_query
    buttons = [b for b in db.get_custom_menu_buttons() if b.get('id') != button_id]
    ok = db.save_custom_menu_buttons(buttons)
    await query.edit_message_text(
        "✅ Кнопка удалена." if ok else "❌ Не удалось удалить кнопку.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_custom')]])
    )
