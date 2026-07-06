import asyncio
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database.engine import create_tables
from handlers.start import router as start_router
from handlers.products import router as products_router


async def main():
    create_tables()
    print("База данных готова, таблицы созданы.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(products_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())