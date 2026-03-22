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
            [InlineKeyboardButton("📬 Заказы", callback_data='admin_orders')],
            [InlineKeyboardButton("🏠 Главная страница", callback_data='admin_home_menu')],
            [InlineKeyboardButton("🔘 Главное меню", callback_data='admin_menu_editor')],
            [InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')],
            [InlineKeyboardButton("📈 Продажи", callback_data='admin_sales')],
            [InlineKeyboardButton("👑 Управление админами", callback_data='admin_admins')],
            [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
        ]
        await _edit_or_send(query, 
            "👑 <b>Админ-панель</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data == 'admin_stats':
        await admin_stats(update, context)

    elif data == 'admin_products':
        await admin_products_menu(update, context)
    elif data == 'admin_orders':
        await admin_orders(update, context)
    elif data.startswith('admin_order_') and '_status_' not in data:
        try:
            await admin_order_details(update, context, int(data.replace('admin_order_', '', 1)))
        except ValueError:
            await query.answer("Некорректный ID заказа", show_alert=True)
    elif data.startswith('admin_order_status_'):
        try:
            payload = data.replace('admin_order_status_', '', 1)
            order_id_str, status = payload.split('_', 1)
            await admin_order_update_status(update, context, int(order_id_str), status)
        except ValueError:
            await query.answer("Некорректный статус заказа", show_alert=True)

    elif data == 'admin_home_menu':
        await admin_home_menu(update, context)
    elif data == 'admin_home_edit_text':
        await admin_home_edit_text_start(update, context)
    elif data.startswith('admin_home_edit_text_'):
        await admin_home_edit_text_lang_start(update, context, data.replace('admin_home_edit_text_', '', 1))
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
    elif data.startswith('admin_menu_core_photo_remove_'):
        await admin_menu_core_remove_photo(update, context, data.replace('admin_menu_core_photo_remove_', ''))
    elif data.startswith('admin_menu_core_photo_'):
        await admin_menu_core_edit_photo_start(update, context, data.replace('admin_menu_core_photo_', ''))
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

    # Управление подкатегориями
    elif data == 'admin_subcategories_menu':
        await admin_subcategories_menu(update, context)
    elif data == 'admin_list_subcategories':
        await admin_list_subcategories(update, context)
    elif data == 'admin_sort_subcategories':
        await admin_sort_subcategories(update, context)
    elif data.startswith('admin_move_subcat_'):
        payload = data.replace('admin_move_subcat_', '', 1)
        direction, subcat_id = payload.split('_', 1)
        await admin_move_subcategory(update, context, subcat_id, direction)
    elif data == 'admin_add_subcategory':
        await admin_add_subcategory_start(update, context)
    elif data == 'admin_edit_subcategory':
        await admin_edit_subcategory_list(update, context)
    elif data.startswith('admin_subcat_field_'):
        payload = data.replace('admin_subcat_field_', '', 1)
        parsed = False
        for field in ('parent', 'name_ru', 'name_uk', 'name_en', 'photo'):
            suffix = f'_{field}'
            if payload.endswith(suffix):
                subcat_id = payload[:-len(suffix)]
                await admin_edit_subcategory_field_start(update, context, subcat_id, field)
                parsed = True
                break
        if not parsed:
            await query.answer("Некорректная подкатегория", show_alert=True)
    elif data.startswith('admin_subcat_toggle_'):
        await admin_toggle_subcategory_status(update, context, data.replace('admin_subcat_toggle_', '', 1))
    elif data.startswith('admin_subcat_duplicate_'):
        await admin_duplicate_subcategory(update, context, data.replace('admin_subcat_duplicate_', '', 1))
    elif data.startswith('admin_subcat_photo_remove_'):
        await admin_remove_subcategory_photo(update, context, data.replace('admin_subcat_photo_remove_', '', 1))
    elif data.startswith('admin_edit_subcat_'):
        subcat_id = data[len('admin_edit_subcat_'):]
        await admin_edit_subcategory_start(update, context, subcat_id)
    elif data == 'admin_delete_subcategory':
        await admin_delete_subcategory_list(update, context)
    elif data.startswith('admin_delete_subcat_'):
        subcat_id = data[len('admin_delete_subcat_'):]
        await admin_delete_subcategory_confirm(update, context, subcat_id)

    elif data == 'admin_list_categories':
        await admin_list_categories(update, context)
    elif data == 'admin_sort_categories':
        await admin_sort_categories(update, context)
    elif data.startswith('admin_move_cat_'):
        payload = data.replace('admin_move_cat_', '', 1)
        direction, cat_id = payload.split('_', 1)
        await admin_move_category(update, context, cat_id, direction)

    elif data == 'admin_add_category':
        await admin_add_category_start(update, context)

    elif data == 'admin_edit_category':
        await admin_edit_category_list(update, context)

    elif data.startswith('admin_edit_cat_text_'):
        cat_id = data.replace('admin_edit_cat_text_', '', 1)
        await admin_edit_category_text_start(update, context, cat_id)
    elif data.startswith('admin_category_toggle_'):
        await admin_toggle_category_status(update, context, data.replace('admin_category_toggle_', '', 1))
    elif data.startswith('admin_category_duplicate_'):
        await admin_duplicate_category(update, context, data.replace('admin_category_duplicate_', '', 1))
    elif data.startswith('admin_edit_cat_photo_remove_'):
        cat_id = data.replace('admin_edit_cat_photo_remove_', '', 1)
        await admin_remove_category_photo(update, context, cat_id)
    elif data.startswith('admin_edit_cat_photo_'):
        cat_id = data.replace('admin_edit_cat_photo_', '', 1)
        await admin_edit_category_photo_start(update, context, cat_id)
    elif data.startswith('admin_edit_cat_'):
        cat_id = data[15:]  # обрезаем 'admin_edit_cat_'
        await admin_edit_category_start(update, context, cat_id)

    elif data == 'admin_delete_category':
        await admin_delete_category_list(update, context)

    elif data.startswith('admin_delete_cat_'):
        cat_id = data[len('admin_delete_cat_'):]  # обрезаем 'admin_delete_cat_'
        await admin_delete_category_confirm(update, context, cat_id)

    elif data == 'admin_balance_menu':
        from handlers.admin_balance import admin_balance_menu
        await admin_balance_menu(update, context)

    elif data == 'admin_add_balance':
        from handlers.admin_balance import admin_add_balance_start
        await admin_add_balance_start(update, context)
    elif data == 'admin_search_user':
        from handlers.admin_balance import admin_search_user_start
        await admin_search_user_start(update, context)
    elif data == 'admin_top_users':
        from handlers.admin_balance import admin_show_top_users
        await admin_show_top_users(update, context)
    elif data.startswith('admin_balance_user_'):
        from handlers.admin_balance import admin_show_user_card
        await admin_show_user_card(update, context, int(data.replace('admin_balance_user_', '')))
    elif data.startswith('admin_balance_credit_'):
        from handlers.admin_balance import admin_balance_change_start
        await admin_balance_change_start(update, context, int(data.replace('admin_balance_credit_', '')), 'credit')
    elif data.startswith('admin_balance_debit_'):
        from handlers.admin_balance import admin_balance_change_start
        await admin_balance_change_start(update, context, int(data.replace('admin_balance_debit_', '')), 'debit')

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

    elif data.startswith('admin_edit_product_field_'):
        payload = data.replace('admin_edit_product_field_', '', 1)
        try:
            pid_str, field = payload.split('_', 1)
            await admin_edit_product_field_start(update, context, int(pid_str), field)
        except ValueError:
            await query.answer("Некорректный ID товара", show_alert=True)

    elif data.startswith('admin_product_toggle_'):
        await admin_toggle_product_status(update, context, int(data.replace('admin_product_toggle_', '')))

    elif data.startswith('admin_product_duplicate_'):
        await admin_duplicate_product(update, context, int(data.replace('admin_product_duplicate_', '')))

    elif data.startswith('admin_product_multibuy_'):
        await admin_toggle_product_multi_quantity(update, context, int(data.replace('admin_product_multibuy_', '')))

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
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    keyboard = [
        [InlineKeyboardButton("📂 Управление категориями", callback_data='admin_categories_menu')],
        [InlineKeyboardButton("➕ Добавить товар", callback_data='admin_add_product')],
        [InlineKeyboardButton("✏️ Редактировать товар", callback_data='admin_edit_product')],
        [InlineKeyboardButton("❌ Удалить товар", callback_data='admin_delete_product')],
        [InlineKeyboardButton("📋 Список товаров", callback_data='admin_list_products')],
        [InlineKeyboardButton("📬 Заказы", callback_data='admin_orders')],
        [InlineKeyboardButton("💰 Управление балансами", callback_data='admin_balance_menu')],
        [InlineKeyboardButton("🎫 Промокоды", callback_data='admin_promo_menu')],
        [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast_menu')],
        [InlineKeyboardButton("🐛 Отладка", callback_data='admin_debug')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]

    await _edit_or_send(query, 
        "📦 <b>Управление товарами и категориями</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.get_products(show_all=True)
    if not products:
        await _edit_or_send(query, "📭 Товаров нет")
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
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    for k in list(context.user_data.keys()):
        if k.startswith('add_prod_'):
            del context.user_data[k]

    db.set_pending_action(user.id, 'admin_add_product_name')

    await _edit_or_send(query, 
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

        subcats = db.get_subcategories(text, lang='ru')
        if subcats:
            db.set_pending_action(user.id, 'admin_add_product_subcategory')
            await update.message.reply_text(
                "✅ Категория сохранена\n\n"
                "Введите ID подкатегории (или /skip если не нужно):\n"
                f"Доступные: {', '.join(subcats.keys())}"
            )
        else:
            context.user_data['add_prod_subcategory'] = None
            db.set_pending_action(user.id, 'admin_add_product_price')
            await update.message.reply_text(
                "✅ Категория сохранена\n\n"
                "Введите цену в $ (например 45.99).\n"
                "Для информационной карточки без покупки укажите -1:"
            )
        return

    elif action == 'admin_add_product_subcategory':
        category = context.user_data.get('add_prod_category')
        subcats = db.get_subcategories(category, lang='ru') if category else {}
        if text == '/skip':
            context.user_data['add_prod_subcategory'] = None
            db.set_pending_action(user.id, 'admin_add_product_price')
            await update.message.reply_text(
                "✅ Подкатегория пропущена\n\n"
                "Введите цену в $ (например 45.99).\n"
                "Для информационной карточки без покупки укажите -1:"
            )
            return

        if text not in subcats:
            await update.message.reply_text(f"❌ Неверная подкатегория. Доступные: {', '.join(subcats.keys())}")
            return

        context.user_data['add_prod_subcategory'] = text
        db.set_pending_action(user.id, 'admin_add_product_price')
        await update.message.reply_text(
            "✅ Подкатегория сохранена\n\n"
            "Введите цену в $ (например 45.99).\n"
            "Для информационной карточки без покупки укажите -1:"
        )
        return

    elif action == 'admin_add_product_price':
        try:
            price = float(text.replace(',', '.'))
            context.user_data['add_prod_price'] = price
            db.set_pending_action(user.id, 'admin_add_product_desc')
            await update.message.reply_text("✅ Цена сохранена\n\nВведите описание (или /skip):")
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число (например 45.99 или -1)")
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
                subcategory=context.user_data.get('add_prod_subcategory'),
                name=context.user_data['add_prod_name'],
                price=float(context.user_data['add_prod_price']),
                description=context.user_data.get('add_prod_desc'),
                stock=int(context.user_data['add_prod_stock']),
                sort_order=sort_order,
                photo_url=context.user_data.get('add_prod_photo_url'),
                input_lang=input_lang,
                is_active=0
            )

            db.clear_pending_action(user.id)
            context.user_data.clear()

            await update.message.reply_text(
                "🎉 Товар создан в черновиках!",
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
        await _edit_or_send(query, "📭 Нет товаров для редактирования")
        return

    keyboard = []
    for prod in products[:10]:
        if isinstance(prod, dict):
            pid = prod.get('id')
            name = prod.get('name', 'Без названия')
            is_active = prod.get('is_active', 1)
        else:
            pid = prod[0]
            name = prod[2]
            is_active = prod[7] if len(prod) > 7 else 1
        
        status = "✅" if is_active else "📝"
        keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f'admin_edit_{pid}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_products')])

    await _edit_or_send(query, 
        "Выберите товар для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_edit_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query

    prod = db.get_product(product_id)
    if not prod:
        await _edit_or_send(query, "❌ Товар не найден")
        return

    db.clear_pending_action(query.from_user.id)
    for key in list(context.user_data.keys()):
        if key.startswith('edit_prod_'):
            del context.user_data[key]

    await _edit_or_send(
        query,
        _build_product_edit_text(product_id, prod),
        reply_markup=InlineKeyboardMarkup(_build_product_edit_keyboard(product_id)),
        parse_mode='HTML'
    )


def _get_product_edit_current(prod):
    if isinstance(prod, dict):
        return {
            'name': prod.get('name'),
            'category': prod.get('category'),
            'subcategory': prod.get('subcategory'),
            'price': prod.get('price_usd'),
            'desc': prod.get('description'),
            'stock': prod.get('stock'),
            'allow_multi_quantity': prod.get('allow_multi_quantity', 1),
            'sort': prod.get('sort_order', 0),
            'photo': prod.get('photo_url'),
        }

    return {
        'name': prod[2],
        'category': prod[1],
        'subcategory': None,
        'price': prod[3],
        'desc': prod[4],
        'stock': prod[5],
        'allow_multi_quantity': 1,
        'sort': prod[7] if len(prod) > 7 else 0,
        'photo': prod[8] if len(prod) > 8 else None,
    }


def _build_product_edit_keyboard(product_id: int):
    product = db.get_product(product_id) or {}
    is_active = product.get('is_active', 1) if isinstance(product, dict) else 1
    allow_multi = bool(product.get('allow_multi_quantity', 1)) if isinstance(product, dict) else True
    publish_label = "📤 Опубликовать" if not is_active else "📝 В черновик"
    multi_label = "🔢 Кол-во: несколько" if allow_multi else "1️⃣ Кол-во: только 1"
    return [
        [
            InlineKeyboardButton("📝 Название", callback_data=f'admin_edit_product_field_{product_id}_name'),
            InlineKeyboardButton("📂 Категория", callback_data=f'admin_edit_product_field_{product_id}_category'),
        ],
        [
            InlineKeyboardButton("📁 Подкатегория", callback_data=f'admin_edit_product_field_{product_id}_subcategory'),
            InlineKeyboardButton("💵 Цена", callback_data=f'admin_edit_product_field_{product_id}_price'),
        ],
        [
            InlineKeyboardButton("📄 Описание", callback_data=f'admin_edit_product_field_{product_id}_desc'),
            InlineKeyboardButton("📦 Запас", callback_data=f'admin_edit_product_field_{product_id}_stock'),
        ],
        [
            InlineKeyboardButton("↕️ Sort order", callback_data=f'admin_edit_product_field_{product_id}_sort'),
            InlineKeyboardButton("🖼 Фото", callback_data=f'admin_edit_product_field_{product_id}_photo'),
        ],
        [
            InlineKeyboardButton(multi_label, callback_data=f'admin_product_multibuy_{product_id}'),
        ],
        [
            InlineKeyboardButton(publish_label, callback_data=f'admin_product_toggle_{product_id}'),
            InlineKeyboardButton("📄 Дублировать", callback_data=f'admin_product_duplicate_{product_id}'),
        ],
        [
            InlineKeyboardButton("📋 К списку товаров", callback_data='admin_edit_product'),
            InlineKeyboardButton("◀️ Назад", callback_data='admin_products'),
        ],
    ]


def _build_product_edit_text(product_id: int, prod) -> str:
    current = _get_product_edit_current(prod)
    stock_value = current['stock']
    stock_str = '∞' if isinstance(stock_value, int) and stock_value < 0 else str(stock_value)
    photo_str = "есть" if current.get('photo') else "нет"
    multi_str = "несколько копий" if current.get('allow_multi_quantity', 1) else "только 1 копия"
    status_str = _draft_status_label(prod.get('is_active', 1) if isinstance(prod, dict) else 1)
    desc = current.get('desc') or 'нет'
    if len(desc) > 200:
        desc = desc[:197] + '...'

    return (
        f"✏️ <b>Редактирование товара ID {product_id}</b>\n\n"
        f"Название: {html.escape(current.get('name') or 'Без названия')}\n"
        f"Категория: <code>{html.escape(current.get('category') or '-')}</code>\n"
        f"Подкатегория: <code>{html.escape(current.get('subcategory') or '-')}</code>\n"
        f"Цена: ${current.get('price')}\n"
        f"Запас: {stock_str}\n"
        f"Покупка: {multi_str}\n"
        f"Sort order: {current.get('sort', 0)}\n"
        f"Статус: {status_str}\n"
        f"Фото: {photo_str}\n"
        f"Описание: {html.escape(desc)}\n\n"
        f"Выберите, что хотите изменить:"
    )


def _format_choice_list(options: dict[str, str]) -> str:
    if not options:
        return "нет"
    return "\n".join(f"• <code>{html.escape(key)}</code> — {html.escape(value or '-')}" for key, value in options.items())


def _draft_status_label(is_active: int | None) -> str:
    return "✅ Опубликовано" if is_active else "📝 Черновик"


def _parse_product_edit_action(action: str):
    if action.startswith('admin_edit_product_'):
        payload = action.replace('admin_edit_product_', '', 1)
        parts = payload.split('_')
        if len(parts) >= 2 and parts[0].isdigit():
            return int(parts[0]), "_".join(parts[1:])

    if action.startswith('admin_edit_'):
        parts = action.split('_')
        if len(parts) >= 4 and parts[2].isdigit():
            return int(parts[2]), "_".join(parts[3:])

    return None, None


async def admin_edit_product_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int, field: str):
    query = update.callback_query
    prod = db.get_product(product_id)
    if not prod:
        await _edit_or_send(query, "❌ Товар не найден")
        return

    current = _get_product_edit_current(prod)
    user = query.from_user
    db.set_pending_action(user.id, f'admin_edit_product_{product_id}_{field}')

    if field == 'name':
        text = (
            f"✏️ <b>Название товара ID {product_id}</b>\n\n"
            f"Текущее значение: {html.escape(current.get('name') or 'Без названия')}\n\n"
            "Введите новое название или /skip, чтобы оставить текущее."
        )
    elif field == 'category':
        categories = db.get_categories('ru', include_inactive=True)
        text = (
            f"✏️ <b>Категория товара ID {product_id}</b>\n\n"
            f"Текущая категория: <code>{html.escape(current.get('category') or '-')}</code>\n\n"
            f"Доступные категории:\n{_format_choice_list(categories)}\n\n"
            "Введите ID новой категории или /skip, чтобы оставить текущую."
        )
    elif field == 'subcategory':
        category = current.get('category')
        subcats = db.get_subcategories(category, lang='ru') if category else {}
        if subcats:
            choices = _format_choice_list(subcats)
            helper = (
                f"Доступные подкатегории для <code>{html.escape(category)}</code>:\n{choices}\n\n"
                "Введите ID новой подкатегории, /skip чтобы оставить текущую, или /none чтобы очистить."
            )
        else:
            helper = (
                "Для текущей категории подкатегорий нет.\n\n"
                "Отправьте /none чтобы очистить подкатегорию или /skip чтобы оставить как есть."
            )
        text = (
            f"✏️ <b>Подкатегория товара ID {product_id}</b>\n\n"
            f"Текущая подкатегория: <code>{html.escape(current.get('subcategory') or '-')}</code>\n\n"
            f"{helper}"
        )
    elif field == 'price':
        text = (
            f"✏️ <b>Цена товара ID {product_id}</b>\n\n"
            f"Текущее значение: ${current.get('price')}\n\n"
            "Введите новую цену или /skip, чтобы оставить текущее значение.\n"
            "Для информационной карточки можно указать <code>-1</code>."
        )
    elif field == 'desc':
        text = (
            f"✏️ <b>Описание товара ID {product_id}</b>\n\n"
            f"Текущее значение:\n{html.escape(current.get('desc') or 'нет')}\n\n"
            "Введите новое описание или /skip, чтобы оставить текущее."
        )
    elif field == 'stock':
        text = (
            f"✏️ <b>Запас товара ID {product_id}</b>\n\n"
            f"Текущее значение: {current.get('stock')}\n\n"
            "Введите новый запас или /skip, чтобы оставить текущее.\n"
            "Используйте <code>-1</code> для бесконечного запаса."
        )
    elif field == 'sort':
        text = (
            f"✏️ <b>Sort order товара ID {product_id}</b>\n\n"
            f"Текущее значение: {current.get('sort', 0)}\n\n"
            "Введите новый sort order или /skip, чтобы оставить текущее."
        )
    elif field == 'photo':
        db.set_pending_action(user.id, f'admin_edit_product_{product_id}_photo_waiting')
        text = (
            f"✏️ <b>Фото товара ID {product_id}</b>\n\n"
            f"Сейчас фото: {'есть' if current.get('photo') else 'нет'}\n\n"
            "Отправьте новое фото или /skip, чтобы оставить текущее."
        )
    else:
        db.clear_pending_action(user.id)
        await query.answer("Неизвестное поле", show_alert=True)
        return

    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад к товару", callback_data=f'admin_edit_{product_id}')],
        ]),
        parse_mode='HTML'
    )


