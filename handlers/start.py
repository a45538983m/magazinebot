from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

router = Router()

# Главное меню
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар")],
            [KeyboardButton(text="📦 Список товаров")],
            [KeyboardButton(text="📥 Приход")],
            [KeyboardButton(text="🛒 Продажа")],
            [KeyboardButton(text="📊 Остатки")],
            [KeyboardButton(text="🚗 Марки/Модели")],
            [KeyboardButton(text="👥 Должники")],
            [KeyboardButton(text="📥 Выгрузить")],
            [KeyboardButton(text="📈 Выручка")],
        ],
        resize_keyboard=True,
    )


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Бот запущен и готов к работе!\n\nВыберите действие:",
        reply_markup=main_keyboard(),
    )