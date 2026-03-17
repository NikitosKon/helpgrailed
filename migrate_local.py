# migrate_local.py
import sqlite3
import os
from datetime import datetime

DB_FILE = 'helpgrailed_bot.db'

print("🔄 Начинаю миграцию локальной базы данных...")

# Подключаемся к БД
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Проверяем текущую структуру
cursor.execute("PRAGMA table_info(categories)")
columns = cursor.fetchall()
print(f"\nТекущая структура: {[col[1] for col in columns]}")

# Создаем резервную копию
cursor.execute("ALTER TABLE categories RENAME TO categories_old")
print("✅ Создана резервная копия")

# Создаем новую таблицу с нужными колонками
cursor.execute("""
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cat_id TEXT UNIQUE NOT NULL,
        name_ru TEXT NOT NULL,
        name_uk TEXT NOT NULL,
        name_en TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )
""")
print("✅ Создана новая таблица")

# Копируем данные из старой таблицы
cursor.execute("SELECT cat_id, name, sort_order, created_at, updated_at FROM categories_old")
old_cats = cursor.fetchall()

for cat in old_cats:
    cat_id = cat[0]
    name = cat[1]
    sort_order = cat[2]
    created_at = cat[3]
    updated_at = cat[4]
    
    cursor.execute(
        """INSERT INTO categories 
           (cat_id, name_ru, name_uk, name_en, sort_order, created_at, updated_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cat_id, name, name, name, sort_order, created_at, updated_at)
    )
print(f"✅ Перенесено {len(old_cats)} категорий")

# Удаляем старую таблицу
cursor.execute("DROP TABLE categories_old")
print("✅ Удалена старая таблица")

# Проверяем результат
cursor.execute("SELECT cat_id, name_ru, name_uk, name_en FROM categories")
new_cats = cursor.fetchall()
print(f"\n📊 Новые данные:")
for cat in new_cats:
    print(f"  • {cat[0]}: {cat[1]} / {cat[2]} / {cat[3]}")

conn.commit()
conn.close()

print("\n✅ Миграция локальной БД завершена!")
print("Теперь нужно:")
print("1. Закоммитить изменения:")
print("   git add database.py migrate_local.py")
print("   git commit -m 'Update categories table structure'")
print("   git push origin master")
print("2. На Render запустить migrate_local.py через консоль")
print("   или добавить временную команду /migrate")