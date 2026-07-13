import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

from config import BOT_TOKEN
from database.engine import create_tables, get_session
from database.models import Product
from handlers.start import router as start_router
from handlers.products import router as products_router
from handlers.purchases import router as purchases_router
from handlers.cars import router as cars_router
from handlers.sales import router as sales_router


async def main():
    create_tables()
    print("База данных готова, таблицы созданы.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(start_router)
    dp.include_router(products_router)
    dp.include_router(purchases_router)
    dp.include_router(cars_router)
    dp.include_router(sales_router)
    # Inline-режим для поиска товаров
    @dp.inline_query()
    async def inline_search(inline_query):
        query = inline_query.query.strip()

        # Если запрос пустой — показываем подсказку
        if not query or len(query) < 1:
            await inline_query.answer(
                results=[],
                switch_pm_text="🔍 Введите артикул, название или бренд",
                switch_pm_parameter="start",
                cache_time=1,
            )
            return

        print(f"Поиск: '{query}'")  # ОТЛАДКА: видим запрос в консоли

        session = get_session()
        try:
            # Сначала попробуем найти ВООБЩЕ ВСЕ товары (для проверки)
            all_products = session.query(Product).limit(5).all()
            print(f"Всего товаров в базе (первые 5): {[(p.article, p.name, p.brand) for p in all_products]}")

            # Поиск: приводим и запрос, и поля к нижнему регистру
            query_lower = query.lower()

            # Ищем по всем полям
            products = (
    session.query(Product)
    .filter(
        (Product.article.ilike(f"%{query}%")) |
        (Product.name.ilike(f"%{query}%")) |
        (Product.brand.ilike(f"%{query}%"))
    )
    .order_by(Product.name)
    .limit(20)
    .all()
)

            print(f"Найдено товаров: {len(products)}")  # ОТЛАДКА

            if not products:
                # Попробуем альтернативный поиск — через ILIKE с lower
                from sqlalchemy import func
                products = (
                    session.query(Product)
                    .filter(
                        (func.lower(Product.article).contains(query_lower)) |
                        (func.lower(Product.name).contains(query_lower)) |
                        (func.lower(Product.brand).contains(query_lower))
                    )
                    .order_by(Product.name)
                    .limit(20)
                    .all()
                )
                print(f"Найдено через func.lower: {len(products)}")  # ОТЛАДКА

            if not products:
                await inline_query.answer(
                    results=[],
                    switch_pm_text=f"❌ По запросу '{query}' ничего не найдено",
                    switch_pm_parameter="start",
                    cache_time=1,
                )
                return

            results = []
            for p in products:
                if p.stock_quantity == 0:
                    indicator = "⚫"
                elif p.stock_quantity < 10:
                    indicator = "🔴"
                else:
                    indicator = "🟢"

                brand = f" | 🏭 {p.brand}" if p.brand else ""
                location = f" | 📍 {p.location_code}" if p.location_code else ""

                title = f"{indicator} {p.article} — {p.name[:50]}"
                description = f"Цена: {p.selling_price:.2f} | Остаток: {p.stock_quantity} шт.{location}"

                message_text = (
                    f"📋 <b>{p.article}</b> — {p.name}{brand}\n"
                    f"💰 Закуп: {p.purchase_price:.2f} | Продажа: {p.selling_price:.2f}\n"
                    f"📊 Остаток: <b>{p.stock_quantity} шт.</b> {indicator}{location}"
                )

                results.append(
                    InlineQueryResultArticle(
                        id=str(p.id),
                        title=title,
                        description=description,
                        input_message_content=InputTextMessageContent(
                            message_text=message_text,
                            parse_mode="HTML",
                        ),
                    )
                )

            await inline_query.answer(results=results, cache_time=5)

        except Exception as e:
            print(f"ОШИБКА в поиске: {e}")  # ОТЛАДКА
            await inline_query.answer(
                results=[],
                switch_pm_text=f"❌ Ошибка: {str(e)[:50]}",
                switch_pm_parameter="start",
                cache_time=1,
            )
        finally:
            session.close()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())