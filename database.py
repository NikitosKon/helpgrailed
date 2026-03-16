import sqlite3
import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Optional, List, Dict, Any, Tuple
import random
import string

# Импортируем переменные из config
from config import (
    DB_FILE, REFERRAL_BONUS, LANGUAGES
)

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных (поддерживает SQLite и PostgreSQL)"""
    
    def __init__(self):
        # Проверяем, используем ли мы PostgreSQL (на Render)
        self.use_postgres = 'DATABASE_URL' in os.environ
        
        if self.use_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Подключаемся к PostgreSQL
            self.conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
            self.conn.autocommit = False
            logger.info("Connected to PostgreSQL database")
        else:
            # Локально используем SQLite
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database: {DB_FILE}")
        
        self.init_tables()
        self.seed_products()
    
    def execute(self, query: str, params: tuple = (), 
                fetch: bool = False, commit: bool = False) -> Optional[List[Any]]:
        """Безопасное выполнение запроса (работает с SQLite и PostgreSQL)"""
        try:
            c = self.conn.cursor()
            
            # Для PostgreSQL заменяем ? на %s
            if self.use_postgres:
                query = query.replace('?', '%s')
                
            c.execute(query, params)
            
            if commit:
                self.conn.commit()
            
            if fetch:
                if self.use_postgres:
                    return c.fetchall()
                else:
                    return c.fetchall()
            return None
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            if commit:
                self.conn.rollback()
            raise
    
    def init_tables(self):
        """Инициализация таблиц с поддержкой обоих движков"""
        
        if self.use_postgres:
            # PostgreSQL синтаксис
            queries = [
                # Пользователи
                """CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    referrer_id BIGINT,
                    balance REAL DEFAULT 0,
                    language TEXT DEFAULT 'ru',
                    registered_date TEXT,
                    last_active TEXT,
                    is_blocked INTEGER DEFAULT 0,
                    notify_enabled INTEGER DEFAULT 1,
                    admin_note TEXT
                )""",
                
                # Транзакции
                """CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    amount REAL,
                    type TEXT CHECK(type IN ('deposit', 'purchase', 'withdraw', 'referral', 'admin_deposit')),
                    product_id INTEGER,
                    status TEXT CHECK(status IN ('pending', 'completed', 'failed', 'cancelled', 'expired')),
                    invoice_id TEXT,
                    currency TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    promo_code TEXT,
                    discount_amount REAL DEFAULT 0
                )""",
                
                # Рефералы
                """CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id BIGINT,
                    referral_id BIGINT,
                    bonus REAL DEFAULT 0,
                    created_at TEXT,
                    purchase_count INTEGER DEFAULT 0,
                    total_earned REAL DEFAULT 0,
                    UNIQUE(referrer_id, referral_id)
                )""",
                
                # Товары
                """CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price_usd REAL NOT NULL,
                    description TEXT,
                    stock INTEGER DEFAULT -1,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    photo_url TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    sold_count INTEGER DEFAULT 0
                )""",
                
                # Ожидающие действия
                """CREATE TABLE IF NOT EXISTS pending_actions (
                    user_id BIGINT PRIMARY KEY,
                    action TEXT,
                    data TEXT,
                    created_at TEXT
                )""",
                
                # Настройки
                """CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )""",
                
                # История покупок
                """CREATE TABLE IF NOT EXISTS purchase_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    product_id INTEGER,
                    product_name TEXT,
                    amount REAL,
                    status TEXT DEFAULT 'completed',
                    purchase_date TEXT,
                    completed_date TEXT
                )""",
                
                # Промокоды
                """CREATE TABLE IF NOT EXISTS promo_codes (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE,
                    bonus_type TEXT DEFAULT 'discount',
                    bonus_value REAL,
                    target_type TEXT DEFAULT 'all',
                    target_id INTEGER DEFAULT 0,
                    max_entries INTEGER DEFAULT -1,
                    max_uses INTEGER DEFAULT -1,
                    used_count INTEGER DEFAULT 0,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_by BIGINT,
                    created_at TEXT
                )""",
                
                # Вводы промокодов
                """CREATE TABLE IF NOT EXISTS promo_entries (
                    id SERIAL PRIMARY KEY,
                    promo_id INTEGER,
                    user_id BIGINT,
                    entered_at TEXT,
                    used INTEGER DEFAULT 0,
                    used_at TEXT,
                    transaction_id INTEGER,
                    FOREIGN KEY (promo_id) REFERENCES promo_codes(id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )""",
                
                # Индексы
                "CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_invoice ON transactions(invoice_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id)",
                "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_history_user ON purchase_history(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code)",
                "CREATE INDEX IF NOT EXISTS idx_promo_entries_user ON promo_entries(user_id)",
            ]
        else:
            # SQLite синтаксис
            queries = [
                # Пользователи
                """CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    referrer_id INTEGER,
                    balance REAL DEFAULT 0,
                    language TEXT DEFAULT 'ru',
                    registered_date TEXT,
                    last_active TEXT,
                    is_blocked INTEGER DEFAULT 0,
                    notify_enabled INTEGER DEFAULT 1,
                    admin_note TEXT
                )""",
                
                # Транзакции
                """CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT CHECK(type IN ('deposit', 'purchase', 'withdraw', 'referral', 'admin_deposit')),
                    product_id INTEGER,
                    status TEXT CHECK(status IN ('pending', 'completed', 'failed', 'cancelled', 'expired')),
                    invoice_id TEXT,
                    currency TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    promo_code TEXT,
                    discount_amount REAL DEFAULT 0
                )""",
                
                # Рефералы
                """CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referral_id INTEGER,
                    bonus REAL DEFAULT 0,
                    created_at TEXT,
                    purchase_count INTEGER DEFAULT 0,
                    total_earned REAL DEFAULT 0,
                    UNIQUE(referrer_id, referral_id)
                )""",
                
                # Товары
                """CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price_usd REAL NOT NULL,
                    description TEXT,
                    stock INTEGER DEFAULT -1,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    photo_url TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    sold_count INTEGER DEFAULT 0
                )""",
                
                # Ожидающие действия
                """CREATE TABLE IF NOT EXISTS pending_actions (
                    user_id INTEGER PRIMARY KEY,
                    action TEXT,
                    data TEXT,
                    created_at TEXT
                )""",
                
                # Настройки
                """CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )""",
                
                # История покупок
                """CREATE TABLE IF NOT EXISTS purchase_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    product_name TEXT,
                    amount REAL,
                    status TEXT DEFAULT 'completed',
                    purchase_date TEXT,
                    completed_date TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )""",
                
                # Промокоды
                """CREATE TABLE IF NOT EXISTS promo_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE,
                    bonus_type TEXT DEFAULT 'discount',
                    bonus_value REAL,
                    target_type TEXT DEFAULT 'all',
                    target_id INTEGER DEFAULT 0,
                    max_entries INTEGER DEFAULT -1,
                    max_uses INTEGER DEFAULT -1,
                    used_count INTEGER DEFAULT 0,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_by INTEGER,
                    created_at TEXT
                )""",
                
                # Вводы промокодов
                """CREATE TABLE IF NOT EXISTS promo_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promo_id INTEGER,
                    user_id INTEGER,
                    entered_at TEXT,
                    used INTEGER DEFAULT 0,
                    used_at TEXT,
                    transaction_id INTEGER,
                    FOREIGN KEY (promo_id) REFERENCES promo_codes(id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )""",
                
                # Индексы
                "CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_invoice ON transactions(invoice_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id)",
                "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
                "CREATE INDEX IF NOT EXISTS idx_purchase_history_user ON purchase_history(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code)",
                "CREATE INDEX IF NOT EXISTS idx_promo_entries_user ON promo_entries(user_id)",
            ]
        
        for query in queries:
            try:
                self.execute(query, commit=True)
            except Exception as e:
                logger.error(f"Error creating table: {e}")
    
    def seed_products(self):
        """Заполнение тестовыми товарами"""
        examples = [
            ('grailed_accounts', 'Aged Grailed 2022–2023 (4.7+)', 95.0, 
             '✅ Возраст 3+ года\n✅ Рейтинг 4.7+\n✅ Есть отзывы', -1, 10),
            ('grailed_accounts', 'Fresh clean Grailed', 38.0, 
             '✅ Новый аккаунт\n✅ Без истории\n✅ Нет банов', -1, 20),
            ('paypal', 'PayPal aged 2021 с историей', 145.0, 
             '✅ Лимит 4–8k\n✅ Есть платежи\n✅ Готов к работе', 6, 30),
            ('call_service', 'Soft USA прозвон', 55.0, 
             '✅ Мягкий прозвон\n✅ ~80% успеха\n✅ Быстро', -1, 50),
            ('grailed_likes', '500 качественных лайков', 22.0, 
             '✅ Плавная подача\n✅ 2–5 дней\n✅ Реальные профили', -1, 70),
            ('ebay', 'eBay 2019+ с отзывами 120+', 115.0, 
             '✅ Лимит 12k+\n✅ 120+ отзывов\n✅ Положительные', 5, 90),
        ]
        
        for cat, name, price, desc, stock, order in examples:
            existing = self.execute(
                "SELECT id FROM products WHERE name = ?", 
                (name,), 
                fetch=True
            )
            
            if not existing:
                now = datetime.now().isoformat()
                self.execute(
                    """INSERT INTO products 
                       (category, name, price_usd, description, stock, sort_order, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cat, name, price, desc, stock, order, now, now),
                    commit=True
                )
    
    # === КЭШИРОВАНИЕ ===
    @lru_cache(maxsize=128)
    def get_product_cached(self, product_id: int) -> Optional[dict]:
        """Получить товар с кэшированием"""
        result = self.execute(
            "SELECT * FROM products WHERE id = ?", 
            (product_id,), 
            fetch=True
        )
        if result:
            return dict(result[0])
        return None
    
    def invalidate_product_cache(self, product_id: int):
        """Инвалидация кэша товара"""
        self.get_product_cached.cache_clear()
    
    # === ПОЛЬЗОВАТЕЛИ ===
    def get_user(self, user_id: int) -> Optional[dict]:
        """Получить пользователя"""
        result = self.execute(
            "SELECT * FROM users WHERE user_id = ?", 
            (user_id,), 
            fetch=True
        )
        if result:
            return dict(result[0])
        return None
    
    def register_user(self, user_id: int, username: str, first_name: str, 
                     referrer_id: Optional[int] = None) -> bool:
        """Регистрация пользователя"""
        if self.get_user(user_id):
            return False
        
        now = datetime.now().isoformat()
        
        try:
            # Начинаем транзакцию
            self.execute("BEGIN TRANSACTION", commit=False)
            
            # Добавляем пользователя
            self.execute(
                """INSERT INTO users 
                   (user_id, username, first_name, referrer_id, registered_date, last_active) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, referrer_id, now, now),
                commit=False
            )
            
            # Если есть реферер, добавляем запись о реферале
            if referrer_id and referrer_id != user_id:
                self.execute(
                    """INSERT INTO referrals 
                       (referrer_id, referral_id, created_at) 
                       VALUES (?, ?, ?)
                       ON CONFLICT (referrer_id, referral_id) DO NOTHING""",
                    (referrer_id, user_id, now),
                    commit=False
                )
            
            self.conn.commit()
            logger.info(f"New user registered: {user_id}")
            return True
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to register user {user_id}: {e}")
            return False
    
    def update_activity(self, user_id: int):
        """Обновить время активности"""
        self.execute(
            "UPDATE users SET last_active = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
            commit=True
        )
    
    # === БАЛАНС ===
    def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        result = self.execute(
            "SELECT balance FROM users WHERE user_id = ?", 
            (user_id,), 
            fetch=True
        )
        if result:
            if self.use_postgres:
                return result[0]['balance']
            else:
                return result[0][0]
        return 0.0
    
    def add_balance(self, user_id: int, amount: float) -> bool:
        """Добавить баланс"""
        try:
            self.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add balance for {user_id}: {e}")
            return False
    
    # === ТОВАРЫ ===
    def get_products(self, category: Optional[str] = None, 
                    show_all: bool = False) -> List[dict]:
        """Получить список товаров"""
        if category:
            if show_all:
                query = """SELECT * FROM products 
                          WHERE category = ? 
                          ORDER BY sort_order, name"""
            else:
                query = """SELECT * FROM products 
                          WHERE category = ? AND is_active = 1 
                          ORDER BY sort_order, name"""
            results = self.execute(query, (category,), fetch=True)
        else:
            if show_all:
                query = "SELECT * FROM products ORDER BY category, sort_order, name"
            else:
                query = "SELECT * FROM products WHERE is_active = 1 ORDER BY category, sort_order, name"
            results = self.execute(query, fetch=True)
        
        return [dict(row) for row in results] if results else []
    
    def get_product(self, product_id: int) -> Optional[dict]:
        """Получить товар по ID"""
        return self.get_product_cached(product_id)
    
    def add_product(self, category: str, name: str, price: float, 
                   description: Optional[str] = None, stock: int = -1, 
                   sort_order: int = 0, photo_url: Optional[str] = None) -> bool:
        """Добавить новый товар"""
        now = datetime.now().isoformat()
        try:
            self.execute(
                """INSERT INTO products 
                   (category, name, price_usd, description, stock, sort_order, photo_url, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (category, name, price, description, stock, sort_order, photo_url, now, now),
                commit=True
            )
            self.invalidate_product_cache(-1)  # Инвалидируем кэш
            logger.info(f"Product added: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            return False
    
    def update_product(self, product_id: int, **kwargs) -> bool:
        """Обновить товар"""
        allowed = ['category', 'name', 'price_usd', 'description', 
                  'stock', 'sort_order', 'is_active', 'photo_url']
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(product_id)
        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        
        query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
        
        try:
            self.execute(query, tuple(values), commit=True)
            self.invalidate_product_cache(product_id)
            logger.info(f"Product {product_id} updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            return False
    
    def delete_product(self, product_id: int) -> bool:
        """Удалить товар"""
        try:
            self.execute("DELETE FROM products WHERE id = ?", (product_id,), commit=True)
            self.invalidate_product_cache(product_id)
            logger.info(f"Product {product_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
            return False
    
    # === ПОКУПКИ ===
    def purchase(self, user_id: int, product_id: int) -> Tuple[bool, str, Optional[dict]]:
        """Безопасная покупка с транзакцией"""
        try:
            self.execute("BEGIN TRANSACTION")
            
            # Получаем товар
            product = self.execute(
                "SELECT * FROM products WHERE id = ?", 
                (product_id,), 
                fetch=True
            )
            
            if not product:
                raise Exception("Товар не найден")
            
            product = dict(product[0])
            price = product['price_usd']
            stock = product['stock']
            
            # Проверяем баланс
            user = self.execute(
                "SELECT balance FROM users WHERE user_id = ?", 
                (user_id,), 
                fetch=True
            )
            
            if not user:
                raise Exception("❌ Недостаточно средств")
            
            user_balance = user[0][0] if not self.use_postgres else user[0]['balance']
            if user_balance < price:
                raise Exception("❌ Недостаточно средств")
            
            # Проверяем наличие
            if stock == 0:
                raise Exception("❌ Товар закончился")
            
            # Списываем баланс
            self.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (price, user_id),
                commit=False
            )
            
            # Уменьшаем запас и увеличиваем счетчик продаж
            if stock > 0:
                self.execute(
                    "UPDATE products SET stock = stock - 1, sold_count = sold_count + 1 WHERE id = ?",
                    (product_id,),
                    commit=False
                )
            else:
                self.execute(
                    "UPDATE products SET sold_count = sold_count + 1 WHERE id = ?",
                    (product_id,),
                    commit=False
                )
            
            # Записываем транзакцию
            now = datetime.now().isoformat()
            self.execute(
                """INSERT INTO transactions 
                   (user_id, amount, type, product_id, status, completed_at, currency) 
                   VALUES (?, ?, 'purchase', ?, 'completed', ?, 'USD')""",
                (user_id, price, product_id, now),
                commit=False
            )
            
            # Добавляем в историю покупок
            self.add_purchase_history(user_id, product_id, product['name'], price)
            
            # Реферальный бонус
            referrer = self.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?", 
                (user_id,), 
                fetch=True
            )
            
            if referrer and referrer[0]:
                if self.use_postgres:
                    referrer_id = referrer[0]['referrer_id']
                else:
                    referrer_id = referrer[0][0]
                    
                if referrer_id:
                    bonus = price * REFERRAL_BONUS
                    
                    # Начисляем бонус
                    self.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (bonus, referrer_id),
                        commit=False
                    )
                    
                    # Обновляем статистику рефералов
                    self.execute(
                        """UPDATE referrals 
                           SET bonus = bonus + ?, purchase_count = purchase_count + 1, 
                               total_earned = total_earned + ? 
                           WHERE referrer_id = ? AND referral_id = ?""",
                        (bonus, bonus, referrer_id, user_id),
                        commit=False
                    )
                    
                    # Записываем реферальную транзакцию
                    self.execute(
                        """INSERT INTO transactions 
                           (user_id, amount, type, status, completed_at, currency, metadata) 
                           VALUES (?, ?, 'referral', 'completed', ?, 'USD', ?)""",
                        (referrer_id, bonus, now, json.dumps({'referral_id': user_id})),
                        commit=False
                    )
            
            self.conn.commit()
            self.invalidate_product_cache(product_id)
            
            logger.info(f"Purchase successful: user {user_id}, product {product_id}")
            return True, "✅ Покупка успешно оформлена!", product
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Purchase failed: {e}")
            return False, str(e), None
    
    # === ИСТОРИЯ ПОКУПОК ===
    def add_purchase_history(self, user_id, product_id, product_name, amount):
        """Добавить запись в историю покупок"""
        now = datetime.now().isoformat()
        self.execute(
            """INSERT INTO purchase_history 
               (user_id, product_id, product_name, amount, purchase_date, completed_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, product_id, product_name, amount, now, now),
            commit=True
        )

    def get_purchase_history(self, user_id, limit=10):
        """Получить историю покупок пользователя"""
        results = self.execute(
            """SELECT * FROM purchase_history 
               WHERE user_id = ? 
               ORDER BY purchase_date DESC 
               LIMIT ?""",
            (user_id, limit),
            fetch=True
        )
        return [dict(row) for row in results] if results else []

    def get_all_purchases(self, limit=50):
        """Получить все покупки (для админа)"""
        results = self.execute(
            """SELECT ph.*, u.username, u.first_name 
               FROM purchase_history ph
               JOIN users u ON ph.user_id = u.user_id
               ORDER BY ph.purchase_date DESC 
               LIMIT ?""",
            (limit,),
            fetch=True
        )
        return [dict(row) for row in results] if results else []

    # === РАСШИРЕННЫЕ ПРОМОКОДЫ ===
    def create_advanced_promo(self, code, bonus_type, bonus_value, target_type='all', 
                             target_id=0, max_entries=-1, max_uses=-1, 
                             expires_at=None, created_by=None):
        """Создать расширенный промокод"""
        now = datetime.now().isoformat()
        try:
            self.execute(
                """INSERT INTO promo_codes 
                   (code, bonus_type, bonus_value, target_type, target_id, 
                    max_entries, max_uses, expires_at, created_by, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code.upper(), bonus_type, bonus_value, target_type, target_id,
                 max_entries, max_uses, expires_at, created_by, now),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create promo code: {e}")
            return False

    # === ГЕНЕРАЦИЯ ПРОМОКОДОВ ===
    def generate_random_code(self, length=8):
        """Генерирует случайный код в формате XXXXXXXX-XXXXXXXX"""
        import random
        import string
        
        # Только заглавные буквы и цифры
        chars = string.ascii_uppercase + string.digits
        
        # Первая часть
        part1 = ''.join(random.choices(chars, k=length))
        # Вторая часть
        part2 = ''.join(random.choices(chars, k=length))
        
        # Соединяем с дефисом
        return f"{part1}-{part2}"

    def validate_advanced_promo(self, code, user_id):
        """Проверить расширенный промокод"""
        promo = self.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
            (code,),
            fetch=True
        )
        
        if not promo:
            return False, "Промокод не найден"
        
        promo = dict(promo[0])
        
        # Проверка срока действия
        if promo['expires_at']:
            if datetime.now().isoformat() > promo['expires_at']:
                return False, "Срок действия промокода истек"
        
        # Проверка лимита вводов
        entries_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ?",
            (promo['id'],),
            fetch=True
        )
        entries = entries_result[0]['count'] if self.use_postgres else entries_result[0][0]
        
        if promo['max_entries'] > 0 and entries >= promo['max_entries']:
            return False, "Лимит вводов промокода исчерпан"
        
        # Проверка, не вводил ли пользователь уже
        user_entry = self.execute(
            "SELECT id FROM promo_entries WHERE promo_id = ? AND user_id = ?",
            (promo['id'], user_id),
            fetch=True
        )
        
        if user_entry:
            return False, "Вы уже активировали этот промокод"
        
        return True, promo

    def record_promo_entry(self, promo_id, user_id):
        """Записать ввод промокода пользователем"""
        now = datetime.now().isoformat()
        self.execute(
            "INSERT INTO promo_entries (promo_id, user_id, entered_at) VALUES (?, ?, ?)",
            (promo_id, user_id, now),
            commit=True
        )

    def use_promo_entry(self, promo_id, user_id, transaction_id):
        """Отметить использование промокода"""
        self.execute(
            """UPDATE promo_entries 
               SET used = 1, used_at = ?, transaction_id = ? 
               WHERE promo_id = ? AND user_id = ?""",
            (datetime.now().isoformat(), transaction_id, promo_id, user_id),
            commit=True
        )

    def get_promo_stats(self, promo_id):
        """Получить статистику промокода"""
        stats = {}
        
        # Общее количество вводов
        entries_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ?",
            (promo_id,),
            fetch=True
        )
        stats['total_entries'] = entries_result[0]['count'] if self.use_postgres else entries_result[0][0]
        
        # Количество использованных
        used_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ? AND used = 1",
            (promo_id,),
            fetch=True
        )
        stats['used'] = used_result[0]['count'] if self.use_postgres else used_result[0][0]
        
        # Список пользователей
        users = self.execute(
            """SELECT pe.*, u.username, u.first_name 
               FROM promo_entries pe
               JOIN users u ON pe.user_id = u.user_id
               WHERE pe.promo_id = ?
               ORDER BY pe.entered_at DESC""",
            (promo_id,),
            fetch=True
        )
        
        stats['users'] = [dict(row) for row in users] if users else []
        
        return stats
    
    # === ПРОМОКОДЫ (СТАРЫЕ, ДЛЯ СОВМЕСТИМОСТИ) ===
    def create_promo_code(self, code, discount_type, discount_value, min_amount=0, 
                          max_uses=-1, expires_at=None, created_by=None):
        """Создать новый промокод (старая версия)"""
        return self.create_advanced_promo(
            code=code,
            bonus_type=discount_type,
            bonus_value=discount_value,
            target_type='all',
            target_id=0,
            max_entries=max_uses,
            max_uses=max_uses,
            expires_at=expires_at,
            created_by=created_by
        )

    def get_promo_code(self, code):
        """Получить информацию о промокоде"""
        result = self.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
            (code.upper(),),
            fetch=True
        )
        return dict(result[0]) if result else None

    def validate_promo_code(self, code, user_id, amount):
        """Проверить валидность промокода (старая версия)"""
        valid, result = self.validate_advanced_promo(code, user_id)
        if not valid:
            return False, result
        
        promo = result
        if amount < promo.get('min_amount', 0):
            return False, f"Минимальная сумма заказа: ${promo.get('min_amount', 0)}"
        
        return True, promo

    def apply_promo_code(self, code, user_id, amount):
        """Применить промокод к сумме"""
        valid, result = self.validate_promo_code(code, user_id, amount)
        if not valid:
            return False, result, amount
        
        promo = result
        
        # Рассчитываем скидку
        discount = 0
        if promo['bonus_type'] in ['percent', 'discount']:
            discount = amount * (promo['bonus_value'] / 100)
        else:  # fixed или balance
            discount = min(promo['bonus_value'], amount)
        
        final_amount = amount - discount
        
        return True, "Промокод применен", {
            'original': amount,
            'discount': discount,
            'final': final_amount,
            'promo_id': promo['id']
        }

    def use_promo_code(self, promo_id, user_id, transaction_id):
        """Отметить использование промокода"""
        return self.use_promo_entry(promo_id, user_id, transaction_id)

    def get_all_promo_codes(self):
        """Получить все промокоды (для админа)"""
        results = self.execute(
            "SELECT * FROM promo_codes ORDER BY created_at DESC",
            fetch=True
        )
        return [dict(row) for row in results] if results else []

    def deactivate_promo_code(self, promo_id):
        """Деактивировать промокод"""
        self.execute(
            "UPDATE promo_codes SET is_active = 0 WHERE id = ?",
            (promo_id,),
            commit=True
        )

    # === НАКРУТКА БАЛАНСА (АДМИНКА) ===
    def admin_add_balance(self, user_id, amount, reason=""):
        """Админская накрутка баланса"""
        now = datetime.now().isoformat()
        self.execute("BEGIN TRANSACTION")
        try:
            # Начисляем баланс
            self.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
                commit=False
            )
            
            # Записываем транзакцию
            self.execute(
                """INSERT INTO transactions 
                   (user_id, amount, type, status, completed_at, currency, metadata) 
                   VALUES (?, ?, 'admin_deposit', 'completed', ?, 'USD', ?)""",
                (user_id, amount, now, json.dumps({'reason': reason})),
                commit=False
            )
            
            self.conn.commit()
            logger.info(f"Admin added ${amount} to user {user_id}. Reason: {reason}")
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to add balance: {e}")
            return False

    def search_users(self, query):
        """Поиск пользователей по ID или username"""
        if self.use_postgres:
            results = self.execute(
                """SELECT user_id, username, first_name, balance 
                   FROM users 
                   WHERE user_id::text LIKE ? OR username LIKE ? OR first_name LIKE ?
                   LIMIT 20""",
                (f'%{query}%', f'%{query}%', f'%{query}%'),
                fetch=True
            )
        else:
            results = self.execute(
                """SELECT user_id, username, first_name, balance 
                   FROM users 
                   WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ?
                   LIMIT 20""",
                (f'%{query}%', f'%{query}%', f'%{query}%'),
                fetch=True
            )
        return [dict(row) for row in results] if results else []
    
    # === ТРАНЗАКЦИИ ===
    def add_transaction(self, user_id: int, amount: float, type_: str, 
                       status: str, invoice_id: Optional[str] = None,
                       currency: Optional[str] = None, 
                       metadata: Optional[dict] = None) -> bool:
        """Добавить транзакцию"""
        now = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            self.execute(
                """INSERT INTO transactions 
                   (user_id, amount, type, status, invoice_id, currency, metadata, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, amount, type_, status, invoice_id, currency, metadata_json, now),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add transaction: {e}")
            return False
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[dict]:
        """Получить транзакции пользователя"""
        results = self.execute(
            """SELECT * FROM transactions 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit),
            fetch=True
        )
        return [dict(row) for row in results] if results else []
    
    # === СТАТИСТИКА ===
    def get_stats(self) -> dict:
        """Получить общую статистику"""
        stats = {}
        
        # Пользователи
        users = self.execute(
            "SELECT COUNT(*) as count, SUM(balance) as total FROM users", 
            fetch=True
        )[0]
        if self.use_postgres:
            stats['total_users'] = users['count']
            stats['total_balance'] = users['total'] or 0
        else:
            stats['total_users'] = users[0]
            stats['total_balance'] = users[1] or 0
        
        # Пользователи сегодня
        today = datetime.now().date().isoformat()
        users_today_result = self.execute(
            "SELECT COUNT(*) as count FROM users WHERE DATE(registered_date) = ?",
            (today,),
            fetch=True
        )[0]
        if self.use_postgres:
            stats['users_today'] = users_today_result['count'] or 0
        else:
            stats['users_today'] = users_today_result[0] or 0
        
        # Продажи
        sales = self.execute(
            "SELECT COUNT(*) as count, SUM(amount) as total FROM transactions WHERE type = 'purchase' AND status = 'completed'",
            fetch=True
        )[0]
        if self.use_postgres:
            stats['total_sales'] = sales['count'] or 0
            stats['total_revenue'] = sales['total'] or 0
        else:
            stats['total_sales'] = sales[0] or 0
            stats['total_revenue'] = sales[1] or 0
        
        # Продажи сегодня
        sales_today = self.execute(
            "SELECT COUNT(*) as count, SUM(amount) as total FROM transactions WHERE type = 'purchase' AND status = 'completed' AND DATE(completed_at) = ?",
            (today,),
            fetch=True
        )[0]
        if self.use_postgres:
            stats['sales_today'] = sales_today['count'] or 0
            stats['revenue_today'] = sales_today['total'] or 0
        else:
            stats['sales_today'] = sales_today[0] or 0
            stats['revenue_today'] = sales_today[1] or 0
        
        # Товары
        products = self.execute(
            "SELECT COUNT(*) as count FROM products WHERE is_active = 1",
            fetch=True
        )[0]
        if self.use_postgres:
            stats['active_products'] = products['count'] or 0
        else:
            stats['active_products'] = products[0] or 0
        
        return stats
    
    # === ОЖИДАЮЩИЕ ДЕЙСТВИЯ ===
    def set_pending_action(self, user_id: int, action: str, data: Optional[str] = None):
        """Установить ожидающее действие"""
        now = datetime.now().isoformat()
        if self.use_postgres:
            self.execute(
                """INSERT INTO pending_actions (user_id, action, data, created_at) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (user_id) DO UPDATE SET action = ?, data = ?, created_at = ?""",
                (user_id, action, data, now, action, data, now),
                commit=True
            )
        else:
            self.execute(
                "REPLACE INTO pending_actions (user_id, action, data, created_at) VALUES (?, ?, ?, ?)",
                (user_id, action, data, now),
                commit=True
            )
    
    def get_pending_action(self, user_id: int) -> Optional[Tuple[str, Optional[str]]]:
        """Получить ожидающее действие"""
        result = self.execute(
            "SELECT action, data FROM pending_actions WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        if result:
            if self.use_postgres:
                return (result[0]['action'], result[0]['data'])
            else:
                return (result[0][0], result[0][1])
        return None
    
    def clear_pending_action(self, user_id: int):
        """Очистить ожидающее действие"""
        self.execute(
            "DELETE FROM pending_actions WHERE user_id = ?",
            (user_id,),
            commit=True
        )
    
    # === ЭКСПОРТ ===
    def export_users(self) -> List[tuple]:
        """Экспорт пользователей для CSV"""
        return self.execute(
            "SELECT user_id, username, balance, registered_date, last_active FROM users",
            fetch=True
        ) or []
    
    def export_sales(self, days: int = 30) -> List[tuple]:
        """Экспорт продаж за период"""
        from datetime import timedelta
        date_from = (datetime.now() - timedelta(days=days)).isoformat()
        
        return self.execute(
            """SELECT t.completed_at, u.user_id, u.username, p.name, t.amount 
               FROM transactions t
               JOIN users u ON t.user_id = u.user_id
               JOIN products p ON t.product_id = p.id
               WHERE t.type = 'purchase' AND t.status = 'completed' 
                 AND t.completed_at > ?
               ORDER BY t.completed_at DESC""",
            (date_from,),
            fetch=True
        ) or []
    
    def close(self):
        """Закрыть соединение с БД"""
        self.conn.close()


# Создаем глобальный экземпляр
db = Database()