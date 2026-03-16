from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database
from handlers.start import start_command
from handlers.services import handle_services, handle_category, handle_product, handle_buy
from handlers.payments import (
    handle_balance, handle_deposit, handle_withdraw,
    handle_currency_selection, handle_amount_selection,
    handle_custom_amount, handle_custom_deposit
)
from handlers.profile import handle_profile, handle_referral, handle_purchase_history
from handlers.admin import (
    handle_admin,
    handle_admin_add_product_input,
    handle_admin_photo_input
)
import logging

logger = logging.getLogger(__name__)
db = Database()

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
    if data in ('menu', 'back'):
        await start_command(update, context)

    # Услуги / категории / товары
    elif data == 'services':
        await handle_services(update, context)
    elif data.startswith('cat_'):
        await handle_category(update, context, data[4:])
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

    # Баланс и платежи
    elif data == 'balance':
        await handle_balance(update, context)
    elif data == 'deposit':
        await handle_deposit(update, context)
    elif data == 'withdraw':
        await handle_withdraw(update, context)
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
    elif data == 'purchase_history':
        await handle_purchase_history(update, context)

    # Админ-панель (все что связано с админкой, включая рассылки)
    elif (data.startswith('admin') or 
          data.startswith('promo_type_') or 
          data.startswith('promo_target_') or
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
        if action == 'admin_add_product_photo_waiting':
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

    # Депозит — кастомная сумма
    if action.startswith('deposit_custom_'):
        await handle_custom_deposit(update, context, text)
        return

    # Ввод промокода
    if action == 'enter_promo':
        from handlers.promo import process_promo_input
        await process_promo_input(update, context, text)
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

    # Добавление категории
    if action == 'admin_add_category_id' or action == 'admin_add_category_name':
        from handlers.admin import handle_admin_add_category_input
        await handle_admin_add_category_input(update, context, action, text)
        return

    # Редактирование категории
    if action.startswith('admin_edit_category_name_'):
        from handlers.admin import handle_admin_edit_category_input
        await handle_admin_edit_category_input(update, context, action, text)
        return

    # Добавление товара — шаги wizard
    add_product_actions = {
        'admin_add_product_name',
        'admin_add_product_category',
        'admin_add_product_price',
        'admin_add_product_desc',
        'admin_add_product_photo_waiting',
        'admin_add_product_stock',
        'admin_add_product_sort',
    }

    if action in add_product_actions:
        await handle_admin_add_product_input(update, context, action, text)
        return

    # Если дошли сюда — неизвестное состояние
    logger.warning(f"Неизвестное или необрабатываемое состояние: {action}")
    db.clear_pending_action(user.id)
    await message.reply_text("Состояние сброшено. Начните заново.")