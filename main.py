import asyncio
import logging
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = "8830743683:AAEpsT5xrduXGgYzRLTDTHiqgTZAxUVk8cA"

# ==================== НАСТРОЙКИ ====================
MANAGER_USERNAME = "@financialriskss"
REVIEWS_URL = "https://t.me/your_reviews_channel"  # Замените на ссылку вашей группы/канала отзывов

# ID вашей админ-группы (полученный от IDBot)
ADMIN_CHAT_ID = -5237741624

# Реквизиты
PAYMENT_CARD = "4874 0700 3188 2838"
PAYMENT_NAME = "Данило Жирик Ігорович"

# Авторасчет цены покупки Stars в UAH
def calculate_buy_price(stars: int) -> float:
    """
    Расчет:
    - 60 stars = 60.0 грн (1.00 грн / star)
    - 1000 stars = 840.0 грн (0.84 грн / star)
    """
    if stars <= 60:
        rate = 1.00
    elif stars >= 1000:
        rate = 0.84
    else:
        # Плавная скидка от 1.00 до 0.84
        rate = 1.00 - ((stars - 60) / (1000 - 60)) * (1.00 - 0.84)
    return round(stars * rate, 2)

# Выплата при продаже (0.40 грн / star)
def calculate_sell_payout(stars: int) -> float:
    return round(stars * 0.40, 2)
# ===================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class BotStates(StatesGroup):
    buy_amount = State()
    buy_username = State()
    sell_amount = State()
    calc_grn = State()
    calc_stars = State()
    receipt_upload = State()

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="⭐️ Замовити Зірки"))
    builder.row(types.KeyboardButton(text="💵 Продати Зірки"))
    builder.row(
        types.KeyboardButton(text="🎁 Бонуси"),
        types.KeyboardButton(text="🧑‍💼 Підтримка")
    )
    builder.row(
        types.KeyboardButton(text="🛡️ Відгуки 10 100+"),
        types.KeyboardButton(text="💫 Розрахувати ціну")
    )
    return builder.as_markup(resize_keyboard=True)

# --- 0. СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "⭐ **Вітаємо у StarsUkr!**\n\nЗамовити зірки можна від 50 грн\n\n"
        "💳 Оплата карткою\n⚡ Швидке зарахування\n💬 Підтримка після покупки",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

# --- 1. КНОПКА: ⭐️ Замовити Зірки ---
@dp.message(F.text == "⭐️ Замовити Зірки")
async def process_buy_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.buy_amount)
    await message.answer("Введіть кількість Stars, яку хочете придбати (мінімум 50):")

@dp.message(BotStates.buy_amount)
async def process_buy_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Будь ласка, введіть число!")
        return
    
    amount = int(message.text)
    if amount < 50:
        await message.answer("Мінімальне замовлення = 50 ⭐️. Спробуйте ще раз:")
        return

    price = calculate_buy_price(amount)
    await state.update_data(buy_amount=amount, buy_price=price)
    
    await state.set_state(BotStates.buy_username)
    await message.answer(
        f"💫 **Напишіть @username**, на який потрібно надіслати TG Stars.\n\n"
        f"📊 **{amount} ⭐️ — {price} грн**\n\n"
        f"⚠️ Увага! Якщо ви введете @username неправильно, зірки можуть бути відправлені іншій людині!",
        parse_mode="Markdown"
    )

@dp.message(BotStates.buy_username)
async def process_buy_username(message: types.Message, state: FSMContext):
    target_username = message.text
    await state.update_data(target_username=target_username)

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="💳 Карта", callback_data="pay_card"))
    
    await message.answer(
        f"✅ **Отримувача збережено!** ({target_username})\n\nВиберіть зручний спосіб оплати та завершіть покупку ⭐️",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "pay_card")
