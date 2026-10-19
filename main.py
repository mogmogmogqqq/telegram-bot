import asyncio
import logging
import sqlite3
import uuid
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

BOT_TOKEN = "8830743683:AAEpsT5xrduXGgYzRLTDTHiqgTZAxUVk8cA"

# ==================== НАСТРОЙКИ ====================
MANAGER_USERNAME = "@financialriskss"
REVIEWS_URL = "https://t.me/starsukr_reviewsss"
RULES_URL = "https://telegra.ph/Pravila-koristuvannya-botom-starsukre-bot-10-19"

ADMIN_CHAT_ID = -5237741624

PAYMENT_CARD = "4874 0700 3188 2838"
PAYMENT_NAME = "Данило Жирик Ігорович"

# ==================== БАЗА ДАННЫХ (SQLite) ====================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            invited_count INTEGER DEFAULT 0,
            referrer_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

def db_add_user(user_id: int, username: str, referrer_id: int = None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        valid_referrer = None
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                valid_referrer = referrer_id
                cursor.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (valid_referrer,))
        
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
            (user_id, username, valid_referrer)
        )
        conn.commit()
    conn.close()

def db_get_user(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, invited_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"balance": row[0], "invited_count": row[1]}
    return {"balance": 0.0, "invited_count": 0}

def db_add_bonus_to_referrer(user_id: int, order_amount: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        referrer_id = row[0]
        bonus = round(order_amount * 0.01, 2)
        if bonus > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
            conn.commit()
    conn.close()

def calculate_buy_price(stars: int) -> float:
    if stars <= 50:
        rate = 1.00  
    elif stars == 100:
        rate = 0.89  
    elif stars == 150:
        rate = 0.88  
    elif stars == 200:
        rate = 0.87  
    elif stars >= 1000:
        rate = 0.84  
    else:
        rate = 1.00 - ((stars - 50) / (1000 - 50)) * (1.00 - 0.84)
    return round(stars * rate, 2)

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
        types.KeyboardButton(text="🛡️ Відгуки"),
        types.KeyboardButton(text="💫 Розрахувати ціну")
    )
    return builder.as_markup(resize_keyboard=True)

