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
        self.CHANNEL_URL = os.getenv('CHANNEL_URL', 'https://t.me/helpergrailed')
        
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
                'faq': "❓ FAQ",
                'back': "◀️ Назад",
                'balance': "💰 Баланс: ${balance}",
                'deposit': "💰 Пополнить",
                'withdraw': "💸 Вывести",
                'transfer': "💸 Перевести",
                'transfer_balance': "💸 Перевести средства",
                'enter_transfer_recipient': "Введите @username или Telegram ID получателя:",
                'enter_transfer_amount': "Введите сумму перевода в USD:",
                'transfer_recipient_found': "Получатель найден",
                'transfer_self_error': "❌ Нельзя перевести средства самому себе.",
                'transfer_user_not_found': "❌ Пользователь не найден. Попросите его сначала запустить бота.",
                'transfer_invalid_amount': "❌ Введите корректную сумму больше 0.",
                'transfer_insufficient_funds': "❌ Недостаточно средств на балансе.",
                'transfer_success': "✅ Перевод выполнен.",
                'transfer_received': "💸 Вам поступил перевод",
                'support_button': "🆘 Тех поддержка",
                'support_title': "🆘 Тех. поддержка",
                'support_contact_text': "Свяжитесь с нами здесь:",
                'details_button': "ℹ️ Подробнее",
                'info_service_note': "Это информационная услуга. Следуйте инструкции ниже, чтобы получить её.",
                'transfer_unexpected_error': "❌ Ошибка при переводе. Попробуйте ещё раз.",
                'buy': "✅ Купить за ${price:.2f}",
                'choose_category': "📂 Выберите категорию:",
                'choose_subcategory': "📂 Выберите подкатегорию:",
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
                'referral_details': "Подробная статистика",
                'no_referrals_yet': "У вас пока нет приглашённых пользователей.",
                'error': "Ошибка",
            },
            'en': {
                'welcome': "👋 Hello, {name}!\nWelcome to @helpgrailed_bot",
                'main_menu': "🏠 Main menu",
                'services': "🛒 Services",
                'profile': "👤 Profile",
                'referral': "🔗 Referral",
                'faq': "❓ FAQ",
                'back': "◀️ Back",
                'balance': "💰 Balance: ${balance}",
                'deposit': "💰 Deposit",
                'withdraw': "💸 Withdraw",
                'transfer': "💸 Transfer",
                'transfer_balance': "💸 Transfer funds",
                'enter_transfer_recipient': "Enter recipient @username or Telegram ID:",
                'enter_transfer_amount': "Enter transfer amount in USD:",
                'transfer_recipient_found': "Recipient found",
                'transfer_self_error': "❌ You cannot transfer funds to yourself.",
                'transfer_user_not_found': "❌ User not found. Ask them to start the bot first.",
                'transfer_invalid_amount': "❌ Enter a valid amount greater than 0.",
                'transfer_insufficient_funds': "❌ Insufficient balance.",
                'transfer_success': "✅ Transfer completed.",
                'transfer_received': "💸 You received a transfer",
                'support_button': "🆘 Support",
                'support_title': "🆘 Technical Support",
                'support_contact_text': "Contact us here:",
                'details_button': "ℹ️ Details",
                'info_service_note': "This is an informational service. Follow the instructions below to get it.",
                'transfer_unexpected_error': "❌ Transfer failed. Please try again.",
                'buy': "✅ Buy for ${price:.2f}",
                'choose_category': "📂 Choose category:",
                'choose_subcategory': "📂 Choose subcategory:",
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
                'referral_details': "Detailed stats",
                'no_referrals_yet': "You have no invited users yet.",
                'error': "Error",
            },
            'uk': {
                'welcome': "👋 Привіт, {name}!\nЛаскаво просимо до @helpgrailed_bot",
                'main_menu': "🏠 Головне меню",
                'services': "🛒 Послуги",
                'profile': "👤 Профіль",
                'referral': "🔗 Рефералка",
                'faq': "❓ FAQ",
                'back': "◀️ Назад",
                'balance': "💰 Баланс: ${balance}",
                'deposit': "💰 Поповнити",
                'withdraw': "💸 Вивести",
                'transfer': "💸 Переказати",
                'transfer_balance': "💸 Переказати кошти",
                'enter_transfer_recipient': "Введіть @username або Telegram ID отримувача:",
                'enter_transfer_amount': "Введіть суму переказу в USD:",
                'transfer_recipient_found': "Отримувача знайдено",
                'transfer_self_error': "❌ Не можна переказати кошти самому собі.",
                'transfer_user_not_found': "❌ Користувача не знайдено. Попросіть його спочатку запустити бота.",
                'transfer_invalid_amount': "❌ Введіть коректну суму більше 0.",
                'transfer_insufficient_funds': "❌ Недостатньо коштів на балансі.",
                'transfer_success': "✅ Переказ виконано.",
                'transfer_received': "💸 Вам надійшов переказ",
                'support_button': "🆘 Тех підтримка",
                'support_title': "🆘 Тех. підтримка",
                'support_contact_text': "Зв'яжіться з нами тут:",
                'details_button': "ℹ️ Детальніше",
                'info_service_note': "Це інформаційна послуга. Дотримуйтесь інструкції нижче, щоб отримати її.",
                'transfer_unexpected_error': "❌ Помилка переказу. Спробуйте ще раз.",
                'buy': "✅ Купити за ${price:.2f}",
                'choose_category': "📂 Виберіть категорію:",
                'choose_subcategory': "📂 Виберіть підкатегорію:",
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
                'referral_details': "Детальна статистика",
                'no_referrals_yet': "У вас ще немає запрошених користувачів.",
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
            'min_deposit': '❌ Минимальная сумма - 1',
            'max_deposit': '❌ Максимальная сумма - 10000',
            'invalid_number': '❌ Введите число (например: 25)',
            'invoice_created': 'Счёт создан',
            'invoice_amount': 'Сумма',
            'invoice_pay': 'Перейти к оплате',
            'invoice_after': '⏳ После оплаты баланс обновится автоматически',
            'invoice_create_error': '❌ Ошибка при создании счёта. Попробуйте позже.',
            'withdraw_title': 'Вывод средств',
            'withdraw_available': 'Доступно',
            'withdraw_contact': 'Для вывода напишите администратору',
            'withdraw_rules': 'Вывод возможен от 10 USDT. Комиссия - 5%.',
            'promo_discount': '💸 Скидка по промокоду',
            'promo_was': '💰 Было',
            'faq_intro': 'Выберите вопрос, чтобы быстро получить ответ.',
            'order_status': 'Статус',
            'order_status_pending': 'Ожидает',
            'order_status_in_progress': 'В работе',
            'order_status_completed': 'Завершён',
            'order_status_cancelled': 'Отменён',
            'my_orders': 'Мои заказы',
            'no_orders': 'У вас пока нет заказов.',
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
            'min_deposit': '❌ Minimum amount is 1',
            'max_deposit': '❌ Maximum amount is 10000',
            'invalid_number': '❌ Enter a number (e.g. 25)',
            'invoice_created': 'Invoice created',
            'invoice_amount': 'Amount',
            'invoice_pay': 'Pay invoice',
            'invoice_after': '⏳ After payment, balance updates automatically',
            'invoice_create_error': '❌ Error creating invoice. Please try again later.',
            'withdraw_title': 'Withdraw',
            'withdraw_available': 'Available',
            'withdraw_contact': 'To withdraw, contact admin',
            'withdraw_rules': 'Withdrawals available from 10 USDT. Fee: 5%.',
            'promo_discount': '💸 Promo discount',
            'promo_was': '💰 Was',
            'faq_intro': 'Choose a question to get a quick answer.',
            'order_status': 'Status',
            'order_status_pending': 'Pending',
            'order_status_in_progress': 'In progress',
            'order_status_completed': 'Completed',
            'order_status_cancelled': 'Cancelled',
            'my_orders': 'My orders',
            'no_orders': 'You have no orders yet.',
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
            'min_deposit': '❌ Мінімальна сума - 1',
            'max_deposit': '❌ Максимальна сума - 10000',
            'invalid_number': '❌ Введіть число (наприклад: 25)',
            'invoice_created': 'Рахунок створено',
            'invoice_amount': 'Сума',
            'invoice_pay': 'Перейти до оплати',
            'invoice_after': '⏳ Після оплати баланс оновиться автоматично',
            'invoice_create_error': '❌ Помилка створення рахунку. Спробуйте пізніше.',
            'withdraw_title': 'Виведення коштів',
            'withdraw_available': 'Доступно',
            'withdraw_contact': 'Для виводу напишіть адміністратору',
            'withdraw_rules': 'Вивід можливий від 10 USDT. Комісія - 5%.',
            'promo_discount': '💸 Знижка за промокодом',
            'promo_was': '💰 Було',
            'faq_intro': 'Оберіть питання, щоб швидко отримати відповідь.',
            'order_status': 'Статус',
            'order_status_pending': 'Очікує',
            'order_status_in_progress': 'В роботі',
            'order_status_completed': 'Завершено',
            'order_status_cancelled': 'Скасовано',
            'my_orders': 'Мої замовлення',
            'no_orders': 'У вас ще немає замовлень.',
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
            return {}
    
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
