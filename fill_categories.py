# fill_categories.py
import sqlite3
import os
from datetime import datetime

# Игнорируем PostgreSQL, работаем напрямую с SQLite
DB_FILE = 'helpgrailed_bot.db'

def add_category_sqlite(cat_id, name):
    """Добавить категорию напрямую в SQLite"""
    conn = None
    try:
        # Подключаемся к SQLite
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Создаем таблицу если её нет
        c.execute('''CREATE TABLE IF NOT EXISTS categories
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      cat_id TEXT UNIQUE NOT NULL,
                      name TEXT NOT NULL,
                      sort_order INTEGER DEFAULT 0,
                      created_at TEXT,
                      updated_at TEXT)''')
        
        now = datetime.now().isoformat()
        
        # Проверяем, есть ли уже такая категория
        c.execute("SELECT cat_id FROM categories WHERE cat_id = ?", (cat_id,))
        if c.fetchone():
            # Обновляем существующую
            c.execute(
                "UPDATE categories SET name = ?, updated_at = ? WHERE cat_id = ?",
                (name, now, cat_id)
            )
            print(f"🔄 {cat_id}: {name} (обновлено)")
        else:
            # Добавляем новую
            c.execute(
                "INSERT INTO categories (cat_id, name, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (cat_id, name, 0, now, now)
            )
            print(f"✅ {cat_id}: {name} (добавлено)")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Ошибка с {cat_id}: {e}")
    finally:
        if conn:
            conn.close()

default_categories = {
    'grailed_accounts': "📱 Grailed account's",
    'paypal': "💳 PayPal",
    'call_service': "📞 Прозвон сервис",
    'grailed_likes': "❤️ Накрутка лайков на Grailed",
    'ebay': "🏷 eBay",
    'support': "🆘 Тех поддержка",
}

print(f"Заполняю категории в {DB_FILE}...")
print("=" * 40)

for cat_id, cat_name in default_categories.items():
    add_category_sqlite(cat_id, cat_name)

print("=" * 40)
print("Готово! Теперь категории есть в локальной БД.")
print("Сделай деплой на Render - они автоматически переедут в PostgreSQL.")