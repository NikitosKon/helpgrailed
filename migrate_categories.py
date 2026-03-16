# migrate_categories.py
from database import db
from config import CATEGORIES

print("Миграция категорий...")
for cat_id, cat_name in CATEGORIES.items():
    try:
        db.add_category(cat_id, cat_name)
        print(f"✅ {cat_id} - {cat_name}")
    except:
        print(f"❌ {cat_id} уже существует")
print("Готово!")