async def admin_toggle_product_status(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query
    prod = db.get_product(product_id)
    if not prod:
        await query.answer("Товар не найден", show_alert=True)
        return

    new_status = 0 if prod.get('is_active', 1) else 1
    ok = db.update_product(product_id, is_active=new_status)
    if ok:
        await query.answer("Статус товара обновлён", show_alert=False)
        await admin_edit_product_start(update, context, product_id)
    else:
        await query.answer("Не удалось изменить статус", show_alert=True)


async def admin_duplicate_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query
    new_id = db.duplicate_product_to_draft(product_id)
    if not new_id:
        await query.answer("Не удалось создать дубликат", show_alert=True)
        return

    await query.answer("Создан дубликат в черновиках", show_alert=False)
    await admin_edit_product_start(update, context, new_id)


async def admin_toggle_product_multi_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query
    prod = db.get_product(product_id)
    if not prod:
        await query.answer("Товар не найден", show_alert=True)
        return

    new_value = 0 if prod.get('allow_multi_quantity', 1) else 1
    ok = db.update_product(product_id, allow_multi_quantity=new_value, is_active=0)
    if ok:
        await query.answer("Режим покупки обновлён", show_alert=False)
        await admin_edit_product_start(update, context, product_id)
    else:
        await query.answer("Не удалось изменить режим покупки", show_alert=True)


async def admin_delete_product_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    products = db.get_products(show_all=True)
    if not products:
        await _edit_or_send(query, "📭 Нет товаров для удаления")
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

    await _edit_or_send(query, 
        "Выберите товар для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_delete_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query

    db.delete_product(product_id)
    await _edit_or_send(query, f"✅ Товар ID {product_id} удален")

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
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    stats = db.execute("SELECT COUNT(*) as count, SUM(balance) as total FROM users", fetch=True)[0]
    
    if db.use_postgres:
        total_users = stats['count'] if stats else 0
        total_balance = stats['total'] or 0
    else:
        total_users = stats[0] if stats else 0
        total_balance = stats[1] or 0

    users = db.export_users()
    normalized_users = []
    for row in users:
        if db.use_postgres:
            item = dict(row)
        else:
            item = {
                'user_id': row[0],
                'username': row[1],
                'balance': row[2],
                'registered_date': row[3],
                'last_active': row[4],
            }
        normalized_users.append(item)

    normalized_users.sort(
        key=lambda u: (
            str(u.get('registered_date') or ''),
            int(u.get('user_id') or 0),
        ),
        reverse=True
    )
    
    text = (
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: {total_users}\n"
        f"Общий баланс: ${total_balance:.2f}\n"
        f"Средний баланс: ${((total_balance / total_users) if total_users else 0):.2f}\n\n"
    )

    if not normalized_users:
        text += "Пользователей пока нет."
    else:
        text += "<b>Список пользователей:</b>\n\n"
        for user in normalized_users[:50]:
            username = f"@{user['username']}" if user.get('username') else '—'
            reg_date = str(user.get('registered_date') or '—')[:19]
            last_active = str(user.get('last_active') or '—')[:19]
            balance = float(user.get('balance') or 0)
            text += (
                f"• <code>{user.get('user_id')}</code> | {html.escape(username)}\n"
                f"  Баланс: ${balance:.2f}\n"
                f"  Регистрация: {html.escape(reg_date)}\n"
                f"  Активность: {html.escape(last_active)}\n\n"
            )

        if len(normalized_users) > 50:
            text += f"… и ещё {len(normalized_users) - 50} пользователей"
    
    keyboard = [
        [InlineKeyboardButton("💰 Управление балансами", callback_data='admin_balance_menu')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')],
    ]
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


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
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


def _admin_order_status_label(status: str) -> str:
    labels = {
        'pending': '🕒 Ожидает',
        'in_progress': '⚙️ В работе',
        'completed': '✅ Завершён',
        'cancelled': '❌ Отменён',
    }
    return labels.get(status, status)


def _format_order_user(order: dict) -> str:
    username = order.get('username')
    return f"@{username}" if username else f"ID {order.get('user_id')}"


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    orders = db.get_recent_orders(limit=20)

    if not orders:
        await _edit_or_send(
            query,
            "📬 <b>Заказы</b>\n\nЗаказов пока нет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin')]]),
            parse_mode='HTML'
        )
        return

    text = "📬 <b>Последние заказы</b>\n\n"
    keyboard = []

    for order in orders:
        purchase_date = order.get('purchase_date') or ''
        try:
            purchase_date = datetime.fromisoformat(purchase_date).strftime('%d.%m %H:%M')
        except Exception:
            purchase_date = order.get('purchase_date') or '-'

        text += (
            f"• #{order['id']} — {order['product_name']}\n"
            f"  {_format_order_user(order)} · ${order['amount']}\n"
            f"  {_admin_order_status_label(order.get('status') or 'completed')} · {purchase_date}\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(
                f"#{order['id']} · {order['product_name'][:22]}",
                callback_data=f"admin_order_{order['id']}"
            )
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin')])
    await _edit_or_send(query, text[:3900], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    query = update.callback_query
    order = db.get_order(order_id)
    if not order:
        await query.answer("Заказ не найден", show_alert=True)
        return

    purchase_date = order.get('purchase_date') or '-'
    completed_date = order.get('completed_date') or '—'
    try:
        purchase_date = datetime.fromisoformat(purchase_date).strftime('%d.%m.%Y %H:%M')
    except Exception:
        pass
    try:
        completed_date = datetime.fromisoformat(completed_date).strftime('%d.%m.%Y %H:%M') if completed_date != '—' else completed_date
    except Exception:
        pass

    text = (
        f"📦 <b>Заказ #{order['id']}</b>\n\n"
        f"👤 Покупатель: {_format_order_user(order)}\n"
        f"🆔 User ID: <code>{order['user_id']}</code>\n"
        f"📦 Товар: {html.escape(order['product_name'])}\n"
        f"💰 Сумма: ${order['amount']:.2f}\n"
        f"📅 Создан: {purchase_date}\n"
        f"✅ Завершён: {completed_date}\n"
        f"🏷 Статус: {_admin_order_status_label(order.get('status') or 'completed')}"
    )

    keyboard = [
        [InlineKeyboardButton("🕒 Ожидает", callback_data=f"admin_order_status_{order_id}_pending")],
        [InlineKeyboardButton("⚙️ В работе", callback_data=f"admin_order_status_{order_id}_in_progress")],
        [InlineKeyboardButton("✅ Завершён", callback_data=f"admin_order_status_{order_id}_completed")],
        [InlineKeyboardButton("❌ Отменён", callback_data=f"admin_order_status_{order_id}_cancelled")],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_orders')],
    ]
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_order_update_status(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int, status: str):
    query = update.callback_query
    valid_statuses = {'pending', 'in_progress', 'completed', 'cancelled'}
    if status not in valid_statuses:
        await query.answer("Некорректный статус", show_alert=True)
        return

    order = db.get_order(order_id)
    if not order:
        await query.answer("Заказ не найден", show_alert=True)
        return

    if not db.update_order_status(order_id, status):
        await query.answer("Не удалось обновить статус", show_alert=True)
        return

    try:
        await context.bot.send_message(
            order['user_id'],
            (
                f"📦 Статус заказа #{order_id} обновлён.\n\n"
                f"Товар: {order['product_name']}\n"
                f"Статус: {_admin_order_status_label(status)}"
            )
        )
    except Exception:
        pass

    await admin_order_details(update, context, order_id)

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

    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    db.set_pending_action(user.id, 'admin_add_admin')

    await _edit_or_send(query, 
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

    await _edit_or_send(query, 
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

    await _edit_or_send(query, 
        f"✅ Администратор с ID {admin_id} удален!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_admins')]])
    )


# ===== УПРАВЛЕНИЕ КАТЕГОРИЯМИ (МУЛЬТИЯЗЫЧНАЯ ВЕРСИЯ) =====

async def admin_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления категориями"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📋 Список категорий", callback_data='admin_list_categories')],
        [InlineKeyboardButton("↕️ Сортировка категорий", callback_data='admin_sort_categories')],
        [InlineKeyboardButton("📁 Подкатегории", callback_data='admin_subcategories_menu')],
        [InlineKeyboardButton("➕ Добавить категорию", callback_data='admin_add_category')],
        [InlineKeyboardButton("✏️ Редактировать категорию", callback_data='admin_edit_category')],
        [InlineKeyboardButton("❌ Удалить категорию", callback_data='admin_delete_category')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]
    
    await _edit_or_send(query, 
        "📂 <b>Управление категориями</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_subcategories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления подкатегориями"""
    query = update.callback_query

    keyboard = [
        [InlineKeyboardButton("📋 Список подкатегорий", callback_data='admin_list_subcategories')],
        [InlineKeyboardButton("↕️ Сортировка подкатегорий", callback_data='admin_sort_subcategories')],
        [InlineKeyboardButton("➕ Добавить подкатегорию", callback_data='admin_add_subcategory')],
        [InlineKeyboardButton("✏️ Редактировать подкатегорию", callback_data='admin_edit_subcategory')],
        [InlineKeyboardButton("❌ Удалить подкатегорию", callback_data='admin_delete_subcategory')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')],
    ]

    await _edit_or_send(
        query,
        "📁 <b>Управление подкатегориями</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_list_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список подкатегорий"""
    query = update.callback_query

    subcats = db.get_all_subcategories()
    categories_ru = db.get_categories('ru', include_inactive=True)

    if not subcats:
        await _edit_or_send(
            query,
            "📭 Подкатегорий нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]]),
        )
        return

    text = "📋 <b>Список подкатегорий:</b>\n\n"
    for s in subcats:
        parent = s.get('parent_cat_id')
        parent_name = categories_ru.get(parent, parent)
        status = "✅" if s.get('is_active', 1) else "📝"
        text += f"{status} <b>{s.get('subcat_id')}</b> → <i>{parent_name}</i>\n"
        text += f"  🇷🇺 {s.get('name_ru') or '—'}\n"
        text += f"  🇺🇦 {s.get('name_uk') or '—'}\n"
        text += f"  🇬🇧 {s.get('name_en') or '—'}\n\n"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]]
    await _edit_or_send(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def admin_sort_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    subcats = db.get_all_subcategories()
    categories_ru = db.get_categories('ru', include_inactive=True)

    if not subcats:
        await _edit_or_send(
            query,
            "📭 Подкатегорий нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]])
        )
        return

    keyboard = []
    current_parent = None
    for subcat in subcats:
        parent_id = subcat.get('parent_cat_id')
        if parent_id != current_parent:
            current_parent = parent_id
            parent_name = categories_ru.get(parent_id, parent_id)
            keyboard.append([InlineKeyboardButton(f"— {parent_name} —", callback_data='noop')])

        name = subcat.get('name_ru') or subcat.get('subcat_id')
        subcat_id = subcat.get('subcat_id')
        keyboard.append([
            InlineKeyboardButton("⬆️", callback_data=f'admin_move_subcat_up_{subcat_id}'),
            InlineKeyboardButton(f"{name}", callback_data='noop'),
            InlineKeyboardButton("⬇️", callback_data=f'admin_move_subcat_down_{subcat_id}')
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')])
    await _edit_or_send(
        query,
        "↕️ <b>Сортировка подкатегорий</b>\n\nИспользуйте кнопки ⬆️ и ⬇️ для изменения порядка.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_move_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str, direction: str):
    query = update.callback_query
    ok = db.move_subcategory(subcat_id, direction)
    if not ok:
        await query.answer("Нельзя переместить подкатегорию", show_alert=False)
    await admin_sort_subcategories(update, context)


async def admin_add_subcategory_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    context.user_data.clear()
    context.user_data['add_subcategory_step'] = 'id'
    db.set_pending_action(user.id, 'admin_add_subcategory_id')

    await _edit_or_send(
        query,
        "➕ <b>Добавление подкатегории</b>\n\n"
        "Введите <b>ID подкатегории</b> (a-z, 0-9, _ без пробелов):\n"
        "Пример: <code>grailed_accounts</code>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='admin_subcategories_menu')]]),
        parse_mode='HTML'
    )


async def handle_admin_add_subcategory_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    """Add subcategory flow: id -> parent -> ru -> uk -> en."""
    user = update.effective_user
    value = (text or "").strip()
    step = context.user_data.get('add_subcategory_step', 'id')

    if step == 'id':
        import re
        if not re.match(r'^[a-z0-9_]+$', value):
            await update.message.reply_text("❌ ID может содержать только a-z, 0-9 и _. Попробуйте ещё раз:")
            return

        existing = {s.get('subcat_id') for s in db.get_all_subcategories()}
        if value in existing:
            await update.message.reply_text(f"❌ Подкатегория с ID <b>{value}</b> уже существует. Введите другой ID:", parse_mode='HTML')
            return

        context.user_data['new_subcategory_id'] = value
        context.user_data['add_subcategory_step'] = 'parent'
        db.set_pending_action(user.id, 'admin_add_subcategory_parent')

        cats = db.get_categories('ru', include_inactive=True)
        await update.message.reply_text(
            "Введите <b>ID родительской категории</b>.\n"
            f"Доступные: {', '.join(cats.keys())}",
            parse_mode='HTML'
        )
        return

    if step == 'parent':
        cats = db.get_categories('ru', include_inactive=True)
        if value not in cats:
            await update.message.reply_text(f"❌ Неверная категория. Доступные: {', '.join(cats.keys())}")
            return

        context.user_data['new_subcategory_parent'] = value
        context.user_data['add_subcategory_step'] = 'name_ru'
        db.set_pending_action(user.id, 'admin_add_subcategory_name_ru')
        await update.message.reply_text("Введите название на русском:")
        return

    if step == 'name_ru':
        context.user_data['new_subcategory_name_ru'] = value
        context.user_data['add_subcategory_step'] = 'name_uk'
        db.set_pending_action(user.id, 'admin_add_subcategory_name_uk')
        await update.message.reply_text("Введите название на украинском (или /skip):")
        return

    if step == 'name_uk':
        context.user_data['new_subcategory_name_uk'] = None if value == '/skip' else value
        context.user_data['add_subcategory_step'] = 'name_en'
        db.set_pending_action(user.id, 'admin_add_subcategory_name_en')
        await update.message.reply_text("Введите название на английском (или /skip):")
        return

    if step == 'name_en':
        context.user_data['new_subcategory_name_en'] = None if value == '/skip' else value

        subcat_id = context.user_data['new_subcategory_id']
        parent = context.user_data['new_subcategory_parent']
        name_ru = context.user_data['new_subcategory_name_ru']
        name_uk = context.user_data.get('new_subcategory_name_uk')
        name_en = context.user_data.get('new_subcategory_name_en')

        if db.add_subcategory(subcat_id, parent, name_ru, name_uk, name_en, is_active=0):
            await update.message.reply_text(
                "✅ Подкатегория создана в черновиках!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 К списку подкатегорий", callback_data='admin_list_subcategories')],
                    [InlineKeyboardButton("➕ Добавить ещё", callback_data='admin_add_subcategory')],
                    [InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении подкатегории")

        db.clear_pending_action(user.id)
        context.user_data.clear()
        return


async def admin_edit_subcategory_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    subcats = db.get_all_subcategories()
    if not subcats:
        await _edit_or_send(
            query,
            "📭 Подкатегорий нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]]),
        )
        return

    keyboard = []
    for s in subcats:
        label = s.get('name_ru') or s.get('subcat_id')
        status = "✅" if s.get('is_active', 1) else "📝"
        keyboard.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"admin_edit_subcat_{s.get('subcat_id')}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')])

    await _edit_or_send(query, "Выберите подкатегорию для редактирования:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_edit_subcategory_start(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str):
    query = update.callback_query

    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await _edit_or_send(query, "❌ Подкатегория не найдена")
        return

    db.clear_pending_action(query.from_user.id)
    context.user_data.clear()
    parent_name = db.get_categories('ru', include_inactive=True).get(subcat.get('parent_cat_id'), subcat.get('parent_cat_id'))
    toggle_label = "📤 Опубликовать" if not subcat.get('is_active', 1) else "📝 В черновик"
    await _edit_or_send(
        query,
        f"✏️ <b>Редактирование подкатегории {html.escape(subcat_id)}</b>\n\n"
        f"Родитель: <code>{html.escape(subcat.get('parent_cat_id') or '-')}</code> ({html.escape(parent_name or '-')})\n"
        f"🇷🇺 {html.escape(subcat.get('name_ru') or '—')}\n"
        f"🇺🇦 {html.escape(subcat.get('name_uk') or '—')}\n"
        f"🇬🇧 {html.escape(subcat.get('name_en') or '—')}\n"
        f"🖼 Фото: {'есть' if subcat.get('photo_url') else 'нет'}\n"
        f"Статус: {_draft_status_label(subcat.get('is_active', 1))}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Родительская категория", callback_data=f"admin_subcat_field_{subcat_id}_parent")],
            [InlineKeyboardButton("🇷🇺 RU", callback_data=f"admin_subcat_field_{subcat_id}_name_ru")],
            [InlineKeyboardButton("🇺🇦 UK", callback_data=f"admin_subcat_field_{subcat_id}_name_uk")],
            [InlineKeyboardButton("🇬🇧 EN", callback_data=f"admin_subcat_field_{subcat_id}_name_en")],
            [InlineKeyboardButton("🖼 Фото", callback_data=f"admin_subcat_field_{subcat_id}_photo")],
            [InlineKeyboardButton("🗑 Удалить фото", callback_data=f"admin_subcat_photo_remove_{subcat_id}")],
            [InlineKeyboardButton(toggle_label, callback_data=f"admin_subcat_toggle_{subcat_id}")],
            [InlineKeyboardButton("📄 Дублировать", callback_data=f"admin_subcat_duplicate_{subcat_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_edit_subcategory')],
        ]),
        parse_mode='HTML'
    )


async def handle_admin_edit_subcategory_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    value = (text or "").strip()
    payload = action.replace('admin_edit_subcategory_', '', 1)
    field = None
    subcat_id = None
    for candidate in ('parent', 'name_ru', 'name_uk', 'name_en', 'photo'):
        suffix = f"_{candidate}"
        if payload.endswith(suffix):
            subcat_id = payload[:-len(suffix)]
            field = candidate
            break
    if not subcat_id or not field:
        db.clear_pending_action(user.id)
        return
    current = db.get_subcategory(subcat_id) or {}
    if not current:
        db.clear_pending_action(user.id)
        await update.message.reply_text("❌ Подкатегория не найдена")
        return

    if value == '/skip':
        db.clear_pending_action(user.id)
        await update.message.reply_text(
            "Изменение отменено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_subcat_{subcat_id}')]])
        )
        return

    updates = {'is_active': 0}
    if field == 'parent':
        cats = db.get_categories('ru', include_inactive=True)
        if value not in cats:
            await update.message.reply_text(
                f"❌ Неверная категория.\n\nДоступные категории:\n{_format_choice_list(cats)}",
                parse_mode='HTML'
            )
            return
        updates['parent_cat_id'] = value
    elif field == 'name_ru':
        updates['name_ru'] = value
    elif field == 'name_uk':
        updates['name_uk'] = value
    elif field == 'name_en':
        updates['name_en'] = value
    elif field == 'photo':
        await update.message.reply_text("❌ Отправьте фото подкатегории или /skip.")
        return
    else:
        db.clear_pending_action(user.id)
        return

    ok = db.update_subcategory(subcat_id, **updates)
    db.clear_pending_action(user.id)
    if ok:
        await update.message.reply_text(
            "✅ Подкатегория обновлена и сохранена в черновик!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_subcat_{subcat_id}')]])
        )
    else:
        await update.message.reply_text("❌ Ошибка при обновлении подкатегории")


async def admin_edit_subcategory_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str, field: str):
    query = update.callback_query
    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await _edit_or_send(query, "❌ Подкатегория не найдена")
        return

    db.set_pending_action(query.from_user.id, f"admin_edit_subcategory_{subcat_id}_{field}")

    if field == 'parent':
        cats = db.get_categories('ru', include_inactive=True)
        text = (
            f"Введите новый <b>ID родительской категории</b> или /skip.\n\n"
            f"Текущая: <code>{html.escape(subcat.get('parent_cat_id') or '-')}</code>\n"
            f"Доступные категории:\n{_format_choice_list(cats)}"
        )
    elif field == 'name_ru':
        text = f"Введите новое название на русском или /skip.\n\nТекущее: {html.escape(subcat.get('name_ru') or '—')}"
    elif field == 'name_uk':
        text = f"Введите новое название на украинском или /skip.\n\nТекущее: {html.escape(subcat.get('name_uk') or '—')}"
    elif field == 'name_en':
        text = f"Введите новое название на английском или /skip.\n\nТекущее: {html.escape(subcat.get('name_en') or '—')}"
    elif field == 'photo':
        text = (
            f"Отправьте фото для подкатегории или /skip.\n\n"
            f"Сейчас фото: {'есть' if subcat.get('photo_url') else 'нет'}"
        )
    else:
        await query.answer("Неизвестное поле", show_alert=True)
        return

    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_subcat_{subcat_id}')]]),
        parse_mode='HTML'
    )


async def admin_toggle_subcategory_status(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str):
    query = update.callback_query
    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await query.answer("Подкатегория не найдена", show_alert=True)
        return

    ok = db.update_subcategory(subcat_id, is_active=0 if subcat.get('is_active', 1) else 1)
    if ok:
        await query.answer("Статус подкатегории обновлён", show_alert=False)
        await admin_edit_subcategory_start(update, context, subcat_id)
    else:
        await query.answer("Не удалось изменить статус", show_alert=True)


async def admin_duplicate_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str):
    query = update.callback_query
    new_subcat_id = db.duplicate_subcategory_to_draft(subcat_id)
    if not new_subcat_id:
        await query.answer("Не удалось создать дубликат", show_alert=True)
        return

    await query.answer("Создан дубликат подкатегории в черновиках", show_alert=False)
    await admin_edit_subcategory_start(update, context, new_subcat_id)


async def admin_remove_subcategory_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str):
    query = update.callback_query
    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await _edit_or_send(query, "❌ Подкатегория не найдена")
        return

    ok = db.update_subcategory(subcat_id, photo_url='', is_active=0)
    await _edit_or_send(
        query,
        "✅ Фото подкатегории удалено и сохранено в черновик!" if ok else "❌ Не удалось удалить фото подкатегории.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_subcat_{subcat_id}')]])
    )


async def admin_delete_subcategory_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    subcats = db.get_all_subcategories()
    keyboard = []
    for s in subcats:
        label = s.get('name_ru') or s.get('subcat_id')
        keyboard.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"admin_delete_subcat_{s.get('subcat_id')}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')])

    await _edit_or_send(query, "Выберите подкатегорию для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_delete_subcategory_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, subcat_id: str):
    query = update.callback_query

    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await _edit_or_send(query, "❌ Подкатегория не найдена")
        return

    success, message = db.delete_subcategory(subcat_id)
    if success:
        await _edit_or_send(
            query,
            f"✅ Подкатегория <b>{html.escape(subcat_id)}</b> удалена!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]]),
            parse_mode='HTML'
        )
    else:
        await _edit_or_send(
            query,
            f"❌ {html.escape(message)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_subcategories_menu')]]),
            parse_mode='HTML'
        )


async def admin_list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список категорий из БД на всех языках"""
    query = update.callback_query
    
    categories = db.get_all_categories()
    
    text = "📋 <b>Список категорий:</b>\n\n"
    
    for category in categories:
        cat_id = category.get('cat_id')
        status = "✅" if category.get('is_active', 1) else "📝"
        text += f"{status} <b>{cat_id}</b>\n"
        text += f"  🇷🇺 {category.get('name_ru', '—')}\n"
        text += f"  🇺🇦 {category.get('name_uk', '—')}\n"
        text += f"  🇬🇧 {category.get('name_en', '—')}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]]
    await _edit_or_send(query, 
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_sort_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    categories = db.get_all_categories()

    if not categories:
        await _edit_or_send(
            query,
            "📭 Категорий нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]])
        )
        return

    keyboard = []
    for category in categories:
        cat_id = category.get('cat_id')
        name = category.get('name_ru') or cat_id
        keyboard.append([
            InlineKeyboardButton("⬆️", callback_data=f'admin_move_cat_up_{cat_id}'),
            InlineKeyboardButton(name, callback_data='noop'),
            InlineKeyboardButton("⬇️", callback_data=f'admin_move_cat_down_{cat_id}')
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')])
    await _edit_or_send(
        query,
        "↕️ <b>Сортировка категорий</b>\n\nИспользуйте кнопки ⬆️ и ⬇️ для изменения порядка.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_move_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str, direction: str):
    query = update.callback_query
    ok = db.move_category(cat_id, direction)
    if not ok:
        await query.answer("Нельзя переместить категорию", show_alert=False)
    await admin_sort_categories(update, context)


async def admin_add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления категории"""
    query = update.callback_query
    user = query.from_user
    
    # Сохраняем шаги для ввода переводов
    context.user_data['add_category_step'] = 'id'
    db.set_pending_action(user.id, 'admin_add_category_id')
    
    await _edit_or_send(query, 
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
        
        existing = db.get_categories(include_inactive=True)
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
        
        if db.add_category(cat_id, name_ru, name_uk, name_en, is_active=0):
            await update.message.reply_text(
                f"✅ Категория создана в черновиках!\n\n"
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
    
    categories = db.get_all_categories()
    keyboard = []
    for category in categories:
        cat_id = category.get('cat_id')
        cat_name = category.get('name_ru') or cat_id
        status = "✅" if category.get('is_active', 1) else "📝"
        keyboard.append([InlineKeyboardButton(f"{status} {cat_name}", callback_data=f'admin_edit_cat_{cat_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')])
    
    await _edit_or_send(query, 
        "Выберите категорию для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_edit_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    """Экран редактирования категории."""
    query = update.callback_query
    category = db.get_category(cat_id)
    if not category:
        await _edit_or_send(query, "❌ Категория не найдена")
        return

    categories_uk = db.get_categories('uk')
    categories_en = db.get_categories('en')
    photo_state = "есть" if category.get('photo_url') else "нет"
    status = _draft_status_label(category.get('is_active', 1))
    toggle_label = "📤 Опубликовать" if not category.get('is_active', 1) else "📝 В черновик"

    await _edit_or_send(
        query,
        f"✏️ <b>Редактирование категории {cat_id}</b>\n\n"
        f"🇷🇺 {category.get('name_ru') or '—'}\n"
        f"🇺🇦 {categories_uk.get(cat_id) or category.get('name_uk') or '—'}\n"
        f"🇬🇧 {categories_en.get(cat_id) or category.get('name_en') or '—'}\n"
        f"Статус: {status}\n"
        f"🖼 Фото: {photo_state}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Изменить названия", callback_data=f'admin_edit_cat_text_{cat_id}')],
            [InlineKeyboardButton("🖼 Обновить фото", callback_data=f'admin_edit_cat_photo_{cat_id}')],
            [InlineKeyboardButton("🗑 Удалить фото", callback_data=f'admin_edit_cat_photo_remove_{cat_id}')],
            [InlineKeyboardButton(toggle_label, callback_data=f'admin_category_toggle_{cat_id}')],
            [InlineKeyboardButton("📄 Дублировать", callback_data=f'admin_category_duplicate_{cat_id}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_edit_category')],
        ]),
        parse_mode='HTML'
    )


async def admin_edit_category_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    query = update.callback_query
    user = query.from_user
    category = db.get_category(cat_id)
    if not category:
        await _edit_or_send(query, "❌ Категория не найдена")
        return

    context.user_data['edit_cat_id'] = cat_id
    context.user_data['edit_cat_ru'] = category.get('name_ru') or ''
    context.user_data['edit_cat_uk'] = category.get('name_uk') or ''
    context.user_data['edit_cat_en'] = category.get('name_en') or ''

    db.set_pending_action(user.id, f'admin_edit_category_ru_{cat_id}')
    await _edit_or_send(
        query,
        f"✏️ <b>Редактирование названий категории {cat_id}</b>\n\n"
        f"Текущее русское название: {category.get('name_ru') or '—'}\n\n"
        f"Введите новое название на русском (или /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f'admin_edit_cat_{cat_id}')]]),
        parse_mode='HTML'
    )


async def admin_edit_category_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    query = update.callback_query
    user = query.from_user
    if not db.get_category(cat_id):
        await _edit_or_send(query, "❌ Категория не найдена")
        return

    db.set_pending_action(user.id, f'admin_edit_category_photo_{cat_id}')
    await _edit_or_send(
        query,
        "🖼 Отправьте фото для категории.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f'admin_edit_cat_{cat_id}')]])
    )


async def admin_remove_category_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    query = update.callback_query
    category = db.get_category(cat_id)
    if not category:
        await _edit_or_send(query, "❌ Категория не найдена")
        return

    if db.update_category(cat_id, photo_url=''):
        await _edit_or_send(
            query,
            "✅ Фото категории удалено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_cat_{cat_id}')]])
        )
    else:
        await _edit_or_send(
            query,
            "❌ Не удалось удалить фото категории.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_cat_{cat_id}')]])
        )


async def admin_toggle_category_status(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    query = update.callback_query
    category = db.get_category(cat_id)
    if not category:
        await query.answer("Категория не найдена", show_alert=True)
        return

    ok = db.update_category(cat_id, is_active=0 if category.get('is_active', 1) else 1)
    if ok:
        await query.answer("Статус категории обновлён", show_alert=False)
        await admin_edit_category_start(update, context, cat_id)
    else:
        await query.answer("Не удалось изменить статус", show_alert=True)


async def admin_duplicate_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    query = update.callback_query
    new_cat_id = db.duplicate_category_to_draft(cat_id)
    if not new_cat_id:
        await query.answer("Не удалось создать дубликат", show_alert=True)
        return

    await query.answer("Создан дубликат категории в черновиках", show_alert=False)
    await admin_edit_category_start(update, context, new_cat_id)


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
    
    categories = db.get_categories('ru', include_inactive=True)
    keyboard = []
    for cat_id, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(f"❌ {cat_name}", callback_data=f'admin_delete_cat_{cat_id}')])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')])
    
    await _edit_or_send(query, 
        "Выберите категорию для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_delete_category_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str):
    """Подтверждение удаления категории"""
    query = update.callback_query
    
    categories = db.get_categories('ru', include_inactive=True)
    if cat_id not in categories:
        await _edit_or_send(query, "❌ Категория не найдена")
        return
    
    success, message = db.delete_category(cat_id)
    if success:
        await _edit_or_send(query, 
            f"✅ Категория <b>{cat_id}</b> успешно удалена!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_categories_menu')]]),
            parse_mode='HTML'
        )
    else:
        await _edit_or_send(query, 
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
    if action not in {'admin_add_category_photo'} and not action.startswith('admin_edit_category_photo_') and not photo_path:
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
        product_id, _ = _parse_product_edit_action(action)
        if product_id is None:
            await update.message.reply_text("❌ Некорректный ID товара")
            db.clear_pending_action(user.id)
            return

        prod = db.get_product(product_id)
        if not prod:
            await update.message.reply_text("❌ Товар не найден")
            db.clear_pending_action(user.id)
            context.user_data.clear()
            return

        if db.update_product(product_id, input_lang='auto', photo_url=photo_path, is_active=0):
            await update.message.reply_text(
                "✅ Фото товара обновлено и сохранено в черновик!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад к товару", callback_data=f'admin_edit_{product_id}')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении фото товара")

        db.clear_pending_action(user.id)
        return

    if action == 'admin_add_category_photo':
        context.user_data['new_category_photo_url'] = photo.file_id
        cat_id = context.user_data['new_category_id']
        name_ru = context.user_data['new_category_name_ru']
        name_uk = context.user_data.get('new_category_name_uk')
        name_en = context.user_data.get('new_category_name_en')

        if db.add_category(cat_id, name_ru, name_uk, name_en, photo_url=photo.file_id, is_active=0):
            await update.message.reply_text(
                "✅ Категория создана в черновиках!",
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

    if action.startswith('admin_edit_subcategory_') and action.endswith('_photo'):
        subcat_id = action.replace('admin_edit_subcategory_', '', 1).rsplit('_photo', 1)[0]
        subcat = db.get_subcategory(subcat_id)
        if not subcat:
            await update.message.reply_text("❌ Подкатегория не найдена")
            db.clear_pending_action(user.id)
            return

        if db.update_subcategory(subcat_id, photo_url=photo_path, is_active=0):
            await update.message.reply_text(
                "✅ Фото подкатегории обновлено и сохранено в черновик!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_subcat_{subcat_id}')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении фото подкатегории")

        db.clear_pending_action(user.id)
        context.user_data.clear()
        return

    if action.startswith('admin_edit_category_photo_'):
        cat_id = action.replace('admin_edit_category_photo_', '', 1)
        category = db.get_category(cat_id)
        if not category:
            await update.message.reply_text("❌ Категория не найдена")
            db.clear_pending_action(user.id)
            return

        if db.update_category(cat_id, photo_url=photo.file_id, is_active=0):
            await update.message.reply_text(
                "✅ Фото категории обновлено и сохранено в черновик!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_cat_{cat_id}')],
                ])
            )
        else:
            await update.message.reply_text("❌ Ошибка при обновлении фото категории")

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
        existing = db.get_categories(include_inactive=True)
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
        context.user_data['add_category_step'] = 'photo'
        db.set_pending_action(user.id, 'admin_add_category_photo')
        await update.message.reply_text("Отправьте фото для категории или /skip:")
        return

    if step == 'photo':
        context.user_data['new_category_photo_url'] = None if text == '/skip' else text
        cat_id = context.user_data['new_category_id']
        name_ru = context.user_data['new_category_name_ru']
        name_uk = context.user_data.get('new_category_name_uk')
        name_en = context.user_data.get('new_category_name_en')
        photo_url = context.user_data.get('new_category_photo_url')

        if db.add_category(cat_id, name_ru, name_uk, name_en, photo_url=photo_url, is_active=0):
            await update.message.reply_text(
                "✅ Категория создана в черновиках!",
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

    if action.startswith('admin_edit_category_photo_'):
        cat_id = action.replace('admin_edit_category_photo_', '', 1)
        if text == '/skip':
            db.clear_pending_action(user.id)
            await update.message.reply_text(
                "Изменение фото отменено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_edit_cat_{cat_id}')],
                ])
            )
        else:
            await update.message.reply_text("❌ Отправьте фото или нажмите кнопку отмены.")
        return

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
        if db.update_category(cat_id, name_ru, name_uk, name_en, is_active=0):
            await update.message.reply_text(
                "✅ Категория обновлена и сохранена в черновик!",
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
    """Точечное редактирование полей товара."""
    user = update.effective_user
    text = text.strip()
    product_id, field = _parse_product_edit_action(action)
    if product_id is None or not field:
        db.clear_pending_action(user.id)
        return

    prod = db.get_product(product_id)
    if not prod:
        db.clear_pending_action(user.id)
        await update.message.reply_text("❌ Товар не найден")
        return

    current = _get_product_edit_current(prod)

    async def _done(message: str):
        db.clear_pending_action(user.id)
        await update.message.reply_text(
            f"{message}\n\n{_build_product_edit_text(product_id, db.get_product(product_id))}",
            reply_markup=InlineKeyboardMarkup(_build_product_edit_keyboard(product_id)),
            parse_mode='HTML'
        )

    if field == 'name':
        if text == '/skip':
            await _done("Изменение названия отменено.")
            return

        if db.update_product(product_id, input_lang='auto', name=text, is_active=0):
            await _done("✅ Название обновлено и сохранено в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении названия товара")
        return

    if field == 'category':
        categories = db.get_categories('ru', include_inactive=True)
        if text == '/skip':
            await _done("Изменение категории отменено.")
            return

        new_category = text
        if new_category not in categories:
            await update.message.reply_text(
                f"❌ Неверная категория.\n\nДоступные категории:\n{_format_choice_list(categories)}",
                parse_mode='HTML'
            )
            return

        updates = {'category': new_category}
        subcats = db.get_subcategories(new_category, lang='ru')
        if current.get('subcategory') and current['subcategory'] not in subcats:
            updates['subcategory'] = None

        updates['is_active'] = 0
        if db.update_product(product_id, input_lang='auto', **updates):
            suffix = ""
            if 'subcategory' in updates:
                suffix = "\nПодкатегория очищена, потому что не относится к новой категории."
            await _done(f"✅ Категория обновлена и сохранена в черновик.{suffix}")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении категории товара")
        return

    if field == 'subcategory':
        category = current['category']
        subcats = db.get_subcategories(category, lang='ru') if category else {}

        if text == '/skip':
            await _done("Изменение подкатегории отменено.")
            return
        elif text in {'/none', 'none', 'null', '-'}:
            new_subcategory = None
        else:
            if not subcats:
                await update.message.reply_text("❌ Для текущей категории подкатегорий нет. Используйте /none или /skip.")
                return
            if subcats and text not in subcats:
                await update.message.reply_text(
                    f"❌ Неверная подкатегория.\n\nДоступные варианты:\n{_format_choice_list(subcats)}",
                    parse_mode='HTML'
                )
                return
            new_subcategory = text

        if db.update_product(product_id, input_lang='auto', subcategory=new_subcategory, is_active=0):
            await _done("✅ Подкатегория обновлена и сохранена в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении подкатегории товара")
        return

    if field == 'price':
        if text == '/skip':
            await _done("Изменение цены отменено.")
            return
        else:
            try:
                new_price = float(text.replace(',', '.'))
            except ValueError:
                await update.message.reply_text("❌ Введите корректную цену, например 45.99 или -1")
                return
        if db.update_product(product_id, input_lang='auto', price_usd=new_price, is_active=0):
            await _done("✅ Цена обновлена и сохранена в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении цены товара")
        return

    if field == 'desc':
        if text == '/skip':
            await _done("Изменение описания отменено.")
            return

        if db.update_product(product_id, input_lang='auto', description=text, is_active=0):
            await _done("✅ Описание обновлено и сохранено в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении описания товара")
        return

    if field == 'stock':
        if text == '/skip':
            await _done("Изменение запаса отменено.")
            return
        else:
            try:
                new_stock = int(text)
            except ValueError:
                await update.message.reply_text("❌ Запас должен быть целым числом")
                return
        if db.update_product(product_id, input_lang='auto', stock=new_stock, is_active=0):
            await _done("✅ Запас обновлён и сохранён в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении запаса товара")
        return

    if field == 'sort':
        if text == '/skip':
            await _done("Изменение sort order отменено.")
            return
        else:
            try:
                new_sort = int(text)
            except ValueError:
                await update.message.reply_text("❌ sort order должен быть целым числом")
                return
        if db.update_product(product_id, input_lang='auto', sort_order=new_sort, is_active=0):
            await _done("✅ Sort order обновлён и сохранён в черновик.")
        else:
            await update.message.reply_text("❌ Ошибка при обновлении sort order товара")
        return

    if field == 'photo_waiting' and text == '/skip':
        await _done("Изменение фото отменено.")
        return

    if field == 'photo_waiting':
        await update.message.reply_text("❌ Отправьте новое фото товара или /skip.")
        return

    db.clear_pending_action(user.id)


def _menu_target_options():
    return {
        'services': '🛒 Services',
        'balance': '💰 Balance',
        'profile': '👤 Profile',
        'referral': '🔗 Referral',
        'faq': '❓ FAQ',
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
    await _edit_or_send(query, 
        f"🏠 <b>Главная страница</b>\n\n"
        f"Фото: {photo_state}\n"
        f"RU preview: <code>{preview}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_home_edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    home = db.get_home_content()

    await _edit_or_send(query, 
        "📝 <b>Редактирование текстов главной страницы</b>\n\n"
        f"🇷🇺 RU: {'есть' if home.get('text_ru') else 'нет'}\n"
        f"🇺🇦 UK: {'есть' if home.get('text_uk') else 'нет'}\n"
        f"🇬🇧 EN: {'есть' if home.get('text_en') else 'нет'}\n\n"
        "Выберите язык, который хотите изменить:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Русский", callback_data='admin_home_edit_text_ru')],
            [InlineKeyboardButton("🇺🇦 Українська", callback_data='admin_home_edit_text_uk')],
            [InlineKeyboardButton("🇬🇧 English", callback_data='admin_home_edit_text_en')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_home_menu')],
        ]),
        parse_mode='HTML'
    )


async def admin_home_edit_text_lang_start(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    query = update.callback_query
    user = query.from_user
    if lang not in {'ru', 'uk', 'en'}:
        await query.answer("Неизвестный язык", show_alert=True)
        return

    home = db.get_home_content()
    current_text = home.get(f'text_{lang}') or ''
    lang_label = {'ru': 'русском', 'uk': 'украинском', 'en': 'английском'}[lang]

    db.set_pending_action(user.id, f'admin_home_text_{lang}')
    await _edit_or_send(
        query,
        "📝 <b>Редактирование текста главной страницы</b>\n\n"
        f"Язык: <b>{lang.upper()}</b>\n\n"
        f"Текущее значение:\n<code>{html.escape(current_text[:800] or '—')}</code>\n\n"
        f"Введите новый текст на {lang_label}.\n"
        "Можно использовать <code>{name}</code> для имени пользователя.\n"
        "Или отправьте /skip, чтобы оставить текущий.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_edit_text')]]),
        parse_mode='HTML'
    )


async def handle_admin_home_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    text = text.strip()
    lang = action.replace('admin_home_text_', '', 1)
    if lang not in {'ru', 'uk', 'en'}:
        db.clear_pending_action(user.id)
        return

    db.clear_pending_action(user.id)
    if text == '/skip':
        await update.message.reply_text(
            "Изменение текста отменено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_edit_text')]])
        )
        return

    ok = db.save_home_content({f'text_{lang}': text})
    if ok:
        await update.message.reply_text(
            f"✅ Текст главной страницы для {lang.upper()} обновлён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_home_edit_text')]])
        )
    else:
        await update.message.reply_text("❌ Не удалось сохранить текст главной страницы.")


async def admin_home_edit_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    db.set_pending_action(user.id, 'admin_home_photo')
    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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
        [InlineKeyboardButton("🆘 Support", callback_data='admin_menu_core_edit_support')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_editor')],
    ]
    await _edit_or_send(query, 
        "✏️ <b>Core кнопки</b>\n\n"
        "Для Balance можно использовать шаблон <code>{balance}</code>.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def admin_menu_core_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    query = update.callback_query
    core = db.get_main_menu_core()
    labels = core.get(key, {})
    photo_state = "есть" if labels.get('photo_file_id') else "нет"

    await _edit_or_send(query, 
        "✏️ <b>Редактирование core-кнопки</b>\n\n"
        f"Ключ: <code>{html.escape(key)}</code>\n"
        f"RU: {html.escape(labels.get('ru') or '-')}\n"
        f"UK: {html.escape(labels.get('uk') or '-')}\n"
        f"EN: {html.escape(labels.get('en') or '-')}\n"
        f"Фото: {photo_state}\n\n"
        "Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("RU", callback_data=f'admin_menu_core_field_{key}_ru')],
            [InlineKeyboardButton("UK", callback_data=f'admin_menu_core_field_{key}_uk')],
            [InlineKeyboardButton("EN", callback_data=f'admin_menu_core_field_{key}_en')],
            [InlineKeyboardButton("🖼 Обновить фото", callback_data=f'admin_menu_core_photo_{key}')],
            [InlineKeyboardButton("🗑 Удалить фото", callback_data=f'admin_menu_core_photo_remove_{key}')],
            [InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_core')],
        ]),
        parse_mode='HTML'
    )


async def admin_menu_core_edit_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, lang_code: str):
    query = update.callback_query
    labels = db.get_main_menu_core().get(key, {})
    context.user_data['menu_core_key'] = key
    db.set_pending_action(query.from_user.id, f'admin_menu_core_label_{lang_code}')

    await _edit_or_send(query, 
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


async def admin_menu_core_edit_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    query = update.callback_query
    context.user_data['menu_core_key'] = key
    db.set_pending_action(query.from_user.id, f'admin_menu_core_photo_{key}')
    await _edit_or_send(
        query,
        f"🖼 <b>Фото для core-кнопки</b>\n\n"
        f"Ключ: <code>{html.escape(key)}</code>\n"
        "Отправьте фото, которое будет показываться при открытии этого раздела.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_core_edit_{key}')]
        ]),
        parse_mode='HTML'
    )


async def admin_menu_core_remove_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    query = update.callback_query
    current = db.get_main_menu_core().get(key, {})
    current['photo_file_id'] = None
    ok = db.save_main_menu_core({key: current})
    await _edit_or_send(
        query,
        "✅ Фото удалено." if ok else "❌ Не удалось удалить фото.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_core_edit_{key}')]
        ])
    )


async def handle_admin_menu_core_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pending = db.get_pending_action(user.id)
    if not pending or not pending[0].startswith('admin_menu_core_photo_'):
        return

    key = pending[0].replace('admin_menu_core_photo_', '', 1)
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото.")
        return

    photo_file_id = update.message.photo[-1].file_id
    current = db.get_main_menu_core().get(key, {})
    current['photo_file_id'] = photo_file_id
    ok = db.save_main_menu_core({key: current})

    db.clear_pending_action(user.id)
    context.user_data.pop('menu_core_key', None)

    await update.message.reply_text(
        "✅ Фото сохранено." if ok else "❌ Не удалось сохранить фото.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f'admin_menu_core_edit_{key}')]
        ])
    )


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
    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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
            await _edit_or_send(query, 
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
    await _edit_or_send(query, 
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

    await _edit_or_send(query, 
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
    await _edit_or_send(query, 
        "✅ Кнопка удалена." if ok else "❌ Не удалось удалить кнопку.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='admin_menu_custom')]])
    )
