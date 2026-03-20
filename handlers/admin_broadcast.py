from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import ADMIN_IDS
import logging
import asyncio

logger = logging.getLogger(__name__)

# Хранилище для рассылок (чтобы можно было отменить)
active_broadcasts = {}

async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню рассылок"""
    query = update.callback_query
    user = query.from_user
    
    if user.id not in ADMIN_IDS:
        await query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 Создать рассылку", callback_data='broadcast_create')],
        [InlineKeyboardButton("📊 Статистика рассылок", callback_data='broadcast_stats')],
        [InlineKeyboardButton("◀️ Назад", callback_data='admin')]
    ]
    
    await query.edit_message_text(
        "📢 <b>Рассылки</b>\n\n"
        "Создайте рассылку для всех пользователей бота:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def broadcast_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания рассылки"""
    query = update.callback_query
    user = query.from_user
    
    # Сохраняем шаг создания
    context.user_data['broadcast_step'] = 'text'
    db.set_pending_action(user.id, 'broadcast_text')
    
    await query.edit_message_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Введите текст рассылки (можно использовать HTML-теги):\n"
        "Пример: <code>&lt;b&gt;Важное объявление!&lt;/b&gt;</code>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')
        ]]),
        parse_mode='HTML'
    )

async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    """Предпросмотр рассылки"""
    user = update.effective_user
    
    # Сохраняем текст
    context.user_data['broadcast_text'] = text
    
    # Показываем предпросмотр
    keyboard = [
        [
            InlineKeyboardButton("✅ Отправить", callback_data='broadcast_send'),
            InlineKeyboardButton("✏️ Редактировать", callback_data='broadcast_edit')
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data='admin_broadcast_menu')]
    ]
    
    await update.message.reply_text(
        f"📢 <b>Предпросмотр рассылки:</b>\n\n{text}\n\n"
        f"<i>Так сообщение увидят пользователи</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    db.clear_pending_action(user.id)

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки"""
    query = update.callback_query
    user = query.from_user
    
    text = context.user_data.get('broadcast_text')
    if not text:
        await query.edit_message_text("❌ Ошибка: текст не найден")
        return
    
    await query.edit_message_text(
        "📢 <b>Рассылка началась!</b>\n\n"
        "⏳ Идет отправка... Это может занять несколько минут.\n"
        "Вы получите отчет по окончании.",
        parse_mode='HTML'
    )
    
    # Получаем всех пользователей
    users = db.execute("SELECT user_id FROM users", fetch=True)
    total = len(users)
    success = 0
    failed = 0
    blocked = 0
    
    # Создаем ID рассылки для возможности отмены
    broadcast_id = str(user.id) + '_' + str(datetime.now().timestamp())
    active_broadcasts[broadcast_id] = {'active': True, 'cancelled': False}
    
    # Отправляем сообщение в лог
    logger.info(f"📢 Начата рассылка {broadcast_id} от админа {user.id}. Всего пользователей: {total}")
    
    # Отправляем по очереди с задержкой
    for i, user_row in enumerate(users):
        # Проверяем, не отменена ли рассылка
        if broadcast_id in active_broadcasts and active_broadcasts[broadcast_id].get('cancelled'):
            logger.info(f"📢 Рассылка {broadcast_id} отменена")
            break
            
        user_id = user_row['user_id'] if db.use_postgres else user_row[0]
        try:
            await context.bot.send_message(
                user_id,
                text,
                parse_mode='HTML'
            )
            success += 1
            logger.info(f"✅ Отправлено пользователю {user_id}")
        except Exception as e:
            if "blocked" in str(e).lower():
                blocked += 1
                logger.info(f"🚫 Пользователь {user_id} заблокировал бота")
            else:
                failed += 1
                logger.error(f"❌ Ошибка отправки {user_id}: {e}")
        
        # Задержка между сообщениями (30 в секунду = 0.033 сек)
        await asyncio.sleep(0.05)
        
        # Каждые 100 сообщений обновляем статус (если есть callback)
        if i % 100 == 0 and i > 0:
            try:
                await query.edit_message_text(
                    f"📢 <b>Рассылка...</b>\n\n"
                    f"📊 Прогресс: {i}/{total}\n"
                    f"✅ Успешно: {success}\n"
                    f"🚫 Заблокировали бота: {blocked}\n"
                    f"❌ Ошибок: {failed}",
                    parse_mode='HTML'
                )
            except:
                pass
    
    # Удаляем из активных рассылок
    if broadcast_id in active_broadcasts:
        del active_broadcasts[broadcast_id]
    
    # Итоговый отчет
    delivered_pct = (success / total * 100) if total else 0
    report = (
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"📊 Всего пользователей: {total}\n"
        f"✅ Успешно доставлено: {success}\n"
        f"🚫 Заблокировали бота: {blocked}\n"
        f"❌ Ошибок отправки: {failed}\n\n"
        f"📈 Доставлено: {success}/{total} ({delivered_pct:.1f}%)"
    )
    
    await context.bot.send_message(
        user.id,
        report,
        parse_mode='HTML'
    )
    
    # Очищаем данные
    context.user_data.clear()
    db.clear_pending_action(user.id)

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена рассылки"""
    query = update.callback_query
    user = query.from_user
    
    # Ищем активную рассылку этого админа
    for bid, data in active_broadcasts.items():
        if bid.startswith(str(user.id)):
            data['cancelled'] = True
            await query.edit_message_text("✅ Рассылка отменена")
            return
    
    await query.edit_message_text("❌ Активная рассылка не найдена")

async def broadcast_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика рассылок"""
    query = update.callback_query
    
    # Получаем статистику по пользователям
    total_row = db.execute("SELECT COUNT(*) as count FROM users", fetch=True)[0]
    total_users = total_row['count'] if db.use_postgres else total_row[0]

    active_today_row = db.execute(
        "SELECT COUNT(*) as count FROM users WHERE DATE(last_active) = DATE(?)",
        (datetime.now().date().isoformat(),),
        fetch=True
    )[0]
    active_today = active_today_row['count'] if db.use_postgres else active_today_row[0]
    
    text = (
        f"📊 <b>Статистика пользователей</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🟢 Активных сегодня: {active_today}\n"
        f"📊 Процент активности: {(active_today / total_users * 100) if total_users else 0:.1f}%\n\n"
        f"<i>Рассылка будет отправлена всем пользователям</i>"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='admin_broadcast_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
