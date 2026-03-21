import sqlite3
import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Optional, List, Dict, Any, Tuple
import random
import string

from config import DB_FILE, REFERRAL_BONUS
from utils.translator import build_i18n_triplet

logger = logging.getLogger(__name__)

DEFAULT_ROOT_CATEGORIES = {
    'grailed': {'ru': '📂 Grailed', 'uk': '📂 Grailed', 'en': '📂 Grailed'},
    'support': None,  # filled from DEFAULT_CATEGORIES at runtime (see seed_default_categories)
}

DEFAULT_CATEGORIES = {
    'grailed_accounts': {'ru': "📱 Grailed account's", 'uk': "📱 Grailed account's", 'en': "📱 Grailed account's"},
    'paypal': {'ru': "💳 PayPal", 'uk': "💳 PayPal", 'en': "💳 PayPal"},
    'call_service': {'ru': "📞 Прозвон сервис", 'uk': "📞 Прозвон сервіс", 'en': "📞 Call service"},
    'grailed_likes': {'ru': "❤️ Накрутка лайков на Grailed", 'uk': "❤️ Накрутка лайків на Grailed", 'en': "❤️ Grailed likes"},
    'ebay': {'ru': "🏷 eBay", 'uk': "🏷 eBay", 'en': "🏷 eBay"},
    'support': {'ru': "🆘 Тех поддержка", 'uk': "🆘 Тех підтримка", 'en': "🆘 Support"},
}

