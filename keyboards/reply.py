from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS, TOP_CURRENCIES, CRYPTO_CURRENCIES
from database import db

def get_text(key, user_id=None, **kwargs):
    """Получить текст на языке пользователя"""
    lang = 'ru'
    if user_id:
        user = db.get_user(user_id)
        if user and user.get('language'):
            lang = user.get('language')
    
    from config import config
    return config.get_text(key, lang, **kwargs)

def main_menu(user_id):
    """Главное меню"""
    balance = db.get_balance(user_id)
    user = db.get_user(user_id) or {}
    lang = user.get('language', 'ru')
    core = db.get_main_menu_core()

    services_label = core.get('services', {}).get(lang) or get_text('services', user_id)
    profile_label = core.get('profile', {}).get(lang) or get_text('profile', user_id)
    referral_label = core.get('referral', {}).get(lang) or get_text('referral', user_id)
    transfer_label = core.get('transfer', {}).get(lang) or get_text('transfer_balance', user_id)
    support_label = core.get('support', {}).get(lang) or get_text('support_button', user_id)

    balance_template = core.get('balance', {}).get(lang) or get_text('balance', user_id, balance=balance)
    try:
        balance_label = balance_template.format(balance=f"{balance:.2f}")
    except Exception:
        balance_label = balance_template
    
    keyboard = [
        [InlineKeyboardButton(services_label, callback_data='services')],
        [
            InlineKeyboardButton(balance_label, callback_data='balance'),
            InlineKeyboardButton(profile_label, callback_data='profile')
        ],
        [
            InlineKeyboardButton(referral_label, callback_data='referral'),
            InlineKeyboardButton(transfer_label, callback_data='transfer')
        ],
        [InlineKeyboardButton(support_label, url='https://t.me/helpgrailed')],
    ]

    for button in db.get_custom_menu_buttons():
        if not button.get('enabled', True):
            continue

        label = (
            button.get(f'label_{lang}')
            or button.get('label_ru')
            or button.get('label_en')
            or 'Button'
        )
        target = button.get('target')
        button_type = button.get('type')

        if not target:
            continue

        if button_type == 'url':
            keyboard.append([InlineKeyboardButton(label, url=target)])
        else:
            keyboard.append([InlineKeyboardButton(label, callback_data=target)])
    
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
    try:
        lang = 'ru'
        if user_id:
            user = db.get_user(user_id)
            if user and user.get('language'):
                lang = user.get('language')

        categories = db.get_categories(lang)
        
        keyboard = []
        if categories:
            for cat_id, cat_name in categories.items():
                keyboard.append([InlineKeyboardButton(cat_name, callback_data=f'cat_{cat_id}')])
        else:
            keyboard.append([InlineKeyboardButton("❌ Категории не найдены", callback_data='menu')])
        
        keyboard.append([InlineKeyboardButton(get_text('back', user_id), callback_data='menu')])
        return InlineKeyboardMarkup(keyboard)
    except Exception as e:
        print(f"ERROR in categories_menu: {e}")
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Ошибка загрузки", callback_data='menu')
        ]])

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
    keyboard.append([InlineKeyboardButton(get_text('other_amount', user_id), callback_data=f'amount_{currency}_custom')])
    keyboard.append([InlineKeyboardButton(get_text('back', user_id), callback_data='deposit')])
    return InlineKeyboardMarkup(keyboard)

def deposit_menu(user_id=None):
    """Меню пополнения"""
    keyboard = [
        [InlineKeyboardButton(get_text('back', user_id), callback_data='balance')]
    ]
    return InlineKeyboardMarkup(keyboard)
