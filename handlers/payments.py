from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards.reply import deposit_menu, currency_menu, amount_menu, get_text, back_button, cancel_button
from crypto import create_crypto_invoice
from config import ADMIN_CONTACT, CRYPTO_CURRENCIES
import logging
import re
from datetime import datetime
import json  # Добавлен импорт

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



def _strip_leading_icon(text: str) -> str:
    return re.sub(r'^[^\w]+', '', text or '').strip()

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс"""
    query = update.callback_query
    user = query.from_user
    balance = db.get_balance(user.id)
    
    text = (
        f"💰 <b>{get_text('balance_title', user.id)}</b>\n\n"
        f"{get_text('current_balance', user.id)}: <b>${balance:.2f}</b>\n\n"
        f"{get_text('choose_action', user.id)}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(get_text('deposit', user.id), callback_data='deposit'),
            InlineKeyboardButton(get_text('withdraw', user.id), callback_data='withdraw')
        ],
        [InlineKeyboardButton(get_text('transfer_balance', user.id), callback_data='transfer')],
        [InlineKeyboardButton(f"🎫 {get_text('promo_code', user.id)}", callback_data='promo_code')],
        [InlineKeyboardButton(get_text('back', user.id), callback_data='menu')]
    ]
    
    await _edit_or_send(query, 
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню пополнения - выбор валюты"""
    query = update.callback_query
    user = query.from_user
    text = f"💰 {get_text('choose_deposit_currency', user.id)}"
    await _edit_or_send(query, text, reply_markup=currency_menu(user.id))

async def handle_currency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, currency):
    """Обработка выбора валюты"""
    query = update.callback_query
    user = query.from_user
    
    context.user_data['deposit_currency'] = currency
    
    currency_name = CRYPTO_CURRENCIES.get(currency, currency)
    text = f"💰 {get_text('selected_currency', user.id)}: {currency_name}\n\n{get_text('choose_deposit_amount', user.id)}"
    await _edit_or_send(query, text, reply_markup=amount_menu(currency, user.id))

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
    text = f"💰 {get_text('selected_currency', user.id)}: {currency_name}\n\n{get_text('enter_deposit_amount', user.id)}"
    await _edit_or_send(query, text, reply_markup=cancel_button(user.id))

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
        
        await _edit_or_send(query, 
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await _edit_or_send(query, 
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
    await _edit_or_send(query, 
        text,
        reply_markup=back_button('balance'),
        parse_mode='HTML'
    )


async def handle_transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Старт перевода между пользователями."""
    query = update.callback_query
    user = query.from_user

    context.user_data.pop('transfer_recipient', None)
    db.set_pending_action(user.id, 'transfer_recipient')

    await _edit_or_send(query, 
        f"💸 <b>{_strip_leading_icon(get_text('transfer_balance', user.id))}</b>\n\n"
        f"{get_text('enter_transfer_recipient', user.id)}",
        reply_markup=cancel_button(user.id),
        parse_mode='HTML'
    )


async def handle_transfer_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
    user = update.effective_user
    value = (text or "").strip()

    if action == 'transfer_recipient':
        recipient = db.find_user_by_identifier(value)
        if not recipient:
            await update.message.reply_text(get_text('transfer_user_not_found', user.id))
            return
        if recipient['user_id'] == user.id:
            await update.message.reply_text(get_text('transfer_self_error', user.id))
            return

        context.user_data['transfer_recipient'] = recipient
        db.set_pending_action(user.id, 'transfer_amount')

        recipient_name = recipient.get('username') or recipient.get('first_name') or str(recipient['user_id'])
        recipient_display = f"@{recipient_name}" if recipient.get('username') else recipient_name
        await update.message.reply_text(
            f"✅ {get_text('transfer_recipient_found', user.id)}: {recipient_display}\n\n"
            f"{get_text('enter_transfer_amount', user.id)}"
        )
        return

    if action == 'transfer_amount':
        recipient = context.user_data.get('transfer_recipient')
        if not recipient:
            db.set_pending_action(user.id, 'transfer_recipient')
            await update.message.reply_text(get_text('enter_transfer_recipient', user.id))
            return

        try:
            amount = float(value.replace(',', '.'))
        except ValueError:
            await update.message.reply_text(get_text('transfer_invalid_amount', user.id))
            return

        if amount <= 0:
            await update.message.reply_text(get_text('transfer_invalid_amount', user.id))
            return

        ok, message, saved_recipient = db.transfer_balance(user.id, str(recipient['user_id']), amount)
        if not ok:
            if message == 'Insufficient funds':
                await update.message.reply_text(get_text('transfer_insufficient_funds', user.id))
            elif message == 'Cannot transfer to self':
                await update.message.reply_text(get_text('transfer_self_error', user.id))
            elif message == 'Recipient not found':
                await update.message.reply_text(get_text('transfer_user_not_found', user.id))
            else:
                await update.message.reply_text(get_text('transfer_unexpected_error', user.id))
            return

        db.clear_pending_action(user.id)
        context.user_data.pop('transfer_recipient', None)

        recipient_name = saved_recipient.get('username') or saved_recipient.get('first_name') or str(saved_recipient['user_id'])
        recipient_display = f"@{recipient_name}" if saved_recipient.get('username') else recipient_name
        await update.message.reply_text(
            f"{get_text('transfer_success', user.id)}\n\n"
            f"👤 {recipient_display}\n"
            f"💰 ${amount:.2f}",
            reply_markup=back_button('balance', user.id)
        )

        try:
            await context.bot.send_message(
                saved_recipient['user_id'],
                f"{get_text('transfer_received', saved_recipient['user_id'])}\n\n"
                f"💰 ${amount:.2f}"
            )
        except Exception as e:
            logger.warning(f"Failed to notify recipient about transfer: {e}")
