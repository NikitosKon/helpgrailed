from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import ADMIN_IDS
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def admin_promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления промокодами"""
    query = update.callback_query
    user = query.from_user
    
    if not db.is_admin(user.id):
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Создать промокод", callback_data='admin_create_promo')],
        [InlineKeyboardButton("📋 Список промокодов", callback_data='admin_list_promo')],
        [InlineKeyboardButton("📊 Статистика промокодов", callback_data='admin_promo_stats')],
        [InlineKeyboardButton("❌ Деактивировать", callback_data='admin_deactivate_promo')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_products')]
    ]
    
    await query.edit_message_text(
        "🎫 <b>Управление промокодами</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def admin_create_promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания промокода"""
    query = update.callback_query
    user = query.from_user
    
    context.user_data['creating_promo'] = True
    
    keyboard = [
        [InlineKeyboardButton("💰 На баланс", callback_data='promo_type_balance')],
        [InlineKeyboardButton("🛍️ На конкретный товар", callback_data='promo_type_product')],
        [InlineKeyboardButton("📦 На категорию", callback_data='promo_type_category')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin_promo_menu')]
    ]
    
    await query.edit_message_text(
        "🎫 <b>Создание промокода</b>\n\n"
        "Выберите тип промокода:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_promo_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Обработка выбора типа промокода"""
    query = update.callback_query
    user = query.from_user
    
    if callback_data == 'promo_type_balance':
        context.user_data['promo_type'] = 'balance'
        context.user_data['target_type'] = 'all'
        context.user_data['target_id'] = 0
        
        # Генерируем код автоматически
        generated_code = db.generate_random_code()
        context.user_data['promo_code'] = generated_code
        
        # Сразу переходим к выбору бонуса
        context.user_data['promo_step'] = 'bonus_type'
        db.set_pending_action(user.id, 'admin_create_promo_bonus_type')
        
        keyboard = [
            [InlineKeyboardButton("💸 Скидка на сумму", callback_data='bonus_discount')],
            [InlineKeyboardButton("➕ Бонус на баланс", callback_data='bonus_balance')]
        ]
        
        await query.edit_message_text(
            f"🎫 <b>Создание промокода на баланс</b>\n\n"
            f"Сгенерированный код: <code>{generated_code}</code>\n\n"
            f"Выберите тип бонуса:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    elif callback_data == 'promo_type_product':
        context.user_data['promo_type'] = 'product'
        context.user_data['target_type'] = 'product'
        context.user_data['bonus_type'] = 'discount'
        context.user_data['bonus_value'] = 100
        
        # Сразу показываем товары
        products = db.get_products(show_all=True)
        keyboard = []
        for prod in products[:10]:
            if isinstance(prod, dict):
                name = prod.get('name', 'Товар')
                pid = prod.get('id')
            else:
                name = prod[2]
                pid = prod[0]
            keyboard.append([InlineKeyboardButton(f"📦 {name}", callback_data=f'promo_target_product_{pid}')])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_create_promo')])
        
        await query.edit_message_text(
            "🎫 <b>Создание промокода на товар</b>\n\n"
            "Выберите товар (будет бесплатно):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
    elif callback_data == 'promo_type_category':
        context.user_data['promo_type'] = 'category'
        context.user_data['target_type'] = 'category'
        context.user_data['bonus_type'] = 'discount'
        context.user_data['bonus_value'] = 100
        
        # Получаем категории из БД
        categories = db.get_categories()
        keyboard = []
        for cat_id, cat_name in categories.items():
            keyboard.append([InlineKeyboardButton(f"📂 {cat_name}", callback_data=f'promo_target_category_{cat_id}')])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='admin_create_promo')])
        
        await query.edit_message_text(
            "🎫 <b>Создание промокода на категорию</b>\n\n"
            "Выберите категорию (товары будут бесплатными):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def handle_promo_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Обработка выбора цели промокода"""
    query = update.callback_query
    user = query.from_user
    
    if callback_data.startswith('promo_target_product_'):
        product_id = int(callback_data.replace('promo_target_product_', ''))
        context.user_data['target_id'] = product_id
        
        # Генерируем код автоматически
        generated_code = db.generate_random_code()
        context.user_data['promo_code'] = generated_code
        
        # Переходим к лимитам
        await ask_limits(query, context, user)
        
    elif callback_data.startswith('promo_target_category_'):
        category_id = callback_data.replace('promo_target_category_', '')
        context.user_data['target_id'] = category_id
        
        # Генерируем код автоматически
        generated_code = db.generate_random_code()
        context.user_data['promo_code'] = generated_code
        
        # Переходим к лимитам
        await ask_limits(query, context, user)

async def process_admin_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    """Обработка создания промокода"""
    admin = update.effective_user
    step = context.user_data.get('promo_step')
    
    logger.info(f"📢 process_admin_create_promo: step={step}, text={text}")
    
    # Обработка лимитов
    if step == 'max_entries':
        try:
            max_entries = int(text)
            context.user_data['max_entries'] = max_entries
            context.user_data['promo_step'] = 'max_uses'
            db.set_pending_action(admin.id, 'admin_create_promo_max_uses')
            
            await update.message.reply_text(
                "🔄 <b>Лимит использований</b>\n\n"
                "Сколько раз можно использовать промокод?\n"
                "(введите число, или -1 для безлимита):",
                parse_mode='HTML'
            )
            logger.info(f"✅ max_entries={max_entries}, переходим к max_uses")
            return
            
        except ValueError:
            await update.message.reply_text(
                "❌ Введите целое число (например: 10 или -1)"
            )
            return
    
    elif step == 'max_uses':
        try:
            max_uses = int(text)
            context.user_data['max_uses'] = max_uses
            context.user_data['promo_step'] = 'expires'
            db.set_pending_action(admin.id, 'admin_create_promo_expires')
            
            await update.message.reply_text(
                "⏰ <b>Срок действия</b>\n\n"
                "Срок действия в днях (или 0 для бессрочного):",
                parse_mode='HTML'
            )
            logger.info(f"✅ max_uses={max_uses}, переходим к expires")
            return
            
        except ValueError:
            await update.message.reply_text(
                "❌ Введите целое число (например: 30 или 0)"
            )
            return
    
    elif step == 'expires':
        try:
            days = int(text)
            logger.info(f"✅ expires days={days}")
            
            expires_at = None
            if days > 0:
                expires_at = (datetime.now() + timedelta(days=days)).isoformat()
            
            success = db.create_advanced_promo(
                code=context.user_data['promo_code'],
                bonus_type=context.user_data.get('bonus_type', 'discount'),
                bonus_value=context.user_data.get('bonus_value', 0),
                target_type=context.user_data.get('target_type', 'all'),
                target_id=context.user_data.get('target_id', 0),
                max_entries=context.user_data.get('max_entries', -1),
                max_uses=context.user_data.get('max_uses', -1),
                expires_at=expires_at,
                created_by=admin.id
            )
            
            if success:
                # Получаем название категории если нужно
                target_info = ""
                if context.user_data.get('target_type') == 'category':
                    categories = db.get_categories()
                    cat_name = categories.get(context.user_data['target_id'], context.user_data['target_id'])
                    target_info = f"📂 Категория: {cat_name}\n"
                elif context.user_data.get('target_type') == 'product':
                    product = db.get_product(context.user_data['target_id'])
                    if product:
                        if isinstance(product, dict):
                            product_name = product.get('name', f"ID {context.user_data['target_id']}")
                        else:
                            product_name = product[2]
                        target_info = f"📦 Товар: {product_name}\n"
                    else:
                        target_info = f"📦 Товар: ID {context.user_data['target_id']}\n"
                
                result_text = (
                    f"✅ <b>Промокод успешно создан!</b>\n\n"
                    f"Код: <code>{context.user_data['promo_code']}</code>\n"
                )
                
                if context.user_data.get('bonus_type') == 'discount':
                    result_text += f"💸 Скидка: {context.user_data['bonus_value']}%\n"
                else:
                    result_text += f"💰 Бонус на баланс: ${context.user_data['bonus_value']}\n"
                
                result_text += target_info
                result_text += f"👥 Могут ввести: {context.user_data['max_entries']}\n"
                result_text += f"🔄 Использований: {context.user_data['max_uses']}\n"
                result_text += f"⏰ Срок: {days if days > 0 else 'бессрочно'}"
                
                await update.message.reply_text(
                    result_text,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ В меню промокодов", callback_data='admin_promo_menu')
                    ]]),
                    parse_mode='HTML'
                )
                logger.info(f"✅ Промокод создан: {context.user_data['promo_code']}")
            else:
                await update.message.reply_text("❌ Ошибка при создании промокода")
            
            db.clear_pending_action(admin.id)
            context.user_data.clear()
            return
            
        except ValueError:
            await update.message.reply_text("❌ Введите число")
            return
    
    # Обработка типа бонуса для баланса
    elif step == 'bonus_type':
        if text == 'bonus_discount':
            context.user_data['bonus_type'] = 'discount'
            context.user_data['promo_step'] = 'discount_value'
            db.set_pending_action(admin.id, 'admin_create_promo_discount_value')
            
            await update.message.reply_text(
                "Введите процент скидки (от 1 до 100):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
                ]])
            )
            
        elif text == 'bonus_balance':
            context.user_data['bonus_type'] = 'balance'
            context.user_data['promo_step'] = 'balance_value'
            db.set_pending_action(admin.id, 'admin_create_promo_balance_value')
            
            await update.message.reply_text(
                "Введите сумму бонуса на баланс (в $):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
                ]])
            )
        return
    
    # Обработка значения скидки
    elif step == 'discount_value':
        try:
            value = float(text)
            if value < 1 or value > 100:
                await update.message.reply_text("❌ Введите число от 1 до 100")
                return
            
            context.user_data['bonus_value'] = value
            await ask_limits(update, context, admin)
            
        except ValueError:
            await update.message.reply_text("❌ Введите число")
        return
            
    elif step == 'balance_value':
        try:
            clean_text = text.replace('$', '').replace(',', '.').strip()
            value = float(clean_text)
            
            if value < 1:
                await update.message.reply_text("❌ Минимальная сумма - 1")
                return
            if value > 10000:
                await update.message.reply_text("❌ Максимальная сумма - 10000")
                return
            
            context.user_data['bonus_value'] = value
            context.user_data['bonus_type'] = 'balance'
            
            await ask_limits(update, context, admin)
            
        except ValueError:
            await update.message.reply_text(
                "❌ Введите число (например: 50)\n"
                "Используйте только цифры и точку для копеек.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
                ]])
            )
        return

async def ask_limits(update, context, admin):
    """Запрос лимитов промокода"""
    context.user_data['promo_step'] = 'max_entries'
    db.set_pending_action(admin.id, 'admin_create_promo_max_entries')
    
    # Показываем сгенерированный код
    promo_code = context.user_data.get('promo_code', '')
    
    await update.message.reply_text(
        f"✅ Код: <code>{promo_code}</code>\n\n"
        f"Сколько пользователей могут ввести этот промокод?\n"
        f"(введите число, или -1 для безлимита):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='admin_promo_menu')
        ]]),
        parse_mode='HTML'
    )
