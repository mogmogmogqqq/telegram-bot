import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BOT_TOKEN = "8830743683:AAEpsT5xrduXGgYzRLTDTHiqgTZAxUVk8cA"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "⭐ **Вітаємо у StarsUkr!**\n\nЗамовити зірки можна від 50 грн\n\n"
        "💳 Оплата карткою\n⚡ Швидке зарахування\n💬 Підтримка після покупки",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@dp.message()
async def handle_buttons(message: types.Message):
    if message.text == "⭐️ Замовити Зірки":
        await message.answer("Переходим к оформлению заказа...")
    elif message.text == "💵 Продати Зірки":
        await message.answer("Раздел продажи звезд...")
    elif message.text == "🎁 Бонуси":
        await message.answer("Ваши доступные бонусы...")
    elif message.text == "🧑‍💼 Підтримка":
        await message.answer("Напишите нашему менеджеру: @admin")
    else:
        await message.answer("Выберите нужный пункт из меню ниже 👇")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
