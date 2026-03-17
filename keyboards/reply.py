from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS, LANGUAGES, TOP_CURRENCIES, CRYPTO_CURRENCIES
from database import db

def get_text(key, user_id=None, **kwargs):
    """Получить текст на языке пользователя"""
    # Определяем язык пользователя
    lang = 'ru'  # по умолчанию
    if user_id:
        user = db.get_user(user_id)
        if user and user.get('language'):
            lang = user.get('language')
    
    # Получаем текст
    text = LANGUAGES[lang].get(key, key)
    return text.format(**kwargs) if kwargs else text

def main_menu(user_id):
    """Главное меню"""
    balance = db.get_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton(get_text('services', user_id), callback_data='services')],
        [
            InlineKeyboardButton(get_text('balance', user_id, balance=balance), callback_data='balance'),
            InlineKeyboardButton(get_text('profile', user_id), callback_data='profile')
        ],
        [InlineKeyboardButton(get_text('referral', user_id), callback_data='referral')],
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin')])
    
    return InlineKeyboardMarkup(keyboard)

def back_button(callback_data='menu', user_id=None):
    """Кнопка назад"""
    return InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back', user_id), callback_data=callback_data)]])

def cancel_button(user_id=None):
    """Кнопка отмены"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='cancel_input')]])

def categories_menu(user_id=None):
    """Меню категорий из БД"""
    categories = db.get_categories()
    
    keyboard = []
    for cat_id, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f'cat_{cat_id}')])
    keyboard.append([InlineKeyboardButton(get_text('back', user_id), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)

def currency_menu(user_id=None):
    """Меню выбора валюты"""
    keyboard = []
    row = []
    for i, currency in enumerate(TOP_CURRENCIES, 1):
        name = CRYPTO_CURRENCIES.get(currency, currency)
        btn = InlineKeyboardButton(name, callback_data=f'curr_{currency}')
        row.append(btn)
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_text('back', user_id), callback_data='balance')])
    return InlineKeyboardMarkup(keyboard)

def amount_menu(currency, user_id=None):
    """Меню выбора суммы"""
    amounts = [10, 25, 50, 100, 250, 500]
    keyboard = []
    row = []
    for i, amount in enumerate(amounts, 1):
        btn = InlineKeyboardButton(f"${amount}", callback_data=f'amount_{currency}_{amount}')
        row.append(btn)
        if i % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("💰 Другая сумма", callback_data=f'amount_{currency}_custom')])
    keyboard.append([InlineKeyboardButton(get_text('back', user_id), callback_data='deposit')])
    return InlineKeyboardMarkup(keyboard)

def deposit_menu(user_id=None):
    """Меню пополнения"""
    keyboard = [
        [InlineKeyboardButton(get_text('back', user_id), callback_data='balance')]
    ]
    return InlineKeyboardMarkup(keyboard)