import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Централизованная конфигурация бота"""
    
    def __init__(self):
        # Токены
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.CRYPTO_TOKEN = os.getenv('CRYPTO_TOKEN')
        
        # ID админов (загружаем из переменной окружения)
        admin_ids_str = os.getenv('ADMIN_IDS', '[5060808767, 882950874]')
        try:
            self.ADMIN_IDS = json.loads(admin_ids_str)
        except:
            self.ADMIN_IDS = [5060808767, 882950874]
        
        # Контакты
        self.ADMIN_CONTACT = os.getenv('ADMIN_CONTACT', '@helpgrailed')
        self.SUPPORT_CONTACT = os.getenv('SUPPORT_CONTACT', '@helpgrailed')
        self.CHANNEL_URL = os.getenv('CHANNEL_URL', 'https://t.me/helpgrailed')
        
        # База данных
        self.DB_FILE = os.getenv('DB_FILE', 'helpgrailed_bot.db')
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        
        # Реферальный бонус
        self.REFERRAL_BONUS = float(os.getenv('REFERRAL_BONUS', '0.1'))
        
        # Лимиты
        self.MIN_DEPOSIT = 1.0
        self.MAX_DEPOSIT = 10000.0
        self.ANTI_FLOOD_INTERVAL = 0.6
        
        # Прокси для CryptoPay (если нужны)
        self.PROXY_LIST = []
        
        # Языки - ПОЛНАЯ ВЕРСИЯ СО ВСЕМИ КЛЮЧАМИ
        self.LANGUAGES = {
            'ru': {
                'welcome': "👋 Привет, {name}!\nДобро пожаловать в @helpgrailed_bot",
                'main_menu': "🏠 Главное меню",
                'services': "🛒 Услуги",
                'profile': "👤 Профиль",
                'referral': "🔗 Рефералка",
                'back': "◀️ Назад",
                'balance': "💰 Баланс: ${balance}",
                'deposit': "💰 Пополнить",
                'withdraw': "💸 Вывести",
                'buy': "✅ Купить за ${price:.2f}",
                'choose_category': "📂 Выберите категорию:",
                'choose_item': "Выберите товар:",
                'in_stock': "в наличии",
                'no_items': "😕 В этой категории пока нет товаров.",
                'insufficient_funds': "❌ Недостаточно средств",
                'purchase_success': "✅ Покупка успешно оформлена!",
                'choose_language': "🌐 Выберите язык / Choose language / Оберіть мову:",
                'language_changed': "✅ Язык изменен на русский",
                'referral_description': "Приглашайте друзей и получайте 10% от их первой покупки!",
                'your_link': "Ваша ссылка",
                'invited': "Приглашено",
                'earned': "Заработано",
                'error': "Ошибка",
            },
            'en': {
                'welcome': "👋 Hello, {name}!\nWelcome to @helpgrailed_bot",
                'main_menu': "🏠 Main menu",
                'services': "🛒 Services",
                'profile': "👤 Profile",
                'referral': "🔗 Referral",
                'back': "◀️ Back",
                'balance': "💰 Balance: ${balance}",
                'deposit': "💰 Deposit",
                'withdraw': "💸 Withdraw",
                'buy': "✅ Buy for ${price:.2f}",
                'choose_category': "📂 Choose category:",
                'choose_item': "Choose product:",
                'in_stock': "in stock",
                'no_items': "😕 No products in this category yet.",
                'insufficient_funds': "❌ Insufficient funds",
                'purchase_success': "✅ Purchase successful!",
                'choose_language': "🌐 Choose language / Оберіть мову / Выберите язык:",
                'language_changed': "✅ Language changed to English",
                'referral_description': "Invite friends and get 10% from their first purchase!",
                'your_link': "Your link",
                'invited': "Invited",
                'earned': "Earned",
                'error': "Error",
            },
            'uk': {
                'welcome': "👋 Привіт, {name}!\nЛаскаво просимо до @helpgrailed_bot",
                'main_menu': "🏠 Головне меню",
                'services': "🛒 Послуги",
                'profile': "👤 Профіль",
                'referral': "🔗 Рефералка",
                'back': "◀️ Назад",
                'balance': "💰 Баланс: ${balance}",
                'deposit': "💰 Поповнити",
                'withdraw': "💸 Вивести",
                'buy': "✅ Купити за ${price:.2f}",
                'choose_category': "📂 Виберіть категорію:",
                'choose_item': "Виберіть товар:",
                'in_stock': "в наявності",
                'no_items': "😕 У цій категорії ще немає товарів.",
                'insufficient_funds': "❌ Недостатньо коштів",
                'purchase_success': "✅ Покупка успішна!",
                'choose_language': "🌐 Оберіть мову / Choose language / Выберите язык:",
                'language_changed': "✅ Мову змінено на українську",
                'referral_description': "Запрошуйте друзів та отримуйте 10% від їхньої першої покупки!",
                'your_link': "Ваше посилання",
                'invited': "Запрошено",
                'earned': "Зароблено",
                'error': "Помилка",
            }
        }

        self.LANGUAGES['ru'].update({
            'profile_title': 'Профиль',
            'username_label': 'Username',
            'not_set': 'нет',
            'purchases_label': 'Покупок',
            'total_spent_label': 'Всего потрачено',
            'referrals_label': 'Рефералов',
            'purchase_history': 'История покупок',
            'your_purchases': 'Ваши покупки',
            'no_purchases': 'У вас пока нет покупок.',
            'balance_title': 'Баланс',
            'current_balance': 'Текущий баланс',
            'choose_action': 'Выберите действие:',
            'promo_code': 'Промокод',
            'other_amount': 'Другая сумма',
            'choose_deposit_currency': 'Выберите валюту для пополнения:',
            'selected_currency': 'Выбрана валюта',
            'choose_deposit_amount': 'Выберите сумму пополнения:',
            'enter_deposit_amount': 'Введите сумму пополнения (только число):',
        })
        self.LANGUAGES['en'].update({
            'profile_title': 'Profile',
            'username_label': 'Username',
            'not_set': 'not set',
            'purchases_label': 'Purchases',
            'total_spent_label': 'Total spent',
            'referrals_label': 'Referrals',
            'purchase_history': 'Purchase history',
            'your_purchases': 'Your purchases',
            'no_purchases': 'You have no purchases yet.',
            'balance_title': 'Balance',
            'current_balance': 'Current balance',
            'choose_action': 'Choose an action:',
            'promo_code': 'Promo code',
            'other_amount': 'Other amount',
            'choose_deposit_currency': 'Choose deposit currency:',
            'selected_currency': 'Selected currency',
            'choose_deposit_amount': 'Choose deposit amount:',
            'enter_deposit_amount': 'Enter deposit amount (numbers only):',
        })
        self.LANGUAGES['uk'].update({
            'profile_title': 'Профіль',
            'username_label': 'Username',
            'not_set': 'немає',
            'purchases_label': 'Покупок',
            'total_spent_label': 'Всього витрачено',
            'referrals_label': 'Рефералів',
            'purchase_history': 'Історія покупок',
            'your_purchases': 'Ваші покупки',
            'no_purchases': 'У вас ще немає покупок.',
            'balance_title': 'Баланс',
            'current_balance': 'Поточний баланс',
            'choose_action': 'Оберіть дію:',
            'promo_code': 'Промокод',
            'other_amount': 'Інша сума',
            'choose_deposit_currency': 'Оберіть валюту для поповнення:',
            'selected_currency': 'Обрана валюта',
            'choose_deposit_amount': 'Оберіть суму поповнення:',
            'enter_deposit_amount': 'Введіть суму поповнення (тільки число):',
        })
        
        # Список поддерживаемых валют в CryptoPay
        self.CRYPTO_CURRENCIES = {
            'USDT': 'USDT (TRC-20)',
            'TON': 'TON',
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'BNB': 'BNB',
            'TRX': 'TRX',
            'USDC': 'USDC',
            'BUSD': 'BUSD',
            'EUR': 'EUR (крипто-евро)'
        }
        
        # Сортированный список для отображения
        self.TOP_CURRENCIES = ['USDT', 'TON', 'BTC', 'ETH', 'BNB', 'TRX', 'USDC', 'BUSD', 'EUR']
        
        self.validate()
    
    @property
    def CATEGORIES(self):
        """Геттер для категорий - всегда свежие из БД"""
        try:
            from database import db
            return db.get_categories()
        except Exception as e:
            print(f"Error loading categories from DB: {e}")
            return {
                'grailed_accounts': "📱 Grailed account's",
                'paypal': "💳 PayPal",
                'call_service': "📞 Прозвон сервис",
                'grailed_likes': "❤️ Накрутка лайков на Grailed",
                'ebay': "🏷 eBay",
                'support': "🆘 Тех поддержка",
            }
    
    def validate(self):
        """Валидация конфигурации"""
        if not self.BOT_TOKEN or len(self.BOT_TOKEN) < 40:
            raise ValueError("❌ Неверный формат BOT_TOKEN")
        
        if not self.CRYPTO_TOKEN or len(self.CRYPTO_TOKEN) < 40:
            raise ValueError("❌ Неверный формат CRYPTO_TOKEN")
        
        if not self.ADMIN_IDS:
            raise ValueError("❌ Не указаны администраторы")
    
    def get_text(self, key: str, lang: str = 'ru', **kwargs) -> str:
        """Получить текст на нужном языке"""
        if lang not in self.LANGUAGES:
            lang = 'ru'
        
        text = self.LANGUAGES[lang].get(key, key)
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except:
                return text
        return text


# Создаем экземпляр config
config = Config()

# Для обратной совместимости со старым кодом
BOT_TOKEN = config.BOT_TOKEN
CRYPTO_TOKEN = config.CRYPTO_TOKEN
ADMIN_IDS = config.ADMIN_IDS
ADMIN_CONTACT = config.ADMIN_CONTACT
SUPPORT_CONTACT = config.SUPPORT_CONTACT
DB_FILE = config.DB_FILE
DATABASE_URL = config.DATABASE_URL
REFERRAL_BONUS = config.REFERRAL_BONUS
LANGUAGES = config.LANGUAGES
CRYPTO_CURRENCIES = config.CRYPTO_CURRENCIES
TOP_CURRENCIES = config.TOP_CURRENCIES
CHANNEL_URL = config.CHANNEL_URL
