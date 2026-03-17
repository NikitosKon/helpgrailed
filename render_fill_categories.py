# render_fill_categories.py
from database import db
from config import config

print("=" * 50)
print("ЗАПОЛНЕНИЕ КАТЕГОРИЙ НА RENDER")
print("=" * 50)

# Получаем дефолтные категории
default_categories = {
    'grailed_accounts': "📱 Grailed account's",
    'paypal': "💳 PayPal",
    'call_service': "📞 Прозвон сервис",
    'grailed_likes': "❤️ Накрутка лайков на Grailed",
    'ebay': "🏷 eBay",
    'support': "🆘 Тех поддержка",
}

print("\nДобавляю категории в базу данных...\n")

for cat_id, cat_name in default_categories.items():
    try:
        # Проверяем, есть ли уже
        existing = db.get_categories()
        if cat_id in existing:
            print(f"🔄 Категория {cat_id} уже существует: {existing[cat_id]}")
            # Обновляем название
            db.update_category(cat_id, cat_name)
            print(f"✅ Обновлено: {cat_id} - {cat_name}")
        else:
            # Добавляем новую
            db.add_category(cat_id, cat_name)
            print(f"✅ Добавлено: {cat_id} - {cat_name}")
    except Exception as e:
        print(f"❌ Ошибка с {cat_id}: {e}")

print("\n" + "=" * 50)
print("ПРОВЕРКА ИТОГА:")
print("=" * 50)

# Проверяем, что получилось
categories = db.get_categories()
if categories:
    print(f"\nНайдено категорий: {len(categories)}")
    for cat_id, cat_name in categories.items():
        print(f"  • {cat_id}: {cat_name}")
else:
    print("❌ Категории не найдены!")

print("\n" + "=" * 50)
print("ГОТОВО! Теперь перезапусти бота на Render")
print("=" * 50)