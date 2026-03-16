from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS, LANGUAGES, TOP_CURRENCIES, CRYPTO_CURRENCIES
from database import db

def get_text(key, **kwargs):
    """Получить текст на русском"""
    text = LANGUAGES['ru'].get(key, key)
    return text.format(**kwargs) if kwargs else text

def main_menu(user_id):
    """Главное меню (только inline кнопки, без текстовых)"""
    # Получаем баланс пользователя
    balance = db.get_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton(get_text('services'), callback_data='services')],
        [
            InlineKeyboardButton(get_text('balance', balance=balance), callback_data='balance'),
            InlineKeyboardButton(get_text('profile'), callback_data='profile')
        ],
        [InlineKeyboardButton(get_text('referral'), callback_data='referral')],
    ]
    
    # Добавляем кнопку админки если пользователь админ
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data='admin')])
    
    return InlineKeyboardMarkup(keyboard)

def back_button(callback_data='menu'):
    """Кнопка назад"""
    return InlineKeyboardMarkup([[InlineKeyboardButton(get_text('back'), callback_data=callback_data)]])

def cancel_button():
    """Кнопка отмены"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data='cancel_input')]])

def categories_menu():
    """Меню категорий из БД"""
    # Получаем категории из базы данных
    categories = db.get_categories()
    
    keyboard = []
    for cat_id, cat_name in categories.items():
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f'cat_{cat_id}')])
    keyboard.append([InlineKeyboardButton(get_text('back'), callback_data='menu')])
    return InlineKeyboardMarkup(keyboard)

def currency_menu():
    """Меню выбора валюты"""
    keyboard = []
    row = []
    for i, currency in enumerate(TOP_CURRENCIES, 1):
        name = CRYPTO_CURRENCIES.get(currency, currency)
        btn = InlineKeyboardButton(name, callback_data=f'curr_{currency}')
        row.append(btn)
        if i % 2 == 0:  # по 2 в ряд
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_text('back'), callback_data='balance')])
    return InlineKeyboardMarkup(keyboard)

def amount_menu(currency):
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
    keyboard.append([InlineKeyboardButton(get_text('back'), callback_data='deposit')])
    return InlineKeyboardMarkup(keyboard)

def deposit_menu():
    """Меню пополнения"""
    keyboard = [
        [InlineKeyboardButton(get_text('back'), callback_data='balance')]
    ]
    return InlineKeyboardMarkup(keyboard)