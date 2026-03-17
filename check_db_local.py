# check_db_local.py
import sqlite3
import os

print("=" * 50)
print("ЛОКАЛЬНАЯ ПРОВЕРКА БАЗЫ ДАННЫХ")
print("=" * 50)

DB_FILE = 'helpgrailed_bot.db'

# Проверяем существует ли файл БД
if not os.path.exists(DB_FILE):
    print(f"❌ Файл {DB_FILE} не найден!")
    exit()

print(f"✅ Файл БД найден: {DB_FILE}")

# Подключаемся к SQLite
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Проверяем таблицы
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"\n📊 Таблицы в БД: {len(tables)}")
for table in tables:
    print(f"  • {table[0]}")

# Проверяем структуру таблицы categories
try:
    cursor.execute("PRAGMA table_info(categories);")
    columns = cursor.fetchall()
    print(f"\n📋 Структура таблицы categories:")
    if columns:
        for col in columns:
            print(f"  • {col[1]} ({col[2]})")
    else:
        print("  ❌ Таблица categories не найдена")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Если есть таблица, покажем данные
if 'categories' in [t[0] for t in tables]:
    cursor.execute("SELECT * FROM categories;")
    rows = cursor.fetchall()
    print(f"\n📦 Данные в categories: {len(rows)} записей")
    for row in rows:
        print(f"  • {row}")

conn.close()
print("\n✅ Проверка завершена")