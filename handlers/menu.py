from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from handlers.start import start_command
from handlers.services import (
    handle_services,
    handle_category,
    handle_subcategory,
    handle_product,
    handle_buy,
    handle_buy_quantity,
    handle_buy_confirm,
)
from handlers.payments import (
    handle_balance, handle_deposit, handle_withdraw,
    handle_currency_selection, handle_amount_selection,
    handle_custom_amount, handle_custom_deposit,
    handle_transfer_start, handle_transfer_text_input
)
from handlers.profile import handle_profile, handle_referral, handle_referral_details, handle_purchase_history
from handlers.faq import handle_faq, handle_faq_item
from handlers.admin import (
    handle_admin,
    handle_admin_add_product_input,
    handle_admin_photo_input,
    handle_admin_home_photo_input
)
import logging

logger = logging.getLogger(__name__)

# Anti-flood: минимальный интервал между действиями одного пользователя (в секундах)
ANTI_FLOOD_INTERVAL = 0.6
last_action_time = {}


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-запросов (кнопок)"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data
    
    # ОТЛАДКА
    logger.info(f"🔵 CALLBACK RECEIVED: {data} from user {user.id}")

    # Anti-flood защита
    now = datetime.now().timestamp()
    if user.id in last_action_time:
        if now - last_action_time[user.id] < ANTI_FLOOD_INTERVAL:
            return
    last_action_time[user.id] = now

    # Обновляем время последней активности
    db.update_activity(user.id)

    # Отмена текущего ввода
    if data == 'cancel_input':
        db.clear_pending_action(user.id)
        for k in list(context.user_data.keys()):
            if k.startswith('add_prod_') or k.startswith('edit_prod_'):
                del context.user_data[k]
        await query.message.reply_text("Ввод отменён.", reply_markup=None)
        await start_command(update, context)
        return

    # Основная навигация
    if data == 'noop':
        return
    if data in ('menu', 'back'):
        await start_command(update, context)

    # Услуги / категории / товары
    elif data == 'services':
        await handle_services(update, context)
    elif data.startswith('cat_'):
        await handle_category(update, context, data[4:])
    elif data.startswith('subcat|'):
        parts = data.split('|', 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            await query.edit_message_text("Некорректная подкатегория")
        else:
            await handle_subcategory(update, context, parts[1], parts[2])
    elif data.startswith('prod_'):
        try:
            product_id = int(data[5:])
            await handle_product(update, context, product_id)
        except ValueError:
            await query.edit_message_text("Некорректный ID товара")
    elif data.startswith('buy_'):
        try:
            product_id = int(data[4:])
            await handle_buy(update, context, product_id)
        except ValueError:
            await query.edit_message_text("Некорректный ID товара")
    elif data.startswith('buyqty_'):
        try:
            _, product_id, quantity = data.split('_', 2)
            await handle_buy_quantity(update, context, int(product_id), int(quantity))
        except ValueError:
            await query.edit_message_text("Некорректное количество")
    elif data.startswith('buyconfirm_'):
        try:
            _, product_id, quantity = data.split('_', 2)
            await handle_buy_confirm(update, context, int(product_id), int(quantity))
        except ValueError:
            await query.edit_message_text("Некорректное подтверждение покупки")

    # Баланс и платежи
    elif data == 'balance':
        await handle_balance(update, context)
    elif data == 'deposit':
        await handle_deposit(update, context)
    elif data == 'withdraw':
        await handle_withdraw(update, context)
    elif data == 'transfer':
        await handle_transfer_start(update, context)
    elif data.startswith('curr_'):
        currency = data[5:]
        await handle_currency_selection(update, context, currency)
    elif data.startswith('amount_'):
        parts = data.split('_')
        if len(parts) == 3:
            currency, amount_str = parts[1], parts[2]
            if amount_str == 'custom':
                await handle_custom_amount(update, context, currency)
            else:
                try:
                    amount = int(amount_str)
                    await handle_amount_selection(update, context, currency, amount)
                except ValueError:
                    await query.edit_message_text("Ошибка в сумме")

    # Промокод
    elif data == 'promo_code':
        from handlers.promo import handle_promo
        await handle_promo(update, context)

    # Профиль и рефералка
    elif data == 'profile':
        await handle_profile(update, context)
    elif data == 'referral':
        await handle_referral(update, context)
    elif data == 'referral_details':
        await handle_referral_details(update, context)
    elif data == 'purchase_history':
        await handle_purchase_history(update, context)
    elif data == 'faq':
        await handle_faq(update, context)
    elif data.startswith('faq_'):
        await handle_faq_item(update, context, data.replace('faq_', '', 1))

    # Админ-панель (все что связано с админкой, включая рассылки)
    elif (data.startswith('admin') or 
          data.startswith('promo_') or 
          data.startswith('broadcast_')):
        logger.info(f"📢 Передаем в админ-панель: {data}")
        await handle_admin(update, context, data)
    
    # Обработка выбора типа бонуса для промокодов
    elif data == 'bonus_discount' or data == 'bonus_balance':
        logger.info(f"📢 Выбор типа бонуса: {data}")
        
        # Устанавливаем pending action для ввода значения
        if data == 'bonus_discount':
            db.set_pending_action(user.id, 'admin_create_promo_discount_value')
            context.user_data['promo_step'] = 'discount_value'
            context.user_data['bonus_type'] = 'discount'
            await query.edit_message_text(
                "💸 <b>Скидка</b>\n\nВведите процент скидки (от 1 до 100):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
                ]]),
                parse_mode='HTML'
            )
        elif data == 'bonus_balance':
            db.set_pending_action(user.id, 'admin_create_promo_balance_value')
            context.user_data['promo_step'] = 'balance_value'
            context.user_data['bonus_type'] = 'balance'
            await query.edit_message_text(
                "💰 <b>Бонус на баланс</b>\n\nВведите сумму бонуса (в $):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
                ]]),
                parse_mode='HTML'
            )
        
        await query.answer()


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений и фото"""
    user = update.effective_user
    message = update.message

    is_photo = bool(message.photo)
    logger.info(f"Сообщение от {user.id} | тип: {'фото' if is_photo else 'текст'}")

    # Обработка фото отдельно
    if is_photo:
        pending = db.get_pending_action(user.id)
        if not pending:
            await message.reply_text("Сейчас я не жду фотографию.")
            return

        action, _ = pending
        if (
            action == 'admin_add_product_photo_waiting'
            or action == 'admin_add_category_photo'
            or action == 'admin_home_photo'
            or action.startswith('admin_menu_core_photo_')
            or action == 'broadcast_photo'
            or action.startswith('admin_edit_category_photo_')
            or action.startswith('admin_edit_subcategory_') and action.endswith('_photo')
            or (action.startswith('admin_edit_') and action.endswith('_photo_waiting'))
        ):
            if action == 'admin_home_photo':
                await handle_admin_home_photo_input(update, context)
            elif action.startswith('admin_menu_core_photo_'):
                from handlers.admin import handle_admin_menu_core_photo_input
                await handle_admin_menu_core_photo_input(update, context)
            elif action == 'broadcast_photo':
                from handlers.admin_broadcast import handle_broadcast_photo_input
                await handle_broadcast_photo_input(update, context)
            else:
                await handle_admin_photo_input(update, context)
        else:
            await message.reply_text(f"Ожидается действие: {action}\nФото сейчас не нужно.")
        return

    # Дальше только текст
    text = message.text.strip()
    if not text:
        return

    pending = db.get_pending_action(user.id)
    if not pending:
        logger.debug("Нет pending action — игнорируем сообщение")
        return

    action, _ = pending
    logger.info(f"Обрабатываем pending action: {action} | текст: {text[:60]!r}")

    # Рассылка
    if action == 'broadcast_text':
        from handlers.admin_broadcast import broadcast_preview
        await broadcast_preview(update, context, text)
        return

    if action == 'broadcast_draft_title':
        from handlers.admin_broadcast import handle_broadcast_draft_title
        await handle_broadcast_draft_title(update, context, text)
        return

    # Депозит — кастомная сумма
    if action.startswith('deposit_custom_'):
        await handle_custom_deposit(update, context, text)
        return

    if action in {'transfer_recipient', 'transfer_amount'}:
        await handle_transfer_text_input(update, context, action, text)
        return

    # Ввод промокода - ИСПРАВЛЕНО!
    if action == 'enter_promo':
        from config import ADMIN_IDS
        code = text.strip().upper()
        
        # Проверяем промокод
        valid, promo = db.validate_advanced_promo(code, user.id)
        
        if not valid:
            await message.reply_text(f"❌ {promo}")
            db.clear_pending_action(user.id)
            return
        
        # Записываем ввод промокода
        db.record_promo_entry(promo['id'], user.id)
        
        # Начисляем бонус в зависимости от типа
        if promo['bonus_type'] == 'balance':
            # Прямое начисление на баланс
            amount = float(promo['bonus_value'])
            db.add_balance(user.id, amount)
            
            # Создаем транзакцию
            db.add_transaction(
                user_id=user.id,
                amount=amount,
                type_='referral',
                status='completed',
                metadata={'promo_id': promo['id'], 'promo_code': code}
            )
            
            # Получаем ID последней транзакции
            trans_result = db.execute(
                "SELECT id FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user.id,),
                fetch=True
            )
            
            if trans_result:
                if db.use_postgres:
                    trans_id = trans_result[0]['id']
                else:
                    trans_id = trans_result[0][0]
                
                # Отмечаем промокод как использованный
                db.use_promo_entry(promo['id'], user.id, trans_id)
            
            await message.reply_text(
                f"✅ Промокод активирован!\n"
                f"💰 На баланс начислено: ${amount:.2f}\n"
                f"💵 Текущий баланс: ${db.get_balance(user.id):.2f}"
            )
            
            # Уведомление админам
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🎫 <b>АКТИВАЦИЯ ПРОМОКОДА</b>\n\n"
                        f"👤 Пользователь: <code>{user.id}</code> (@{user.username})\n"
                        f"🔑 Промокод: <code>{code}</code>\n"
                        f"💵 Начислено: ${amount:.2f}",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        elif promo['bonus_type'] in ['discount', 'percent']:
            # Скидка на следующую покупку
            context.user_data['active_promo'] = {
                'id': promo['id'],
                'code': code,
                'type': promo['bonus_type'],
                'value': promo['bonus_value']
            }
            await message.reply_text(
                f"✅ Промокод активирован!\n"
                f"💰 Скидка {promo['bonus_value']}% на следующую покупку"
            )
        
        db.clear_pending_action(user.id)
        return

    # Начисление баланса админом
    if action == 'admin_add_balance_user' or action == 'admin_add_balance_amount':
        from handlers.admin_balance import process_admin_add_balance
        await process_admin_add_balance(update, context, text)
        return

    # Создание промокода
    if action.startswith('admin_create_promo_'):
        logger.info(f"📢 Вызов process_admin_create_promo с action={action}")
        from handlers.admin_promo import process_admin_create_promo
        await process_admin_create_promo(update, context, text)
        return

    # Добавление нового администратора
    if action == 'admin_add_admin':
        try:
            new_id = int(text)
            await message.reply_text(f"Добавлен админ с ID {new_id} (заглушка)")
        except ValueError:
            await message.reply_text("Пожалуйста, введите числовой Telegram ID.")
        db.clear_pending_action(user.id)
        return

    # Добавление категории (мультиязычный мастер)
    if action in {'admin_home_text_ru', 'admin_home_text_uk', 'admin_home_text_en'}:
        from handlers.admin import handle_admin_home_text_input
        await handle_admin_home_text_input(update, context, action, text)
        return

    if action in {'admin_menu_core_label_ru', 'admin_menu_core_label_uk', 'admin_menu_core_label_en'}:
        from handlers.admin import handle_admin_menu_core_input
        await handle_admin_menu_core_input(update, context, action, text)
        return

    if action in {'admin_menu_custom_label_ru', 'admin_menu_custom_label_uk', 'admin_menu_custom_label_en', 'admin_menu_custom_url', 'admin_menu_custom_target_text'}:
        from handlers.admin import handle_admin_menu_custom_input
        await handle_admin_menu_custom_input(update, context, action, text)
        return

    if action.startswith('admin_add_category_'):
        from handlers.admin import handle_admin_add_category_input
        await handle_admin_add_category_input(update, context, action, text)
        return

    if action.startswith('admin_add_subcategory_'):
        from handlers.admin import handle_admin_add_subcategory_input
        await handle_admin_add_subcategory_input(update, context, action, text)
        return

    # Редактирование категории (ru/uk/en шаги)
    if action.startswith('admin_edit_category_'):
        from handlers.admin import handle_admin_edit_category_input
        await handle_admin_edit_category_input(update, context, action, text)
        return

    if action.startswith('admin_edit_subcategory_'):
        from handlers.admin import handle_admin_edit_subcategory_input
        await handle_admin_edit_subcategory_input(update, context, action, text)
        return

    # Добавление товара — шаги wizard
    add_product_actions = {
        'admin_add_product_name',
        'admin_add_product_category',
        'admin_add_product_subcategory',
        'admin_add_product_price',
        'admin_add_product_desc',
        'admin_add_product_photo_waiting',
        'admin_add_product_stock',
        'admin_add_product_sort',
    }

    if action in add_product_actions:
        await handle_admin_add_product_input(update, context, action, text)
        return

    if action.startswith('admin_edit_'):
        from handlers.admin import handle_admin_edit_product_input
        await handle_admin_edit_product_input(update, context, action, text)
        return

    # Если дошли сюда — неизвестное состояние
    logger.warning(f"Неизвестное или необрабатываемое состояние: {action}")
    db.clear_pending_action(user.id)
    await message.reply_text("Состояние сброшено. Начните заново.")
