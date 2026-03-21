from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from keyboards.reply import get_text


async def _edit_or_send(query, text, reply_markup=None, parse_mode=None, **kwargs):
    try:
        return await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    except Exception as e:
        if 'There is no text in the message to edit' not in str(e):
            raise
        try:
            await query.message.delete()
        except Exception:
            pass
        return await query.get_bot().send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )


FAQ_TEXTS = {
    'how_order': {
        'ru': (
            "<b>Как оформить заказ</b>\n\n"
            "1. Откройте раздел с услугами.\n"
            "2. Выберите категорию, подкатегорию и нужную услугу.\n"
            "3. Проверьте описание, цену и наличие.\n"
            "4. Нажмите кнопку покупки и подтвердите оплату.\n"
            "5. Если для выполнения нужны данные, администратор или поддержка напишут вам отдельно."
        ),
        'uk': (
            "<b>Як оформити замовлення</b>\n\n"
            "1. Відкрийте розділ з послугами.\n"
            "2. Оберіть категорію, підкатегорію та потрібну послугу.\n"
            "3. Перевірте опис, ціну та наявність.\n"
            "4. Натисніть кнопку покупки та підтвердіть оплату.\n"
            "5. Якщо для виконання потрібні дані, адміністратор або підтримка напишуть вам окремо."
        ),
        'en': (
            "<b>How to place an order</b>\n\n"
            "1. Open the services section.\n"
            "2. Choose a category, subcategory, and the service you need.\n"
            "3. Check the description, price, and availability.\n"
            "4. Tap the purchase button and confirm payment.\n"
            "5. If extra details are needed, admin or support will message you separately."
        ),
    },
    'after_payment': {
        'ru': (
            "<b>Что делать после оплаты</b>\n\n"
            "Обычно ничего дополнительно делать не нужно. Если услуга требует логин, ссылку, почту или другие данные, "
            "администратор напишет вам, что именно нужно отправить. Рекомендуем не удалять чат с ботом и держать уведомления включёнными."
        ),
        'uk': (
            "<b>Що робити після оплати</b>\n\n"
            "Зазвичай нічого додатково робити не потрібно. Якщо для послуги потрібен логін, посилання, пошта або інші дані, "
            "адміністратор напише вам, що саме потрібно надіслати. Рекомендуємо не видаляти чат з ботом і тримати сповіщення увімкненими."
        ),
        'en': (
            "<b>What to do after payment</b>\n\n"
            "Usually nothing else is needed. If the service requires a login, link, email, or other details, "
            "admin will message you with the exact instructions. We recommend keeping this chat and notifications enabled."
        ),
    },
    'timing': {
        'ru': (
            "<b>Сроки выполнения</b>\n\n"
            "Срок зависит от выбранной услуги. Быстрые цифровые позиции могут обрабатываться почти сразу, "
            "а ручные услуги требуют больше времени. Точные сроки смотрите в описании товара или уточняйте у поддержки."
        ),
        'uk': (
            "<b>Терміни виконання</b>\n\n"
            "Термін залежить від обраної послуги. Швидкі цифрові позиції можуть оброблятися майже одразу, "
            "а ручні послуги потребують більше часу. Точні терміни дивіться в описі товару або уточнюйте у підтримки."
        ),
        'en': (
            "<b>Fulfillment timing</b>\n\n"
            "Timing depends on the selected service. Fast digital items can be processed almost instantly, "
            "while manual services take longer. Check the product description or contact support for exact timing."
        ),
    },
    'refunds': {
        'ru': (
            "<b>Возвраты и спорные ситуации</b>\n\n"
            "Если возникла проблема с заказом, сразу напишите в поддержку. Каждый случай рассматривается отдельно. "
            "Если услуга ещё не была начата, шанс на возврат выше. Если работа уже выполнена или в процессе, решение зависит от конкретной ситуации."
        ),
        'uk': (
            "<b>Повернення та спірні ситуації</b>\n\n"
            "Якщо виникла проблема із замовленням, одразу напишіть у підтримку. Кожен випадок розглядається окремо. "
            "Якщо послуга ще не була розпочата, шанс на повернення вищий. Якщо робота вже виконана або в процесі, рішення залежить від конкретної ситуації."
        ),
        'en': (
            "<b>Refunds and disputes</b>\n\n"
            "If there is any issue with your order, contact support right away. Each case is reviewed individually. "
            "If the service has not started yet, a refund is more likely. If work is already completed or in progress, the decision depends on the specific case."
        ),
    },
    'deposit': {
        'ru': (
            "<b>Депозит и вывод</b>\n\n"
            "Баланс можно пополнить через доступные способы оплаты внутри бота. После оплаты он обновляется автоматически. "
            "Для вывода откройте соответствующий раздел и следуйте инструкции, которая показана в боте."
        ),
        'uk': (
            "<b>Депозит і виведення</b>\n\n"
            "Баланс можна поповнити через доступні способи оплати всередині бота. Після оплати він оновлюється автоматично. "
            "Для виведення відкрийте відповідний розділ і дотримуйтесь інструкції, яка показана в боті."
        ),
        'en': (
            "<b>Deposit and withdrawal</b>\n\n"
            "You can top up your balance using the available payment methods inside the bot. After payment, the balance updates automatically. "
            "For withdrawals, open the withdrawal section and follow the instructions shown there."
        ),
    },
}


FAQ_ORDER = ['how_order', 'after_payment', 'timing', 'refunds', 'deposit']


def _faq_label(key: str, lang: str) -> str:
    labels = {
        'how_order': {'ru': 'Как оформить заказ', 'uk': 'Як оформити замовлення', 'en': 'How to order'},
        'after_payment': {'ru': 'Что делать после оплаты', 'uk': 'Що робити після оплати', 'en': 'What after payment'},
        'timing': {'ru': 'Сроки выполнения', 'uk': 'Терміни виконання', 'en': 'Fulfillment timing'},
        'refunds': {'ru': 'Возвраты и споры', 'uk': 'Повернення та спори', 'en': 'Refunds and disputes'},
        'deposit': {'ru': 'Депозит и вывод', 'uk': 'Депозит і виведення', 'en': 'Deposit and withdrawal'},
    }
    return labels.get(key, {}).get(lang) or labels.get(key, {}).get('ru') or key


async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    lang = (db.get_user(user.id) or {}).get('language', 'ru')

    keyboard = [[InlineKeyboardButton(_faq_label(key, lang), callback_data=f'faq_{key}')] for key in FAQ_ORDER]
    keyboard.append([InlineKeyboardButton(get_text('back', user.id), callback_data='menu')])

    await _edit_or_send(
        query,
        f"❓ <b>{get_text('faq', user.id)}</b>\n\n{get_text('faq_intro', user.id)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def handle_faq_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_key: str):
    query = update.callback_query
    user = query.from_user
    lang = (db.get_user(user.id) or {}).get('language', 'ru')

    text = FAQ_TEXTS.get(item_key, {}).get(lang) or FAQ_TEXTS.get(item_key, {}).get('ru')
    if not text:
        text = get_text('error', user.id)

    await _edit_or_send(
        query,
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text('back', user.id), callback_data='faq')]
        ]),
        parse_mode='HTML'
    )