async def show_card_payment(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get("buy_price", 0)
    amount = data.get("buy_amount", 0)

    text = (
        f"💳 **Сума до оплати: {price} грн**\n"
        f"({amount} ⭐️ на акаунт)\n\n"
        f"🏦 **Реквізити для оплати:**\n\n"
        f"**Номер картки:** `{PAYMENT_CARD}`\n"
        f"**Отримувач:** {PAYMENT_NAME}\n"
        f"**Призначення:** Оплата за товар\n\n"
        f"💡 Оплатіть через будь-який банк або застосунок за реквізитами картки."
    )

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ Я оплатив", callback_data="i_paid"))
    
    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(F.data == "i_paid")
async def process_i_paid(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.receipt_upload)
    await call.message.answer("📸 **Супер, тепер надішліть скріншот повної квитанції про оплату.**")
    await call.answer()

# --- 2. ОБРАБОТКА ЧЕКА И ОТПРАВКА В АДМИН-ГРУППУ ---
@dp.message(BotStates.receipt_upload, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    order_id = str(uuid.uuid4())
    data = await state.get_data()
    amount = data.get("buy_amount", 0)
    price = data.get("buy_price", 0)
    target_username = data.get("target_username", "Не вказано")

    # Ответ клиенту
    await message.answer(
        f"❇️ **Чек прийнято!**\n\n"
        f"📋 **Замовлення:**\n`{order_id}`\n"
        f"⏳ **Статус:** На розгляді\n\n"
        f"⌛ **Час обробки:** 15-30 хвилин",
        parse_mode="Markdown"
    )

    # Кнопки для управления заказом в админ-группе
    admin_kb = InlineKeyboardBuilder()
    admin_kb.row(
        types.InlineKeyboardButton(text="✅ Схвалити", callback_data=f"approve_{order_id}_{amount}_{target_username}_{message.from_user.id}"),
        types.InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{order_id}_{message.from_user.id}")
    )

    # Пересылаем чек и данные заказа в админ-группу
    photo_id = message.photo[-1].file_id
    await bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo_id,
        caption=(
            f"📥 **НОВЕ ЗАМОВЛЕННЯ!**\n\n"
            f"📋 **ID:** `{order_id}`\n"
            f"👤 **Покупець:** @{message.from_user.username or 'без_юзернейма'} (ID: `{message.from_user.id}`)\n"
            f"🎯 **Отримувач ⭐️:** {target_username}\n"
            f"⭐️ **Кількість:** {amount} Stars\n"
            f"💵 **Сума:** {price} грн"
        ),
        parse_mode="Markdown",
        reply_markup=admin_kb.as_markup()
    )
    await state.clear()

# --- 3. РЕАКЦИЯ АДМИНА (СХВАЛИТИ / ВІДХИЛИТИ) ---
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(call: types.CallbackQuery):
    _, order_id, amount, target_username, user_id = call.data.split("_")
    
    review_kb = InlineKeyboardBuilder()
    review_kb.row(types.InlineKeyboardButton(text="📝 Залишити відгук", url=REVIEWS_URL))

    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=(
                f"✅ **Замовлення схвалено!**\n\n"
                f"📋 **ID:** `{order_id}`\n"
                f"📦 **Товар:** {amount} зірок\n\n"
                f"🚀 **Ваше замовлення вже обробляється автоматично!**\n\n"
                f"🎉 **Готово! {amount} зірок надіслано на {target_username}**\n\n"
                f"✨ Дякуємо за користування StarsUkr Bot!"
            ),
            parse_mode="Markdown",
            reply_markup=review_kb.as_markup()
        )
    except Exception as e:
        logging.error(f"Error sending message to user: {e}")

    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ **СХВАЛЕНО**")
    await call.answer("Замовлення схвалено!")

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(call: types.CallbackQuery):
    _, order_id, user_id = call.data.split("_")
    
    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=f"❌ **Замовлення `{order_id}` відхилено.**\nЗверніться у підтримку: {MANAGER_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error sending message to user: {e}")

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ **ВІДХИЛЕНО**")
    await call.answer("Замовлення відхилено!")

# --- 4. КНОПКА: 💵 Продати Зірки ---
@dp.message(F.text == "💵 Продати Зірки")
async def process_sell_start(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.sell_amount)
    await message.answer("📬 **Продати Stars**\n\nВкажіть, будь ласка, скільки зірок ви бажаєте продати.\nМінімальна сума — 500 ⭐️")

@dp.message(BotStates.sell_amount)
async def process_sell_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть число!")
        return

    amount = int(message.text)
    if amount < 500:
        await message.answer("Мінімальна сума для продажу — 500 ⭐️. Спробуйте ще раз:")
        return

    payout = calculate_sell_payout(amount)
    
    await message.answer(
        f"📬 **Ви продаєте: {amount} Stars**\n"
        f"💵 **Ви отримаєте: {payout} грн**\n\n"
        f"Щоб продати зірки, напишіть нашому менеджеру: {MANAGER_USERNAME}\n\n"
        f"📩 **У повідомленні вкажіть:**\n"
        f"• Кількість Stars, які продаєте\n"
        f"• Ваш Telegram username\n"
        f"• Номер вашої картки"
    )
    await state.clear()

# --- 5. КНОПКА: 💫 Розрахувати ціну ---
@dp.message(F.text == "💫 Розрахувати ціну")
async def process_calc(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="ГРН 💵 --> Зірки ⭐️", callback_data="calc_grn"))
    kb.row(types.InlineKeyboardButton(text="Зірки ⭐️ --> ГРН 💵", callback_data="calc_stars"))
    await message.answer("Оберіть, як вам треба порахувати 👇", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "calc_grn")
async def calc_grn_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.calc_grn)
    await call.message.answer("Введіть суму в грн:")
    await call.answer()

@dp.message(BotStates.calc_grn)
async def calc_grn_process(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть число!")
        return
    grn = float(message.text)
    stars = int(grn / 0.85)
    await message.answer(f"Ви оплачуєте: {grn} грн\nВи отримуєте приблизно: {stars} ⭐️")
    await state.clear()

@dp.callback_query(F.data == "calc_stars")
async def calc_stars_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.calc_stars)
    await call.message.answer("Введіть кількість Stars:")
    await call.answer()

@dp.message(BotStates.calc_stars)
async def calc_stars_process(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть число!")
        return
    stars = int(message.text)
    price = calculate_buy_price(stars)
    await message.answer(f"За {stars} ⭐️ сума до оплати: {price} грн")
    await state.clear()

# --- 6. ДОПОЛНИТЕЛЬНЫЕ КНОПКИ ---
@dp.message(F.text == "🎁 Бонуси")
async def process_bonuses(message: types.Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    await message.answer(
        f"Запрошуй друзів, щоб отримати безкоштовні Stars ⭐️\n\n"
        f"За будь-яку покупку твого друга ти отримаєш **1% ⭐️ собі на баланс**\n\n"
        f"Запрошено друзів: 0\n"
        f"Баланс Stars: 0 ⭐️\n\n"
        f"🔗 **Твоє посилання:**\n{ref_link}",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🧑‍💼 Підтримка")
async def process_support(message: types.Message):
    await message.answer(f"Напишіть нашому менеджеру: {MANAGER_USERNAME}")

@dp.message(F.text == "🛡️ Відгуки 10 100+")
async def process_reviews(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="Читати відгуки 💬", url=REVIEWS_URL))
    await message.answer("Наші відгуки доступні за посиланням нижче 👇", reply_markup=kb.as_markup())

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