# --- СТАРТ И КОМАНДЫ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])

    db_add_user(message.from_user.id, message.from_user.username or "", referrer_id)

    await message.answer(
        "⭐ **Вітаємо у StarsUkre!**\n\nЗамовити зірки можна від 50 грн\n\n"
        "💳 Оплата карткою\n⚡ Швидке зарахування\n💬 Підтримка після покупки",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@dp.message(Command("policy"))
async def cmd_policy(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🔗 Відкрити повну сторінку правил", url=RULES_URL))
    await message.answer(
        "📌 **Правила користування ботом StarsUkre (`@starsukre_bot`)**\n\n"
        "1. **Загальні положення:** Сервіс надає послуги з купівлі та продажу Telegram Stars (`⭐️`). Використовуючи бот, ви автоматично погоджуєтеся з цими умовами.\n\n"
        "2. **Купівля зірок:**\n"
        "• Мінімальне замовлення — **50 ⭐️**.\n"
        "• Користувач несе повну відповідальність за правильність введення `@username`.\n"
        "• Після оплати обов'язково надішліть скріншот квитанції.\n"
        "• Час обробки та зарахування: 15–30 хвилин.\n\n"
        "3. **Продаж зірок:**\n"
        "• Мінімальна сума для продажу — **500 ⭐️** через менеджера `@financialriskss`.\n\n"
        "4. **Реферальна система та бонуси:**\n"
        "• Запрошуйте друзів та отримуйте **1% ⭐️** від кожної їх покупки на свій баланс.\n\n"
        "5. **Повернення коштів:**\n"
        "• Оскільки Stars — цифровий товар надшвидкого зарахування, **після нарахування зірок повернення коштів неможливе**.",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🔗 Угода користувача (Telegraph)", url=RULES_URL))
    await message.answer(
        "ℹ️ **Інформація про сервіс StarsUkre**\n\n"
        "Швидка та безпечна купівля/продаж Telegram Stars в Україні.\n"
        "💳 Оплата за реквізитами картки\n"
        "⚡ Автоматизоване нарахування на ваш аккаунт\n"
        "🎁 Вигідна реферальна система (1% бонусів)\n\n"
        "📖 Для довідки по функціоналу використовуйте команду /help",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "❓ **Як користуватись ботом**\n\n"
        "1️⃣ Виберіть кількість Stars, яку хочете придбати.\n"
        "2️⃣ Введіть @username акаунта, на який будуть нараховані Stars.\n"
        "3️⃣ Оплатіть замовлення через зручний платіжний метод.\n"
        "4️⃣ Відправте повну квитанцію на перевірку.\n\n"
        "✅ Stars нараховуються напряму на ваш Telegram-акаунт — нічого більше робити не потрібно!",
        parse_mode="Markdown"
    )

# --- МЕНЮ ПОКУПКИ ---
@dp.message(F.text == "⭐️ Замовити Зірки")
async def process_buy_start(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="⭐️ 50 - 50 грн 🔥", callback_data="pack_50"))
    kb.row(types.InlineKeyboardButton(text="⭐️ 100 - 89 грн 🔥", callback_data="pack_100"))
    kb.row(types.InlineKeyboardButton(text="⭐️ 150 - 132 грн 🔥", callback_data="pack_150"))
    kb.row(types.InlineKeyboardButton(text="⭐️ 200 - 174 грн 🔥", callback_data="pack_200"))
    kb.row(types.InlineKeyboardButton(text="✏️ Ввести свою суму", callback_data="pack_custom"))
    kb.row(types.InlineKeyboardButton(text="💬 Читати відгуки", url=REVIEWS_URL))

    await message.answer(
        "✨ **Виберіть потрібну кількість Telegram Stars:**",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data.startswith("pack_"))
async def process_buy_pack(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    
    if action == "custom":
        await state.set_state(BotStates.buy_amount)
        await call.message.answer("Введіть кількість Stars, яку хочете придбати (мінімум 50):")
        await call.answer()
        return

    amount = int(action)
    price = calculate_buy_price(amount)
    await state.update_data(buy_amount=amount, buy_price=price)
    
    await state.set_state(BotStates.buy_username)
    await call.message.answer(
        f"💫 **Напишіть @username**, на який потрібно надіслати TG Stars.\n\n"
        f"📊 **{amount} ⭐️ — {price} грн**\n\n"
        f"⚠️ Увага! Якщо ви введете @username неправильно, зірки можуть бути відправлені іншій людині!",
        parse_mode="Markdown"
    )
    await call.answer()

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
    if message.text in ["⭐️ Замовити Зірки", "💵 Продати Зірки", "🎁 Бонуси", "🧑‍💼 Підтримка", "🛡️ Відгуки", "💫 Розрахувати ціну"]:
        await state.clear()
        return

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

@dp.message(BotStates.receipt_upload, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    order_id = str(uuid.uuid4())
    data = await state.get_data()
    amount = data.get("buy_amount", 0)
    price = data.get("buy_price", 0)
    target_username = data.get("target_username", "Не вказано")

    await message.answer(
        f"❇️ **Чек прийнято!**\n\n"
        f"📋 **Замовлення:**\n`{order_id}`\n"
        f"⏳ **Статус:** На розгляді\n\n"
        f"⌛ **Час обробки:** 15-30 хвилин",
        parse_mode="Markdown"
    )

    admin_kb = InlineKeyboardBuilder()
    admin_kb.row(
        types.InlineKeyboardButton(text="✅ Схвалити", callback_data=f"approve_{order_id}_{amount}_{target_username}_{message.from_user.id}"),
        types.InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{order_id}_{message.from_user.id}")
    )

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

@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(call: types.CallbackQuery):
    parts = call.data.split("_")
    order_id = parts[1]
    amount = int(parts[2])
    target_username = parts[3]
    user_id = int(parts[4])
    
    db_add_bonus_to_referrer(user_id, amount)

    review_kb = InlineKeyboardBuilder()
    review_kb.row(types.InlineKeyboardButton(text="📝 Залишити відгук", url=REVIEWS_URL))

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ **Замовлення схвалено!**\n\n"
                f"📋 **ID:** `{order_id}`\n"
                f"📦 **Товар:** {amount} зірок\n\n"
                f"🚀 **Ваше замовлення вже обробляється автоматично!**\n\n"
                f"🎉 **Готово! {amount} зірок надіслано на {target_username}**\n\n"
                f"✨ Дякуємо за користування StarsUkre Bot!"
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

@dp.message(F.text == "💵 Продати Зірки")
async def process_sell_start(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
    await state.set_state(BotStates.sell_amount)
    await message.answer("📬 **Продати Stars**\n\nВкажіть, будь ласка, скільки зірок ви бажаєте продати.\nМінімальна сума — 500 ⭐️")

@dp.message(BotStates.sell_amount)
async def process_sell_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть число!")
        return

    amount = int(message.text)
    if amount < 500:
        await message.answer("Мінімальне замовлення для продажу — 500 ⭐️. Спробуйте ще раз:")
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

@dp.message(F.text == "💫 Розрахувати ціну")
async def process_calc(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
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

# --- БОНУСЫ И РЕФЕРАЛКА ---
@dp.message(F.text == "🎁 Бонуси")
async def process_bonuses(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
    
    user_data = db_get_user(message.from_user.id)
    ref_link = f"https://t.me/starsukre_bot?start={message.from_user.id}"

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📤 Вивести бонуси", callback_data="withdraw_bonus"))

    await message.answer(
        f"🎁 **Реферальна система**\n\n"
        f"Запрошуй друзів за своїм посиланням і отримуй **1% ⭐️** від кожної їх купівлі на свій бонусний баланс!\n\n"
        f"👥 Запрошено друзів: **{user_data['invited_count']}**\n"
        f"⭐️ Баланс Stars: **{user_data['balance']} ⭐️**\n\n"
        f"🔗 **Твоє реферальне посилання:**\n`{ref_link}`",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "withdraw_bonus")
async def process_withdraw(call: types.CallbackQuery):
    user_data = db_get_user(call.from_user.id)
    balance = user_data["balance"]

    if balance <= 0:
        await call.answer("На вашому балансі поки немає бонусів для виведення!", show_alert=True)
        return

    await call.message.answer(
        f"📤 **Виведення бонусів**\n\n"
        f"Доступно до виведення: **{balance} ⭐️**\n\n"
        f"Для виведення бонусів зверніться до менеджера: {MANAGER_USERNAME}\n"
        f"Напишіть йому ваш ID (`{call.from_user.id}`) та суму зірок на балансі.",
        parse_mode="Markdown"
    )
    await call.answer()

@dp.message(F.text == "🧑‍💼 Підтримка")
async def process_support(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
    await message.answer(f"Напишіть нашому менеджеру: {MANAGER_USERNAME}")

@dp.message(F.text == "🛡️ Відгуки")
async def process_reviews(message: types.Message, state: FSMContext):
    db_add_user(message.from_user.id, message.from_user.username or "")
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="Читати відгуки 💬", url=REVIEWS_URL))
    await message.answer("Наші відгуки доступні за посиланням нижче 👇", reply_markup=kb.as_markup())

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    try:
        await bot.set_my_commands([
            types.BotCommand(command="start", description="Головне меню"),
            types.BotCommand(command="policy", description="Правила користування"),
            types.BotCommand(command="info", description="Інформація"),
            types.BotCommand(command="help", description="Допомога")
        ])
    except Exception as e:
        logging.error(f"Error setting commands: {e}")

    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
