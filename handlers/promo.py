from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import back_button
from config import SUPPORT_CONTACT, ADMIN_IDS, CATEGORIES
import logging

logger = logging.getLogger(__name__)

async def handle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки промокода"""
    query = update.callback_query
    user = query.from_user
    
    context.user_data['awaiting_promo'] = True
    db.set_pending_action(user.id, 'enter_promo')
    
    await query.edit_message_text(
        "🎫 <b>Введите промокод</b>\n\n"
        "Отправьте промокод в чат:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='balance')
        ]]),
        parse_mode='HTML'
    )

async def process_promo_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    """Обработка ввода промокода"""
    user = update.effective_user
    
    # Проверяем промокод
    valid, result = db.validate_advanced_promo(text.upper(), user.id)
    
    if not valid:
        await update.message.reply_text(
            f"❌ {result}",
            reply_markup=back_button('balance')
        )
        db.clear_pending_action(user.id)
        return
    
    promo_data = result
    
    # Записываем, что пользователь ввел промокод
    db.record_promo_entry(promo_data['id'], user.id)
    
    # Сохраняем промокод в контекст
    context.user_data['active_promo'] = {
        'code': text.upper(),
        'data': promo_data
    }
    
    # Формируем сообщение в зависимости от типа промокода
    from config import SUPPORT_CONTACT, ADMIN_IDS
    
    if promo_data['target_type'] == 'product' and promo_data['bonus_value'] == 100:
        # Бесплатный товар
        product = db.get_product(promo_data['target_id'])
        if product:
            product_name = product.get('name', 'товар') if isinstance(product, dict) else product[2]
        else:
            product_name = f"товар (ID: {promo_data['target_id']})"
        
        message = (
            f"🎉 <b>Промокод активирован!</b>\n\n"
            f"Вы получили бесплатный товар:\n"
            f"📦 <b>{product_name}</b>\n\n"
            f"📞 Напишите {SUPPORT_CONTACT} и отправьте этот код, чтобы получить товар:\n"
            f"<code>{text.upper()}</code>\n\n"
            f"🆔 Ваш ID: <code>{user.id}</code>"
        )
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🎁 <b>ЗАПРОС НА БЕСПЛАТНЫЙ ТОВАР</b>\n\n"
                    f"👤 Пользователь: @{user.username or 'нет'} (ID: {user.id})\n"
                    f"📦 Товар: {product_name}\n"
                    f"🎫 Промокод: {text.upper()}\n\n"
                    f"Свяжитесь с пользователем для выдачи товара!",
                    parse_mode='HTML'
                )
            except:
                pass
                
    elif promo_data['target_type'] == 'category' and promo_data['bonus_value'] == 100:
        # Бесплатная категория
        category_name = CATEGORIES.get(promo_data['target_id'], promo_data['target_id'])
        
        message = (
            f"🎉 <b>Промокод активирован!</b>\n\n"
            f"Вы получили бесплатный доступ к категории:\n"
            f"📂 <b>{category_name}</b>\n\n"
            f"📞 Напишите {SUPPORT_CONTACT} и отправьте этот код, чтобы получить товары:\n"
            f"<code>{text.upper()}</code>\n\n"
            f"🆔 Ваш ID: <code>{user.id}</code>"
        )
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🎁 <b>ЗАПРОС НА БЕСПЛАТНУЮ КАТЕГОРИЮ</b>\n\n"
                    f"👤 Пользователь: @{user.username or 'нет'} (ID: {user.id})\n"
                    f"📂 Категория: {category_name}\n"
                    f"🎫 Промокод: {text.upper()}\n\n"
                    f"Свяжитесь с пользователем для выдачи товаров!",
                    parse_mode='HTML'
                )
            except:
                pass
    else:
        # Обычный промокод (на баланс или со скидкой)
        if promo_data['target_type'] == 'product':
            product = db.get_product(promo_data['target_id'])
            product_name = product.get('name', 'товар') if isinstance(product, dict) else product[2]
            target_text = f"🎯 Товар: <b>{product_name}</b>"
            usage_text = "Промокод будет применен при покупке этого товара!"
        elif promo_data['target_type'] == 'category':
            category_name = CATEGORIES.get(promo_data['target_id'], promo_data['target_id'])
            target_text = f"📂 Категория: <b>{category_name}</b>"
            usage_text = "Промокод будет применен при покупке любого товара из этой категории!"
        else:
            target_text = ""
            usage_text = "Промокод будет применен при следующем пополнении!"
        
        bonus_text = f"💸 Скидка: {promo_data['bonus_value']}%" if promo_data['bonus_type'] == 'discount' else f"💰 Бонус на баланс: ${promo_data['bonus_value']}"
        
        message = f"✅ Промокод активирован!\n\n"
        if target_text:
            message += f"{target_text}\n"
        message += f"{bonus_text}\n\n"
        message += f"{usage_text}"
    
    await update.message.reply_text(
        message,
        reply_markup=back_button('balance'),
        parse_mode='HTML'
    )
    
    db.clear_pending_action(user.id)