class Database:
    _bootstrapped = False
    """Класс для работы с базой данных (поддерживает SQLite и PostgreSQL)"""
    
    def __init__(self):
        self.use_postgres = 'DATABASE_URL' in os.environ
        
        if self.use_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
            self.conn.autocommit = False
            logger.info("Connected to PostgreSQL database")
        else:
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database: {DB_FILE}")
        
        if not Database._bootstrapped:
            self.init_tables()
            self.ensure_schema_compat()
            self.seed_default_categories()
            self.seed_products()
            Database._bootstrapped = True
    
    def execute(self, query: str, params: tuple = (), 
                fetch: bool = False, commit: bool = False) -> Optional[List[Any]]:
        try:
            c = self.conn.cursor()
            
            if self.use_postgres:
                query = query.replace('?', '%s')
                
            c.execute(query, params)
            
            if commit:
                self.conn.commit()
            
            if fetch:
                return c.fetchall()
            return None
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            
            if self.use_postgres:
                try:
                    self.conn.rollback()
                except:
                    pass
            
            if commit:
                self.conn.rollback()
            raise
    
    def init_tables(self):
        if self.use_postgres:
            queries = [
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
                """CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    amount REAL,
                    type TEXT,
                    product_id INTEGER,
                    status TEXT,
                    invoice_id TEXT,
                    currency TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    promo_code TEXT,
                    discount_amount REAL DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS balance_transfers (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT,
                    recipient_id BIGINT,
                    amount REAL,
                    created_at TEXT,
                    metadata TEXT
                )""",
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
                """CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    name_ru TEXT,
                    name_uk TEXT,
                    name_en TEXT,
                    price_usd REAL NOT NULL,
                    description TEXT,
                    description_ru TEXT,
                    description_uk TEXT,
                    description_en TEXT,
                    stock INTEGER DEFAULT -1,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    photo_url TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    sold_count INTEGER DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS pending_actions (
                    user_id BIGINT PRIMARY KEY,
                    action TEXT,
                    data TEXT,
                    created_at TEXT
                )""",
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
                """CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    cat_id TEXT UNIQUE NOT NULL,
                    name_ru TEXT NOT NULL,
                    name_uk TEXT,
                    name_en TEXT,
                    photo_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS subcategories (
                    id SERIAL PRIMARY KEY,
                    subcat_id TEXT UNIQUE NOT NULL,
                    parent_cat_id TEXT NOT NULL,
                    name_ru TEXT NOT NULL,
                    name_uk TEXT,
                    name_en TEXT,
                    photo_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS broadcast_drafts (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    text TEXT,
                    photo_file_id TEXT,
                    created_by BIGINT,
                    created_at TEXT,
                    updated_at TEXT
                )""",
            ]
        else:
            queries = [
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
                """CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT,
                    product_id INTEGER,
                    status TEXT,
                    invoice_id TEXT,
                    currency TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    promo_code TEXT,
                    discount_amount REAL DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS balance_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    recipient_id INTEGER,
                    amount REAL,
                    created_at TEXT,
                    metadata TEXT
                )""",
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
                """CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    name_ru TEXT,
                    name_uk TEXT,
                    name_en TEXT,
                    price_usd REAL NOT NULL,
                    description TEXT,
                    description_ru TEXT,
                    description_uk TEXT,
                    description_en TEXT,
                    stock INTEGER DEFAULT -1,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    photo_url TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    sold_count INTEGER DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS pending_actions (
                    user_id INTEGER PRIMARY KEY,
                    action TEXT,
                    data TEXT,
                    created_at TEXT
                )""",
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
                """CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cat_id TEXT UNIQUE NOT NULL,
                    name_ru TEXT NOT NULL,
                    name_uk TEXT,
                    name_en TEXT,
                    photo_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS subcategories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subcat_id TEXT UNIQUE NOT NULL,
                    parent_cat_id TEXT NOT NULL,
                    name_ru TEXT NOT NULL,
                    name_uk TEXT,
                    name_en TEXT,
                    photo_url TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS broadcast_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    text TEXT,
                    photo_file_id TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                )""",
            ]
        
        for query in queries:
            try:
                self.execute(query, commit=True)
            except Exception as e:
                logger.error(f"Error creating table: {e}")

    def ensure_schema_compat(self):
        """Лёгкие миграции для уже существующих БД."""
        try:
            if self.use_postgres:
                self.execute(
                    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS name_ru TEXT",
                    commit=True
                )
                self.execute(
                    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS name_uk TEXT",
                    commit=True
                )
                self.execute(
                    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS name_en TEXT",
                    commit=True
                )
                self.execute(
                    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS photo_url TEXT",
                    commit=True
                )
                try:
                    self.execute(
                        """UPDATE categories
                           SET name_ru = COALESCE(name_ru, name),
                               name_uk = COALESCE(name_uk, name),
                               name_en = COALESCE(name_en, name)
                           WHERE name IS NOT NULL""",
                        commit=True
                    )
                except Exception:
                    pass
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS name_ru TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS name_uk TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS name_en TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS description_ru TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS description_uk TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS description_en TEXT", commit=True)
                self.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS subcategory TEXT", commit=True)
                self.execute(
                    """CREATE TABLE IF NOT EXISTS subcategories (
                        id SERIAL PRIMARY KEY,
                        subcat_id TEXT UNIQUE NOT NULL,
                        parent_cat_id TEXT NOT NULL,
                        name_ru TEXT NOT NULL,
                        name_uk TEXT,
                        name_en TEXT,
                        photo_url TEXT,
                        sort_order INTEGER DEFAULT 0,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    commit=True
                )
            else:
                cols = self.execute("PRAGMA table_info(categories)", fetch=True) or []
                col_names = {row[1] for row in cols}
                if 'name_ru' not in col_names:
                    self.execute("ALTER TABLE categories ADD COLUMN name_ru TEXT", commit=True)
                if 'name_uk' not in col_names:
                    self.execute("ALTER TABLE categories ADD COLUMN name_uk TEXT", commit=True)
                if 'name_en' not in col_names:
                    self.execute("ALTER TABLE categories ADD COLUMN name_en TEXT", commit=True)
                if 'photo_url' not in col_names:
                    self.execute("ALTER TABLE categories ADD COLUMN photo_url TEXT", commit=True)
                if 'name' in col_names:
                    self.execute(
                        """UPDATE categories
                           SET name_ru = COALESCE(name_ru, name),
                               name_uk = COALESCE(name_uk, name),
                               name_en = COALESCE(name_en, name)
                           WHERE name IS NOT NULL""",
                        commit=True
                    )

                prod_cols = self.execute("PRAGMA table_info(products)", fetch=True) or []
                prod_col_names = {row[1] for row in prod_cols}
                missing = [
                    ("name_ru", "TEXT"),
                    ("name_uk", "TEXT"),
                    ("name_en", "TEXT"),
                    ("description_ru", "TEXT"),
                    ("description_uk", "TEXT"),
                    ("description_en", "TEXT"),
                    ("subcategory", "TEXT"),
                ]
                for col_name, col_type in missing:
                    if col_name not in prod_col_names:
                        self.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}", commit=True)

                self.execute(
                    """CREATE TABLE IF NOT EXISTS subcategories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subcat_id TEXT UNIQUE NOT NULL,
                        parent_cat_id TEXT NOT NULL,
                        name_ru TEXT NOT NULL,
                        name_uk TEXT,
                        name_en TEXT,
                        photo_url TEXT,
                        sort_order INTEGER DEFAULT 0,
                        created_at TEXT,
                        updated_at TEXT
                    )""",
                    commit=True
                )

            self._bootstrap_default_hierarchy_if_needed()
        except Exception as e:
            logger.warning(f"Schema compatibility migration skipped: {e}")

    def _bootstrap_default_hierarchy_if_needed(self):
        """One-time bootstrap: group legacy flat categories under 'grailed' and migrate products."""
        try:
            if self.get_setting('category_hierarchy_v1_done') == '1':
                return
        except Exception:
            # If settings table isn't ready, skip.
            return

        try:
            sub_count = self.execute("SELECT COUNT(*) as count FROM subcategories", fetch=True)
            if sub_count:
                cnt = sub_count[0]['count'] if self.use_postgres else sub_count[0][0]
                if cnt and cnt > 0:
                    self.set_setting('category_hierarchy_v1_done', '1')
                    return
        except Exception:
            return

        legacy_subcats = ['grailed_accounts', 'paypal', 'call_service', 'grailed_likes', 'ebay']

        try:
            cats = self.execute(
                "SELECT cat_id, name_ru, name_uk, name_en, sort_order FROM categories",
                fetch=True
            ) or []
            if not cats:
                return

            existing_ids = {row['cat_id'] if self.use_postgres else row[0] for row in cats}
            if not set(legacy_subcats).issubset(existing_ids):
                self.set_setting('category_hierarchy_v1_done', '1')
                return

            now = datetime.now().isoformat()

            # Ensure root categories exist.
            if 'grailed' not in existing_ids:
                self.execute(
                    """INSERT INTO categories
                       (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ('grailed', '📂 Grailed', '📂 Grailed', '📂 Grailed', None, 0, now, now),
                    commit=True
                )

            if 'support' not in existing_ids and 'support' in DEFAULT_CATEGORIES:
                s = DEFAULT_CATEGORIES['support']
                self.execute(
                    """INSERT INTO categories
                       (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    ('support', s.get('ru') or 'Support', s.get('uk'), s.get('en'), None, 999, now, now),
                    commit=True
                )

            for cat_id in legacy_subcats:
                row = next((r for r in cats if (r['cat_id'] if self.use_postgres else r[0]) == cat_id), None)
                if not row:
                    continue
                if self.use_postgres:
                    name_ru = row.get('name_ru')
                    name_uk = row.get('name_uk')
                    name_en = row.get('name_en')
                    sort_order = row.get('sort_order') or 0
                else:
                    name_ru = row[1]
                    name_uk = row[2]
                    name_en = row[3]
                    sort_order = row[4] if len(row) > 4 else 0

                exists = self.execute(
                    "SELECT subcat_id FROM subcategories WHERE subcat_id = ?",
                    (cat_id,),
                    fetch=True
                )
                if not exists:
                    self.execute(
                        """INSERT INTO subcategories
                           (subcat_id, parent_cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (cat_id, 'grailed', name_ru, name_uk, name_en, None, sort_order, now, now),
                        commit=True
                    )

                # Move products: category -> grailed, store old in subcategory.
                self.execute(
                    "UPDATE products SET category = ?, subcategory = ? WHERE category = ?",
                    ('grailed', cat_id, cat_id),
                    commit=True
                )

                # Remove old root category so it doesn't show in the main menu.
                self.execute("DELETE FROM categories WHERE cat_id = ?", (cat_id,), commit=True)

            self.set_setting('category_hierarchy_v1_done', '1')
        except Exception as e:
            logger.warning(f"Could not bootstrap category hierarchy: {e}")

    def seed_default_categories(self):
        """Автозаполнение категорий, если таблица пустая."""
        try:
            result = self.execute("SELECT COUNT(*) as count FROM categories", fetch=True)
            if not result:
                return
            count = result[0]['count'] if self.use_postgres else result[0][0]
            if count > 0:
                return

            now = datetime.now().isoformat()

            # Root categories
            roots = [
                ('grailed', {'ru': '📂 Grailed', 'uk': '📂 Grailed', 'en': '📂 Grailed'}, 0),
                ('support', DEFAULT_CATEGORIES.get('support') or {'ru': '🆘 Support', 'uk': '🆘 Support', 'en': '🆘 Support'}, 999),
            ]
            for cat_id, names, sort_order in roots:
                self.execute(
                    """INSERT INTO categories
                       (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cat_id, names.get('ru'), names.get('uk'), names.get('en'), None, sort_order, now, now),
                    commit=True
                )

            # Default subcategories for Grailed (legacy defaults except support)
            sub_sort = 0
            for subcat_id, names in DEFAULT_CATEGORIES.items():
                if subcat_id == 'support':
                    continue
                self.execute(
                    """INSERT INTO subcategories
                       (subcat_id, parent_cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (subcat_id, 'grailed', names.get('ru'), names.get('uk'), names.get('en'), None, sub_sort, now, now),
                    commit=True
                )
                sub_sort += 10
            logger.info("Default categories seeded")
        except Exception as e:
            logger.warning(f"Could not seed default categories: {e}")
    
    def seed_products(self):
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
                name_i18n = build_i18n_triplet(name, source_lang='ru')
                desc_i18n = build_i18n_triplet(desc, source_lang='ru')
                root_cat = 'support' if cat == 'support' else 'grailed'
                subcat = None if cat == 'support' else cat
                self.execute(
                    """INSERT INTO products 
                       (category, subcategory, name, name_ru, name_uk, name_en, price_usd, description, description_ru, description_uk, description_en, stock, sort_order, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        root_cat, subcat, name, name_i18n['ru'], name_i18n['uk'], name_i18n['en'],
                        price, desc, desc_i18n['ru'], desc_i18n['uk'], desc_i18n['en'],
                        stock, order, now, now
                    ),
                    commit=True
                )

    def backfill_product_i18n(self):
        """Заполнить отсутствующие переводы у старых товаров."""
        try:
            rows = self.execute(
                """SELECT id, name, description, name_ru, name_uk, name_en, description_ru, description_uk, description_en
                   FROM products""",
                fetch=True
            ) or []
            for row in rows:
                r = dict(row) if isinstance(row, dict) else {
                    'id': row[0], 'name': row[1], 'description': row[2],
                    'name_ru': row[3], 'name_uk': row[4], 'name_en': row[5],
                    'description_ru': row[6], 'description_uk': row[7], 'description_en': row[8],
                }
                if r.get('name_ru') and r.get('name_uk') and r.get('name_en') and (r.get('description') is None or (r.get('description_ru') and r.get('description_uk') and r.get('description_en'))):
                    continue

                name_i18n = build_i18n_triplet(r.get('name'), source_lang='ru')
                desc_i18n = build_i18n_triplet(r.get('description'), source_lang='ru') if r.get('description') else {'ru': None, 'uk': None, 'en': None}

                self.execute(
                    """UPDATE products
                       SET name_ru = ?, name_uk = ?, name_en = ?,
                           description_ru = ?, description_uk = ?, description_en = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    (
                        r.get('name_ru') or name_i18n['ru'],
                        r.get('name_uk') or name_i18n['uk'],
                        r.get('name_en') or name_i18n['en'],
                        r.get('description_ru') if r.get('description_ru') is not None else desc_i18n['ru'],
                        r.get('description_uk') if r.get('description_uk') is not None else desc_i18n['uk'],
                        r.get('description_en') if r.get('description_en') is not None else desc_i18n['en'],
                        datetime.now().isoformat(),
                        r['id']
                    ),
                    commit=True
                )
        except Exception as e:
            logger.warning(f"Could not backfill product i18n: {e}")
    
    @lru_cache(maxsize=128)
    def get_product_cached(self, product_id: int) -> Optional[dict]:
        result = self.execute(
            "SELECT * FROM products WHERE id = ?", 
            (product_id,), 
            fetch=True
        )
        if result:
            return dict(result[0])
        return None
    
    def invalidate_product_cache(self, product_id: int):
        self.get_product_cached.cache_clear()
    
    def get_user(self, user_id: int) -> Optional[dict]:
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
        if self.get_user(user_id):
            return False
        
        now = datetime.now().isoformat()
        
        try:
            self.execute("BEGIN TRANSACTION", commit=False)
            
            self.execute(
                """INSERT INTO users 
                   (user_id, username, first_name, referrer_id, registered_date, last_active) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, first_name, referrer_id, now, now),
                commit=False
            )
            
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
        self.execute(
            "UPDATE users SET last_active = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
            commit=True
        )
    
    def get_balance(self, user_id: int) -> float:
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

    def find_user_by_identifier(self, identifier: str) -> Optional[dict]:
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        try:
            if identifier.startswith('@'):
                identifier = identifier[1:]

            if identifier.isdigit():
                result = self.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (int(identifier),),
                    fetch=True
                )
            else:
                result = self.execute(
                    "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
                    (identifier,),
                    fetch=True
                )

            if not result:
                return None
            return dict(result[0])
        except Exception as e:
            logger.error(f"Failed to find user by identifier {identifier}: {e}")
            return None

    def transfer_balance(self, sender_id: int, recipient_identifier: str, amount: float) -> Tuple[bool, str, Optional[dict]]:
        if amount <= 0:
            return False, "Amount must be positive", None

        recipient = self.find_user_by_identifier(recipient_identifier)
        if not recipient:
            return False, "Recipient not found", None

        recipient_id = recipient['user_id']
        if recipient_id == sender_id:
            return False, "Cannot transfer to self", None

        now = datetime.now().isoformat()
        try:
            sender_row = self.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (sender_id,),
                fetch=True
            )
            if not sender_row:
                raise Exception("Sender not found")

            sender_balance = sender_row[0]['balance'] if self.use_postgres else sender_row[0][0]
            if sender_balance < amount:
                raise Exception("Insufficient funds")

            self.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, sender_id),
                commit=False
            )
            self.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, recipient_id),
                commit=False
            )
            self.execute(
                """INSERT INTO balance_transfers
                   (sender_id, recipient_id, amount, created_at, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (sender_id, recipient_id, amount, now, json.dumps({
                    'recipient_username': recipient.get('username'),
                })),
                commit=False
            )

            self.conn.commit()
            return True, "ok", recipient
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to transfer balance from {sender_id}: {e}")
            return False, str(e), None
    
    def get_products(self, category: Optional[str] = None,
                    subcategory: Optional[str] = None,
                    show_all: bool = False, lang: str = 'ru') -> List[dict]:
        if category:
            params: list = [category]
            where = "WHERE category = ?"
            if subcategory is not None:
                where += " AND subcategory = ?"
                params.append(subcategory)

            if show_all:
                query = f"""SELECT * FROM products
                          {where}
                          ORDER BY sort_order, name"""
            else:
                query = f"""SELECT * FROM products
                          {where} AND is_active = 1
                          ORDER BY sort_order, name"""
            results = self.execute(query, tuple(params), fetch=True)
        else:
            if show_all:
                query = "SELECT * FROM products ORDER BY category, sort_order, name"
            else:
                query = "SELECT * FROM products WHERE is_active = 1 ORDER BY category, sort_order, name"
            results = self.execute(query, fetch=True)
        
        products = [dict(row) for row in results] if results else []
        return [self._localize_product_row(p, lang) for p in products]
    
    def get_product(self, product_id: int, lang: str = 'ru') -> Optional[dict]:
        prod = self.get_product_cached(product_id)
        if not prod:
            return None
        return self._localize_product_row(dict(prod), lang)

    def _localize_product_row(self, row: dict, lang: str) -> dict:
        """Return product row with language-specific name/description projected to generic fields."""
        if lang not in {'ru', 'uk', 'en'}:
            lang = 'ru'

        name_key = f'name_{lang}'
        desc_key = f'description_{lang}'

        localized_name = row.get(name_key)
        localized_desc = row.get(desc_key)
        if localized_name:
            row['name'] = localized_name
        if localized_desc is not None and localized_desc != '':
            row['description'] = localized_desc
        return row
    
    def add_product(self, category: str, name: str, price: float,
                   subcategory: Optional[str] = None,
                   description: Optional[str] = None, stock: int = -1, 
                   sort_order: int = 0, photo_url: Optional[str] = None,
                   input_lang: str = 'ru') -> bool:
        now = datetime.now().isoformat()
        try:
            name_i18n = build_i18n_triplet(name, source_lang=input_lang)
            desc_i18n = build_i18n_triplet(description, source_lang=input_lang) if description else {'ru': None, 'uk': None, 'en': None}
            self.execute(
                """INSERT INTO products 
                   (category, subcategory, name, name_ru, name_uk, name_en, price_usd, description, description_ru, description_uk, description_en, stock, sort_order, photo_url, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    category, subcategory, name, name_i18n['ru'], name_i18n['uk'], name_i18n['en'],
                    price, description, desc_i18n['ru'], desc_i18n['uk'], desc_i18n['en'],
                    stock, sort_order, photo_url, now, now
                ),
                commit=True
            )
            self.invalidate_product_cache(-1)
            logger.info(f"Product added: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            return False
    
    def update_product(self, product_id: int, **kwargs) -> bool:
        input_lang = kwargs.pop('input_lang', 'ru')
        allowed = ['category', 'subcategory', 'name', 'price_usd', 'description',
                  'stock', 'sort_order', 'is_active', 'photo_url',
                  'name_ru', 'name_uk', 'name_en', 'description_ru', 'description_uk', 'description_en']

        if 'name' in kwargs:
            name_i18n = build_i18n_triplet(kwargs.get('name'), source_lang=input_lang)
            kwargs['name_ru'] = name_i18n['ru']
            kwargs['name_uk'] = name_i18n['uk']
            kwargs['name_en'] = name_i18n['en']

        if 'description' in kwargs:
            desc_i18n = build_i18n_triplet(kwargs.get('description'), source_lang=input_lang)
            kwargs['description_ru'] = desc_i18n['ru']
            kwargs['description_uk'] = desc_i18n['uk']
            kwargs['description_en'] = desc_i18n['en']
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(product_id)
        
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
        try:
            self.execute("DELETE FROM products WHERE id = ?", (product_id,), commit=True)
            self.invalidate_product_cache(product_id)
            logger.info(f"Product {product_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
            return False
    
    def get_categories(self, lang='ru') -> Dict[str, str]:
        """Получить все категории из БД на нужном языке"""
        try:
            result = self.execute(
                "SELECT cat_id, name_ru, name_uk, name_en FROM categories ORDER BY sort_order, cat_id",
                fetch=True
            )
            
            categories = {}
            if result:
                for row in result:
                    if self.use_postgres:
                        cat_id = row['cat_id']
                        if lang == 'uk' and row['name_uk']:
                            name = row['name_uk']
                        elif lang == 'en' and row['name_en']:
                            name = row['name_en']
                        else:
                            name = row['name_ru']
                    else:
                        cat_id = row[0]
                        if lang == 'uk' and row[2]:
                            name = row[2]
                        elif lang == 'en' and row[3]:
                            name = row[3]
                        else:
                            name = row[1]
                    
                    categories[cat_id] = name
                logger.info(f"Loaded {len(categories)} categories from DB for lang {lang}")
                return categories
            else:
                logger.warning("No categories found in database, using defaults")
                return {cat_id: (names.get(lang) or names['ru']) for cat_id, names in DEFAULT_CATEGORIES.items()}
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return {cat_id: (names.get(lang) or names['ru']) for cat_id, names in DEFAULT_CATEGORIES.items()}

    def get_subcategories(self, parent_cat_id: str, lang: str = 'ru') -> Dict[str, str]:
        """Получить подкатегории для выбранной категории."""
        try:
            result = self.execute(
                """SELECT subcat_id, name_ru, name_uk, name_en
                   FROM subcategories
                   WHERE parent_cat_id = ?
                   ORDER BY sort_order, subcat_id""",
                (parent_cat_id,),
                fetch=True
            )
            subcats: Dict[str, str] = {}
            for row in result or []:
                if self.use_postgres:
                    subcat_id = row['subcat_id']
                    name_ru = row.get('name_ru')
                    name_uk = row.get('name_uk')
                    name_en = row.get('name_en')
                else:
                    subcat_id = row[0]
                    name_ru = row[1]
                    name_uk = row[2]
                    name_en = row[3]

                if lang == 'uk' and name_uk:
                    name = name_uk
                elif lang == 'en' and name_en:
                    name = name_en
                else:
                    name = name_ru

                subcats[subcat_id] = name
            return subcats
        except Exception as e:
            logger.error(f"Error getting subcategories for {parent_cat_id}: {e}")
            return {}

    def get_all_subcategories(self) -> List[dict]:
        try:
            result = self.execute(
                """SELECT subcat_id, parent_cat_id, name_ru, name_uk, name_en, sort_order
                   FROM subcategories
                   ORDER BY parent_cat_id, sort_order, subcat_id""",
                fetch=True
            )
            return [dict(r) for r in result] if result else []
        except Exception as e:
            logger.error(f"Error getting all subcategories: {e}")
            return []

    def get_subcategory(self, subcat_id: str) -> Optional[dict]:
        try:
            result = self.execute(
                """SELECT subcat_id, parent_cat_id, name_ru, name_uk, name_en, photo_url, sort_order
                   FROM subcategories
                   WHERE subcat_id = ?""",
                (subcat_id,),
                fetch=True
            )
            if not result:
                return None
            row = result[0]
            if self.use_postgres:
                return dict(row)
            return {
                'subcat_id': row[0],
                'parent_cat_id': row[1],
                'name_ru': row[2],
                'name_uk': row[3],
                'name_en': row[4],
                'photo_url': row[5] if len(row) > 5 else None,
                'sort_order': row[6] if len(row) > 6 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get subcategory {subcat_id}: {e}")
            return None

    def add_subcategory(
        self,
        subcat_id: str,
        parent_cat_id: str,
        name_ru: str,
        name_uk: str = None,
        name_en: str = None,
        sort_order: int = 0,
        photo_url: str = None,
    ) -> bool:
        now = datetime.now().isoformat()
        try:
            self.execute(
                """INSERT INTO subcategories
                   (subcat_id, parent_cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (subcat_id, parent_cat_id, name_ru, name_uk, name_en, photo_url, sort_order, now, now),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add subcategory {subcat_id}: {e}")
            return False

    def update_subcategory(
        self,
        subcat_id: str,
        parent_cat_id: str = None,
        name_ru: str = None,
        name_uk: str = None,
        name_en: str = None,
        photo_url: str = None,
    ) -> bool:
        now = datetime.now().isoformat()
        updates = []
        params = []

        for key, value in [
            ('parent_cat_id', parent_cat_id),
            ('name_ru', name_ru),
            ('name_uk', name_uk),
            ('name_en', name_en),
            ('photo_url', photo_url),
        ]:
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(now)
        params.append(subcat_id)
        try:
            self.execute(
                f"UPDATE subcategories SET {', '.join(updates)} WHERE subcat_id = ?",
                tuple(params),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update subcategory {subcat_id}: {e}")
            return False

    def delete_subcategory(self, subcat_id: str) -> Tuple[bool, str]:
        try:
            products = self.execute(
                "SELECT COUNT(*) as count FROM products WHERE subcategory = ?",
                (subcat_id,),
                fetch=True
            )
            if products:
                count = products[0]['count'] if self.use_postgres else products[0][0]
                if count and count > 0:
                    return False, f"Нельзя удалить: в подкатегории {count} товаров"

            self.execute("DELETE FROM subcategories WHERE subcat_id = ?", (subcat_id,), commit=True)
            return True, "Подкатегория удалена"
        except Exception as e:
            logger.error(f"Failed to delete subcategory {subcat_id}: {e}")
            return False, str(e)

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            result = self.execute(
                "SELECT value FROM bot_settings WHERE key = ?",
                (key,),
                fetch=True
            )
            if not result:
                return default
            return result[0]['value'] if self.use_postgres else result[0][0]
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return default

    def set_setting(self, key: str, value: str) -> bool:
        now = datetime.now().isoformat()
        try:
            if self.use_postgres:
                query = """INSERT INTO bot_settings (key, value, updated_at)
                           VALUES (%s, %s, %s)
                           ON CONFLICT (key) DO UPDATE
                           SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"""
                params = (key, value, now)
            else:
                query = """INSERT INTO bot_settings (key, value, updated_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(key) DO UPDATE SET
                           value = excluded.value,
                           updated_at = excluded.updated_at"""
                params = (key, value, now)

            self.execute(query, params, commit=True)
            return True
        except Exception as e:
            logger.error(f"Failed to save setting {key}: {e}")
            return False

    def get_setting_json(self, key: str, default: Any = None) -> Any:
        raw = self.get_setting(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Failed to decode JSON setting {key}: {e}")
            return default

    def set_setting_json(self, key: str, value: Any) -> bool:
        try:
            return self.set_setting(key, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to encode JSON setting {key}: {e}")
            return False

    def get_home_content(self) -> dict:
        data = self.get_setting_json('home_content', default={}) or {}
        return {
            'text_ru': data.get('text_ru'),
            'text_uk': data.get('text_uk'),
            'text_en': data.get('text_en'),
            'photo_file_id': data.get('photo_file_id'),
        }

    def save_home_content(self, data: dict) -> bool:
        current = self.get_home_content()
        current.update(data or {})
        return self.set_setting_json('home_content', current)

    def get_main_menu_core(self) -> dict:
        default = {
            'services': {'ru': '🛒 Услуги', 'uk': '🛒 Послуги', 'en': '🛒 Services'},
            'balance': {'ru': '💰 Баланс: ${balance}', 'uk': '💰 Баланс: ${balance}', 'en': '💰 Balance: ${balance}'},
            'profile': {'ru': '👤 Профиль', 'uk': '👤 Профіль', 'en': '👤 Profile'},
            'referral': {'ru': '🔗 Рефералка', 'uk': '🔗 Рефералка', 'en': '🔗 Referral'},
            'transfer': {'ru': '💸 Перевести средства', 'uk': '💸 Переказати кошти', 'en': '💸 Transfer funds'},
            'support': {'ru': '🆘 Тех поддержка', 'uk': '🆘 Тех підтримка', 'en': '🆘 Support'},
        }
        data = self.get_setting_json('main_menu_core', default=default) or {}
        for key, labels in default.items():
            data.setdefault(key, {})
            for lang, value in labels.items():
                data[key].setdefault(lang, value)
        return data

    def save_main_menu_core(self, data: dict) -> bool:
        current = self.get_main_menu_core()
        for key, labels in (data or {}).items():
            current.setdefault(key, {})
            current[key].update(labels or {})
        return self.set_setting_json('main_menu_core', current)

    def get_custom_menu_buttons(self) -> List[dict]:
        buttons = self.get_setting_json('main_menu_custom_buttons', default=[]) or []
        if not isinstance(buttons, list):
            return []
        return sorted(buttons, key=lambda b: (b.get('sort_order', 9999), b.get('created_at', '')))

    def save_custom_menu_buttons(self, buttons: List[dict]) -> bool:
        normalized = []
        for index, button in enumerate(buttons or []):
            item = dict(button)
            item.setdefault('sort_order', index)
            normalized.append(item)
        return self.set_setting_json('main_menu_custom_buttons', normalized)

    def save_broadcast_draft(self, title: str, text: str, photo_file_id: Optional[str], created_by: int,
                             draft_id: Optional[int] = None) -> Optional[int]:
        now = datetime.now().isoformat()
        try:
            if draft_id:
                self.execute(
                    """UPDATE broadcast_drafts
                       SET title = ?, text = ?, photo_file_id = ?, updated_at = ?
                       WHERE id = ?""",
                    (title, text, photo_file_id, now, draft_id),
                    commit=True
                )
                return draft_id

            if self.use_postgres:
                result = self.execute(
                    """INSERT INTO broadcast_drafts
                       (title, text, photo_file_id, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       RETURNING id""",
                    (title, text, photo_file_id, created_by, now, now),
                    fetch=True,
                    commit=True
                )
                return result[0]['id'] if result else None

            self.execute(
                """INSERT INTO broadcast_drafts
                   (title, text, photo_file_id, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, text, photo_file_id, created_by, now, now),
                commit=True
            )
            result = self.execute("SELECT last_insert_rowid()", fetch=True)
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Failed to save broadcast draft: {e}")
            return None

    def get_broadcast_drafts(self) -> List[dict]:
        try:
            results = self.execute(
                "SELECT * FROM broadcast_drafts ORDER BY updated_at DESC, id DESC",
                fetch=True
            )
            return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get broadcast drafts: {e}")
            return []

    def get_broadcast_draft(self, draft_id: int) -> Optional[dict]:
        try:
            result = self.execute(
                "SELECT * FROM broadcast_drafts WHERE id = ?",
                (draft_id,),
                fetch=True
            )
            return dict(result[0]) if result else None
        except Exception as e:
            logger.error(f"Failed to get broadcast draft {draft_id}: {e}")
            return None

    def delete_broadcast_draft(self, draft_id: int) -> bool:
        try:
            self.execute(
                "DELETE FROM broadcast_drafts WHERE id = ?",
                (draft_id,),
                commit=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete broadcast draft {draft_id}: {e}")
            return False

    def get_category(self, cat_id: str) -> Optional[dict]:
        """Получить категорию с метаданными."""
        try:
            result = self.execute(
                "SELECT cat_id, name_ru, name_uk, name_en, photo_url, sort_order FROM categories WHERE cat_id = ?",
                (cat_id,),
                fetch=True
            )
            if not result:
                return None
            row = result[0]
            if self.use_postgres:
                return dict(row)
            return {
                'cat_id': row[0],
                'name_ru': row[1],
                'name_uk': row[2],
                'name_en': row[3],
                'photo_url': row[4] if len(row) > 4 else None,
                'sort_order': row[5] if len(row) > 5 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get category {cat_id}: {e}")
            return None

    def add_category(self, cat_id: str, name_ru: str, name_uk: str = None, name_en: str = None, sort_order: int = 0, photo_url: str = None) -> bool:
        """Добавить категорию с переводами"""
        now = datetime.now().isoformat()
        try:
            if self.use_postgres:
                query = """INSERT INTO categories (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                params = (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, now, now)
            else:
                query = """INSERT INTO categories (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, created_at, updated_at) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
                params = (cat_id, name_ru, name_uk, name_en, photo_url, sort_order, now, now)
            
            self.execute(query, params, commit=True)
            logger.info(f"Category added successfully: {cat_id} - {name_ru}")
            return True
        except Exception as e:
            logger.error(f"Failed to add category {cat_id}: {e}")
            return False

    def update_category(self, cat_id: str, name_ru: str = None, name_uk: str = None, name_en: str = None, photo_url: str = None) -> bool:
        """Обновить переводы категории"""
        now = datetime.now().isoformat()
        updates = []
        params = []
        
        if name_ru:
            updates.append("name_ru = ?")
            params.append(name_ru)
        if name_uk:
            updates.append("name_uk = ?")
            params.append(name_uk)
        if name_en:
            updates.append("name_en = ?")
            params.append(name_en)
        if photo_url is not None:
            updates.append("photo_url = ?")
            params.append(photo_url)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(now)
        params.append(cat_id)
        
        if self.use_postgres:
            pg_updates = [u.replace('?', '%s') for u in updates]
            query = f"UPDATE categories SET {', '.join(pg_updates)} WHERE cat_id = %s"
        else:
            query = f"UPDATE categories SET {', '.join(updates)} WHERE cat_id = ?"
        
        try:
            self.execute(query, tuple(params), commit=True)
            logger.info(f"Category updated: {cat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update category {cat_id}: {e}")
            return False
    
    def delete_category(self, cat_id: str) -> Tuple[bool, str]:
        try:
            products = self.execute(
                "SELECT COUNT(*) as count FROM products WHERE category = ?",
                (cat_id,),
                fetch=True
            )
            
            if products:
                if self.use_postgres:
                    count = products[0]['count']
                else:
                    count = products[0][0]
                
                if count > 0:
                    return False, f"Нельзя удалить: в категории {count} товаров"
            
            self.execute(
                "DELETE FROM categories WHERE cat_id = ?",
                (cat_id,),
                commit=True
            )
            logger.info(f"Category deleted: {cat_id}")
            return True, "Категория удалена"
        except Exception as e:
            logger.error(f"Failed to delete category: {e}")
            return False, str(e)
    
    def purchase(self, user_id: int, product_id: int) -> Tuple[bool, str, Optional[dict]]:
        try:
            self.execute("BEGIN TRANSACTION")
            
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
            
            if stock == 0:
                raise Exception("❌ Товар закончился")
            
            self.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (price, user_id),
                commit=False
            )
            
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
            
            now = datetime.now().isoformat()
            self.execute(
                """INSERT INTO transactions 
                   (user_id, amount, type, product_id, status, completed_at, currency) 
                   VALUES (?, ?, 'purchase', ?, 'completed', ?, 'USD')""",
                (user_id, price, product_id, now),
                commit=False
            )
            
            self.add_purchase_history(user_id, product_id, product['name'], price)
            
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
                    
                    self.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (bonus, referrer_id),
                        commit=False
                    )
                    
                    self.execute(
                        """UPDATE referrals 
                           SET bonus = bonus + ?, purchase_count = purchase_count + 1, 
                               total_earned = total_earned + ? 
                           WHERE referrer_id = ? AND referral_id = ?""",
                        (bonus, bonus, referrer_id, user_id),
                        commit=False
                    )
                    
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
    
    def add_purchase_history(self, user_id, product_id, product_name, amount):
        now = datetime.now().isoformat()
        self.execute(
            """INSERT INTO purchase_history 
               (user_id, product_id, product_name, amount, purchase_date, completed_date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, product_id, product_name, amount, now, now),
            commit=True
        )

    def get_purchase_history(self, user_id, limit=10):
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

    def create_advanced_promo(self, code, bonus_type, bonus_value, target_type='all', 
                             target_id=0, max_entries=-1, max_uses=-1, 
                             expires_at=None, created_by=None):
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

    def generate_random_code(self, length=8):
        chars = string.ascii_uppercase + string.digits
        part1 = ''.join(random.choices(chars, k=length))
        part2 = ''.join(random.choices(chars, k=length))
        return f"{part1}-{part2}"

    def validate_advanced_promo(self, code, user_id):
        promo = self.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
            (code,),
            fetch=True
        )
        
        if not promo:
            return False, "Промокод не найден"
        
        promo = dict(promo[0])
        
        if promo['expires_at']:
            if datetime.now().isoformat() > promo['expires_at']:
                return False, "Срок действия промокода истек"
        
        entries_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ?",
            (promo['id'],),
            fetch=True
        )
        entries = entries_result[0]['count'] if self.use_postgres else entries_result[0][0]
        
        if promo['max_entries'] > 0 and entries >= promo['max_entries']:
            return False, "Лимит вводов промокода исчерпан"
        
        user_entry = self.execute(
            "SELECT id FROM promo_entries WHERE promo_id = ? AND user_id = ?",
            (promo['id'], user_id),
            fetch=True
        )
        
        if user_entry:
            return False, "Вы уже активировали этот промокод"
        
        return True, promo

    def record_promo_entry(self, promo_id, user_id):
        now = datetime.now().isoformat()
        self.execute(
            "INSERT INTO promo_entries (promo_id, user_id, entered_at) VALUES (?, ?, ?)",
            (promo_id, user_id, now),
            commit=True
        )

    def use_promo_entry(self, promo_id, user_id, transaction_id):
        self.execute(
            """UPDATE promo_entries 
               SET used = 1, used_at = ?, transaction_id = ? 
               WHERE promo_id = ? AND user_id = ?""",
            (datetime.now().isoformat(), transaction_id, promo_id, user_id),
            commit=True
        )

    def get_promo_stats(self, promo_id):
        stats = {}
        
        entries_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ?",
            (promo_id,),
            fetch=True
        )
        stats['total_entries'] = entries_result[0]['count'] if self.use_postgres else entries_result[0][0]
        
        used_result = self.execute(
            "SELECT COUNT(*) as count FROM promo_entries WHERE promo_id = ? AND used = 1",
            (promo_id,),
            fetch=True
        )
        stats['used'] = used_result[0]['count'] if self.use_postgres else used_result[0][0]
        
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
    
    def create_promo_code(self, code, discount_type, discount_value, min_amount=0, 
                          max_uses=-1, expires_at=None, created_by=None):
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
        result = self.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
            (code.upper(),),
            fetch=True
        )
        return dict(result[0]) if result else None

    def validate_promo_code(self, code, user_id, amount):
        valid, result = self.validate_advanced_promo(code, user_id)
        if not valid:
            return False, result
        
        promo = result
        if amount < promo.get('min_amount', 0):
            return False, f"Минимальная сумма заказа: ${promo.get('min_amount', 0)}"
        
        return True, promo

    def apply_promo_code(self, code, user_id, amount):
        valid, result = self.validate_promo_code(code, user_id, amount)
        if not valid:
            return False, result, amount
        
        promo = result
        
        discount = 0
        if promo['bonus_type'] in ['percent', 'discount']:
            discount = amount * (promo['bonus_value'] / 100)
        else:
            discount = min(promo['bonus_value'], amount)
        
        final_amount = amount - discount
        
        return True, "Промокод применен", {
            'original': amount,
            'discount': discount,
            'final': final_amount,
            'promo_id': promo['id']
        }

    def use_promo_code(self, promo_id, user_id, transaction_id):
        return self.use_promo_entry(promo_id, user_id, transaction_id)

    def get_all_promo_codes(self):
        results = self.execute(
            "SELECT * FROM promo_codes ORDER BY created_at DESC",
            fetch=True
        )
        return [dict(row) for row in results] if results else []

    def deactivate_promo_code(self, promo_id):
        self.execute(
            "UPDATE promo_codes SET is_active = 0 WHERE id = ?",
            (promo_id,),
            commit=True
        )

    def admin_add_balance(self, user_id, amount, reason=""):
        now = datetime.now().isoformat()
        self.execute("BEGIN TRANSACTION")
        try:
            self.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
                commit=False
            )
            
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
        if self.use_postgres:
            results = self.execute(
                """SELECT user_id, username, first_name, balance 
                   FROM users 
                   WHERE user_id::text LIKE %s OR username LIKE %s OR first_name LIKE %s
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
    
    def add_transaction(self, user_id: int, amount: float, type_: str, 
                       status: str, invoice_id: Optional[str] = None,
                       currency: Optional[str] = None, 
                       metadata: Optional[dict] = None) -> bool:
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
        results = self.execute(
            """SELECT * FROM transactions 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit),
            fetch=True
        )
        return [dict(row) for row in results] if results else []
    
    def get_stats(self) -> dict:
        stats = {}
        
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
        
        products = self.execute(
            "SELECT COUNT(*) as count FROM products WHERE is_active = 1",
            fetch=True
        )[0]
        if self.use_postgres:
            stats['active_products'] = products['count'] or 0
        else:
            stats['active_products'] = products[0] or 0
        
        return stats
    
    def set_pending_action(self, user_id: int, action: str, data: Optional[str] = None):
        now = datetime.now().isoformat()
        if self.use_postgres:
            self.execute(
                """INSERT INTO pending_actions (user_id, action, data, created_at) 
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET action = %s, data = %s, created_at = %s""",
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
        self.execute(
            "DELETE FROM pending_actions WHERE user_id = ?",
            (user_id,),
            commit=True
        )
    
    def export_users(self) -> List[tuple]:
        return self.execute(
            "SELECT user_id, username, balance, registered_date, last_active FROM users",
            fetch=True
        ) or []
    
    def export_sales(self, days: int = 30) -> List[tuple]:
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
        self.conn.close()


db = Database()
