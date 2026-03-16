from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from keyboards.reply import deposit_menu, currency_menu, amount_menu, get_text, back_button, cancel_button
from crypto import create_crypto_invoice
from config import ADMIN_CONTACT, CRYPTO_CURRENCIES
import logging
from datetime import datetime
import json  # Добавлен импорт

logger = logging.getLogger(__name__)
db = Database()

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс"""
    query = update.callback_query
    user = query.from_user
    balance = db.get_balance(user.id)
    
    text = (
        f"💰 <b>Баланс</b>\n\n"
        f"Текущий баланс: <b>${balance:.2f}</b>\n\n"
        f"Выберите действие:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📥 Пополнить", callback_data='deposit'),
            InlineKeyboardButton("📤 Вывести", callback_data='withdraw')
        ],
        [InlineKeyboardButton("🎫 Промокод", callback_data='promo_code')],
        [InlineKeyboardButton("◀️ Назад", callback_data='menu')]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню пополнения - выбор валюты"""
    query = update.callback_query
    text = "💰 Выберите валюту для пополнения:"
    await query.edit_message_text(text, reply_markup=currency_menu())

async def handle_currency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, currency):
    """Обработка выбора валюты"""
    query = update.callback_query
    user = query.from_user
    
    context.user_data['deposit_currency'] = currency
    
    currency_name = CRYPTO_CURRENCIES.get(currency, currency)
    text = f"💰 Выбрана валюта: {currency_name}\n\nВыберите сумму пополнения:"
    await query.edit_message_text(text, reply_markup=amount_menu(currency))

async def handle_amount_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, currency, amount):
    """Обработка выбора суммы"""
    query = update.callback_query
    user = query.from_user
    
    await create_deposit_invoice(query, user, currency, amount, context)

async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, currency):
    """Обработка кастомной суммы"""
    query = update.callback_query
    user = query.from_user
    
    context.user_data['deposit_currency'] = currency
    db.set_pending_action(user.id, f'deposit_custom_{currency}')
    
    currency_name = CRYPTO_CURRENCIES.get(currency, currency)
    text = f"💰 Валюта: {currency_name}\n\nВведите сумму пополнения (только число):"
    await query.edit_message_text(text, reply_markup=cancel_button())

async def handle_custom_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    """Обработка кастомной суммы"""
    user = update.effective_user
    
    pending = db.get_pending_action(user.id)
    if not pending:
        return
    
    action, data = pending
    currency = action.replace('deposit_custom_', '')
    
    try:
        amount = float(text)
        if amount < 1:
            await update.message.reply_text("❌ Минимальная сумма - 1")
            return
        if amount > 10000:
            await update.message.reply_text("❌ Максимальная сумма - 10000")
            return
        
        db.clear_pending_action(user.id)
        
        # Проверяем наличие промокода
        final_amount = amount
        promo_info = None
        
        if 'active_promo' in context.user_data:
            promo = context.user_data['active_promo']
            valid, result = db.validate_promo_code(promo['code'], user.id, amount)
            if valid:
                promo_result = db.apply_promo_code(promo['code'], user.id, amount)
                if promo_result[0]:
                    final_amount = promo_result[2]['final']
                    promo_info = promo_result[2]
        
        invoice = await create_crypto_invoice(
            amount=final_amount,
            currency=currency,
            description=f"Пополнение баланса на {final_amount} {currency}",
            payload=f"{user.id}:deposit:{currency}"
        )
        
        now = datetime.now().isoformat()
        
        # Сохраняем информацию о промокоде
        metadata = {}
        if promo_info:
            metadata['promo_code'] = promo['code']
            metadata['original_amount'] = amount
            metadata['discount'] = promo_info['discount']
            metadata['final_amount'] = final_amount
        
        db.execute(
            """INSERT INTO transactions 
               (user_id, amount, type, status, invoice_id, currency, created_at, metadata) 
               VALUES (?, ?, 'deposit', 'pending', ?, ?, ?, ?)""",
            (user.id, final_amount, invoice['invoice_id'], currency, now, 
             json.dumps(metadata) if metadata else None),
            commit=True
        )
        
        # Очищаем промокод
        if 'active_promo' in context.user_data:
            del context.user_data['active_promo']
        
        currency_name = CRYPTO_CURRENCIES.get(currency, currency)
        text = (
            f"🧾 <b>Счёт создан</b>\n\n"
            f"💰 Сумма: {final_amount} {currency_name}\n"
        )
        
        if promo_info:
            text += f"💸 Скидка по промокоду: ${promo_info['discount']}\n"
            text += f"💰 Было: ${amount}\n"
        
        text += f"🔗 <a href='{invoice['pay_url']}'>Перейти к оплате</a>\n\n"
        text += f"⏳ После оплаты баланс обновится автоматически"
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except ValueError:
        await update.message.reply_text("❌ Введите число (например: 25)")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка при создании счёта")

async def create_deposit_invoice(query, user, currency, amount, context):
    """Создание инвойса для депозита"""
    try:
        # Проверяем наличие промокода
        final_amount = amount
        promo_info = None
        
        if 'active_promo' in context.user_data:
            promo = context.user_data['active_promo']
            valid, result = db.validate_promo_code(promo['code'], user.id, amount)
            if valid:
                promo_result = db.apply_promo_code(promo['code'], user.id, amount)
                if promo_result[0]:
                    final_amount = promo_result[2]['final']
                    promo_info = promo_result[2]
        
        invoice = await create_crypto_invoice(
            amount=final_amount,
            currency=currency,
            description=f"Пополнение баланса на {final_amount} {currency}",
            payload=f"{user.id}:deposit:{currency}"
        )
        
        now = datetime.now().isoformat()
        
        # Сохраняем информацию о промокоде
        metadata = {}
        if promo_info:
            metadata['promo_code'] = promo['code']
            metadata['original_amount'] = amount
            metadata['discount'] = promo_info['discount']
            metadata['final_amount'] = final_amount
        
        db.execute(
            """INSERT INTO transactions 
               (user_id, amount, type, status, invoice_id, currency, created_at, metadata) 
               VALUES (?, ?, 'deposit', 'pending', ?, ?, ?, ?)""",
            (user.id, final_amount, invoice['invoice_id'], currency, now, 
             json.dumps(metadata) if metadata else None),
            commit=True
        )
        
        # Очищаем промокод
        if 'active_promo' in context.user_data:
            del context.user_data['active_promo']
        
        currency_name = CRYPTO_CURRENCIES.get(currency, currency)
        text = (
            f"🧾 <b>Счёт создан</b>\n\n"
            f"💰 Сумма: {final_amount} {currency_name}\n"
        )
        
        if promo_info:
            text += f"💸 Скидка по промокоду: ${promo_info['discount']}\n"
            text += f"💰 Было: ${amount}\n"
        
        text += f"🔗 <a href='{invoice['pay_url']}'>Перейти к оплате</a>\n\n"
        text += f"⏳ После оплаты баланс обновится автоматически"
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='menu')]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при создании счёта. Попробуйте позже."
        )

async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вывод средств"""
    query = update.callback_query
    user = query.from_user
    balance = db.get_balance(user.id)
    
    text = (
        f"💸 <b>Вывод средств</b>\n\n"
        f"Доступно: ${balance:.2f}\n\n"
        f"Для вывода напишите администратору: {ADMIN_CONTACT}\n\n"
        f"<i>Вывод возможен от 10 USDT. Комиссия - 5%</i>"
    )
    await query.edit_message_text(
        text,
        reply_markup=back_button('balance'),
        parse_mode='HTML'
    )