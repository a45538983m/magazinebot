from aiogram import Router, types, F
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
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Бот запущен и готов к работе!\n\nВыберите действие:",
        reply_markup=main_keyboard(),
    )


@router.message(F.text == "ℹ️ Помощь")
async def help_command(message: types.Message):
    text = (
        "ℹ️ <b>ПОМОЩЬ ПО БОТУ</b>\n\n"
        "<b>➕ Добавить товар:</b> добавить новый товар с артикулом, брендом, местом\n"
        "<b>📦 Список товаров:</b> просмотр всех товаров, поиск, остатки\n"
        "<b>📥 Приход:</b> пополнение остатков на складе\n"
        "<b>🛒 Продажа:</b> корзина, скидки (% и сомони), продажа в долг\n"
        "<b>📊 Остатки:</b> сводка по складу, поиск по месту\n"
        "<b>🚗 Марки/Модели:</b> справочник авто, привязка совместимости\n"
        "<b>👥 Должники:</b> список должников, частичная оплата долга\n"
        "<b>📥 Выгрузить:</b> Excel-отчёты по остаткам и продажам\n"
        "<b>📈 Выручка:</b> выручка за сегодня и за месяц\n\n"
        "<b>🔍 Быстрый поиск:</b> в строке ввода наберите @SafarmagaBot и название товара\n\n"
        "По вопросам: @ваш_контакт"
    )
    await message.answer(text, parse_mode="HTML")