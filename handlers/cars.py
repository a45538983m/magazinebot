from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func

from database.engine import get_session
from database.models import Product, CarModel

router = Router()


# ===============================================
# Состояния
# ===============================================

class AddCarModelStates(StatesGroup):
    waiting_for_brand = State()
    waiting_for_model = State()
    waiting_for_year_from = State()
    waiting_for_year_to = State()
    confirm = State()


class AddCompatibilityStates(StatesGroup):
    waiting_for_product_search = State()
    waiting_for_car_selection = State()


# ===============================================
# Клавиатуры
# ===============================================

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def skip_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭️ Пропустить")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def cars_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все марки/модели")],
            [KeyboardButton(text="➕ Добавить модель")],
            [KeyboardButton(text="🔗 Привязать к товару")],
            [KeyboardButton(text="🔍 Товары по модели")],
            [KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# ГЛАВНОЕ МЕНЮ МАРОК/МОДЕЛЕЙ
# ===============================================

@router.message(F.text == "🚗 Марки/Модели")
async def cars_menu(message: types.Message):
    await message.answer(
        "🚗 <b>Справочник марок и моделей</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=cars_menu_keyboard(),
    )


# ===============================================
# СПИСОК ВСЕХ МАРОК/МОДЕЛЕЙ
# ===============================================

@router.message(F.text == "📋 Все марки/модели")
async def list_all_cars(message: types.Message):
    session = get_session()
    try:
        cars = session.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

        if not cars:
            await message.answer("📋 Справочник пуст. Добавьте модели.")
            return

        brands = {}
        for car in cars:
            if car.brand not in brands:
                brands[car.brand] = []
            brands[car.brand].append(car)

        text = "🚗 <b>Марки и модели:</b>\n\n"
        for brand, models in brands.items():
            text += f"<b>{brand}</b>\n"
            for m in models[:10]:
                years = ""
                if m.year_from and m.year_to:
                    years = f" ({m.year_from}–{m.year_to})"
                elif m.year_from:
                    years = f" (с {m.year_from})"
                elif m.year_to:
                    years = f" (до {m.year_to})"
                text += f"  • {m.model}{years}\n"
            if len(models) > 10:
                text += f"  ... и ещё {len(models) - 10} моделей\n"
            text += "\n"

        await message.answer(text, parse_mode="HTML")

    finally:
        session.close()


# ===============================================
# ДОБАВЛЕНИЕ МОДЕЛИ
# ===============================================

@router.message(F.text == "➕ Добавить модель")
async def add_car_start(message: types.Message, state: FSMContext):
    await state.set_state(AddCarModelStates.waiting_for_brand)
    await message.answer(
        "Введите марку автомобиля (например: ВАЗ, Toyota, BMW):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddCarModelStates.waiting_for_brand)
async def process_car_brand(message: types.Message, state: FSMContext):
    brand = message.text.strip()

    if not brand:
        await message.answer("⚠️ Марка не может быть пустой. Введите марку:")
        return

    await state.update_data(brand=brand)
    await state.set_state(AddCarModelStates.waiting_for_model)
    await message.answer(
        f"Марка: <b>{brand}</b>\n\n"
        f"Введите модель (например: 2108, Corolla, X5):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddCarModelStates.waiting_for_model)
async def process_car_model(message: types.Message, state: FSMContext):
    model = message.text.strip()

    if not model:
        await message.answer("⚠️ Модель не может быть пустой. Введите модель:")
        return

    data = await state.get_data()
    session = get_session()
    try:
        existing = session.query(CarModel).filter(
            func.lower(CarModel.brand) == data["brand"].lower(),
            func.lower(CarModel.model) == model.lower()
        ).first()
        if existing:
            await message.answer(
                f"⚠️ Модель {data['brand']} {model} уже существует!"
            )
            return
    finally:
        session.close()

    await state.update_data(model=model)
    await state.set_state(AddCarModelStates.waiting_for_year_from)
    await message.answer(
        f"Марка: <b>{data['brand']}</b>\n"
        f"Модель: <b>{model}</b>\n\n"
        f"Введите год начала выпуска (или нажмите Пропустить):",
        parse_mode="HTML",
        reply_markup=skip_keyboard(),
    )


@router.message(AddCarModelStates.waiting_for_year_from)
async def process_year_from(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text == "⏭️ Пропустить":
        year_from = None
    else:
        try:
            year_from = int(text)
            if year_from < 1900 or year_from > 2100:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите корректный год (например: 1984):")
            return

    await state.update_data(year_from=year_from)
    await state.set_state(AddCarModelStates.waiting_for_year_to)
    await message.answer(
        "Введите год окончания выпуска (или нажмите Пропустить):",
        reply_markup=skip_keyboard(),
    )


@router.message(AddCarModelStates.waiting_for_year_to)
async def process_year_to(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text == "⏭️ Пропустить":
        year_to = None
    else:
        try:
            year_to = int(text)
            if year_to < 1900 or year_to > 2100:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите корректный год (например: 2003):")
            return

    await state.update_data(year_to=year_to)
    data = await state.get_data()

    years_text = ""
    if data.get("year_from") and data.get("year_to"):
        years_text = f" ({data['year_from']}–{data['year_to']})"
    elif data.get("year_from"):
        years_text = f" (с {data['year_from']})"
    elif data.get("year_to"):
        years_text = f" (до {data['year_to']})"

    await state.set_state(AddCarModelStates.confirm)

    await message.answer(
        f"📋 <b>Подтвердите модель:</b>\n\n"
        f"Марка: <b>{data['brand']}</b>\n"
        f"Модель: <b>{data['model']}{years_text}</b>\n\n"
        f"Сохранить?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Сохранить"), KeyboardButton(text="❌ Отмена")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(AddCarModelStates.confirm, F.text == "✅ Сохранить")
async def save_car_model(message: types.Message, state: FSMContext):
    data = await state.get_data()

    session = get_session()
    try:
        car = CarModel(
            brand=data["brand"],
            model=data["model"],
            year_from=data.get("year_from"),
            year_to=data.get("year_to"),
        )
        session.add(car)
        session.commit()

        years_text = ""
        if car.year_from and car.year_to:
            years_text = f" ({car.year_from}–{car.year_to})"
        elif car.year_from:
            years_text = f" (с {car.year_from})"

        await message.answer(
            f"✅ Модель сохранена: <b>{car.brand} {car.model}{years_text}</b>",
            parse_mode="HTML",
            reply_markup=cars_menu_keyboard(),
        )
    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

    await state.clear()


# ===============================================
# ПРИВЯЗКА ТОВАРА К МОДЕЛИ
# ===============================================

@router.message(F.text == "🔗 Привязать к товару")
async def link_product_start(message: types.Message, state: FSMContext):
    await state.set_state(AddCompatibilityStates.waiting_for_product_search)

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Быстрый поиск товара",
                    switch_inline_query_current_chat=""
                )
            ]
        ]
    )

    await message.answer(
        "🔗 <b>Привязка товара к модели авто</b>\n\n"
        "🔍 <b>Два способа найти товар:</b>\n\n"
        "<b>1. Быстрый поиск (кнопка ниже)</b>\n"
        "Нажмите кнопку — в строке ввода появится <b>@SafarmagaBot</b>.\n"
        "Введите артикул или название — бот покажет список товаров.\n\n"
        "<b>2. Обычный поиск</b>\n"
        "Введите артикул или часть названия товара прямо в чат.\n\n"
        "Для отмены нажмите кнопку ниже.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )

    await message.answer(
        "Нажмите для быстрого поиска:",
        reply_markup=inline_kb,
    )


@router.message(AddCompatibilityStates.waiting_for_product_search)
async def search_product_for_link(message: types.Message, state: FSMContext):
    query = message.text.strip()

    if not query:
        await message.answer("⚠️ Введите артикул или название:")
        return

    session = get_session()
    try:
        products = (
    session.query(Product)
    .filter(
        (Product.article.ilike(f"%{query}%")) |
        (Product.name.ilike(f"%{query}%")) |
        (Product.brand.ilike(f"%{query}%"))
    )
    .order_by(Product.name)
    .limit(10)
    .all()
)

        if not products:
            await message.answer(
                f"🔍 По запросу «{query}» ничего не найдено.\n"
                f"Попробуйте другой запрос или нажмите Отмена:",
                reply_markup=cancel_keyboard(),
            )
            return

        if len(products) == 1:
            product = products[0]
            await state.update_data(
                product_id=product.id,
                product_name=product.name,
                product_article=product.article
            )
            await state.set_state(AddCompatibilityStates.waiting_for_car_selection)
            await show_cars_for_selection(message, state, product)
            return

        # Несколько товаров
        keyboard_rows = []
        text = "🔍 <b>Найдено несколько товаров, выберите:</b>\n\n"
        for p in products:
            brand = f" | 🏭 {p.brand}" if p.brand else ""
            if p.stock_quantity == 0:
                indicator = "⚫"
            elif p.stock_quantity < 10:
                indicator = "🔴"
            else:
                indicator = "🟢"
            text += f"{indicator} <b>{p.article}</b> — {p.name}{brand} (остаток: {p.stock_quantity} шт.)\n"
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{indicator} {p.article} — {p.name[:35]}{'...' if len(p.name) > 35 else ''}",
                    callback_data=f"link_product:{p.id}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

    finally:
        session.close()


@router.callback_query(F.data.startswith("link_product:"))
async def select_product_for_link(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()

        if not product:
            await callback.answer("Товар не найден.", show_alert=True)
            return

        await state.update_data(
            product_id=product.id,
            product_name=product.name,
            product_article=product.article
        )
        await state.set_state(AddCompatibilityStates.waiting_for_car_selection)

        # Сначала отвечаем на callback
        await callback.answer()

        # Удаляем сообщение со списком товаров
        try:
            await callback.message.delete()
        except:
            pass

        # Показываем выбор марок НОВЫМ сообщением
        session2 = get_session()
        try:
            cars = session2.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

            if not cars:
                await callback.message.answer(
                    "📋 Справочник моделей пуст. Сначала добавьте модели через меню «🚗 Марки/Модели».",
                    reply_markup=cars_menu_keyboard(),
                )
                await state.clear()
                return

            brands = {}
            for car in cars:
                if car.brand not in brands:
                    brands[car.brand] = []
                brands[car.brand].append(car)

            text = f"🔗 Товар: <b>{product.article}</b> — {product.name}\n\n"
            text += "<b>Выберите марку, затем модель:</b>\n\n"

            keyboard_rows = []
            for brand in sorted(brands.keys()):
                keyboard_rows.append([
                    InlineKeyboardButton(
                        text=f"🚗 {brand}",
                        callback_data=f"link_brand:{brand}"
                    )
                ])

            inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

            # Отправляем новое сообщение (не edit, потому что старое удалено)
            await callback.message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

        finally:
            session2.close()

    finally:
        session.close()


async def show_cars_for_selection(message, state: FSMContext, product):
    """Показывает список марок/моделей для выбора."""
    session = get_session()
    try:
        cars = session.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

        if not cars:
            await message.answer(
                "📋 Справочник моделей пуст. Сначала добавьте модели через меню «🚗 Марки/Модели».",
                reply_markup=cars_menu_keyboard(),
            )
            await state.clear()
            return

        brands = {}
        for car in cars:
            if car.brand not in brands:
                brands[car.brand] = []
            brands[car.brand].append(car)

        text = f"🔗 Товар: <b>{product.article}</b> — {product.name}\n\n"
        text += "<b>Выберите марку, затем модель:</b>\n\n"

        keyboard_rows = []
        for brand in sorted(brands.keys()):
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"🚗 {brand}",
                    callback_data=f"link_brand:{brand}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

    finally:
        session.close()


@router.callback_query(F.data.startswith("link_brand:"))
async def show_models_for_brand(callback: types.CallbackQuery):
    brand = callback.data.split(":")[1]

    session = get_session()
    try:
        models = session.query(CarModel).filter(
            func.lower(CarModel.brand) == brand.lower()
        ).order_by(CarModel.model).all()

        if not models:
            await callback.answer("Нет моделей для этой марки.", show_alert=True)
            return

        text = f"🚗 <b>{brand}</b>\n\nВыберите модель:\n\n"
        keyboard_rows = []

        for m in models[:20]:
            years = ""
            if m.year_from and m.year_to:
                years = f" ({m.year_from}–{m.year_to})"
            elif m.year_from:
                years = f" (с {m.year_from})"
            elif m.year_to:
                years = f" (до {m.year_to})"

            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{m.model}{years}",
                    callback_data=f"link_model:{m.id}"
                )
            ])

        keyboard_rows.append([
            InlineKeyboardButton(text="🔙 Назад к маркам", callback_data="link_back_to_brands")
        ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline_kb)
        await callback.answer()

    finally:
        session.close()


@router.callback_query(F.data == "link_back_to_brands")
async def back_to_brands(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_name = data.get("product_name", "?")
    product_article = data.get("product_article", "?")

    session = get_session()
    try:
        cars = session.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

        brands = {}
        for car in cars:
            if car.brand not in brands:
                brands[car.brand] = []
            brands[car.brand].append(car)

        text = f"🔗 Товар: <b>{product_article}</b> — {product_name}\n\n"
        text += "<b>Выберите марку:</b>\n\n"

        keyboard_rows = []
        for brand in sorted(brands.keys()):
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"🚗 {brand}",
                    callback_data=f"link_brand:{brand}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline_kb)
        await callback.answer()

    finally:
        session.close()


@router.callback_query(F.data.startswith("link_model:"))
async def link_product_to_model(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    product_id = data.get("product_id")

    if not product_id:
        await callback.answer("Ошибка: товар не выбран. Начните заново.", show_alert=True)
        await state.clear()
        return

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()
        car = session.query(CarModel).filter(CarModel.id == car_id).first()

        if not product or not car:
            await callback.answer("Ошибка: товар или модель не найдены.", show_alert=True)
            return

        if car in product.compatible_models:
            await callback.answer(f"Товар уже привязан к {car.brand} {car.model}!", show_alert=True)
            return

        product.compatible_models.append(car)
        session.commit()

        years = ""
        if car.year_from and car.year_to:
            years = f" ({car.year_from}–{car.year_to})"
        elif car.year_from:
            years = f" (с {car.year_from})"

        await callback.message.edit_text(
            f"✅ <b>Связь добавлена!</b>\n\n"
            f"Товар: <b>{product.article}</b> — {product.name}\n"
            f"Подходит для: <b>{car.brand} {car.model}{years}</b>",
            parse_mode="HTML",
        )
        await callback.answer("✅ Связь добавлена!")

    except Exception as e:
        session.rollback()
        await callback.answer(f"Ошибка: {e}", show_alert=True)
    finally:
        session.close()

    await state.clear()


# ===============================================
# ПОИСК ТОВАРОВ ПО МОДЕЛИ
# ===============================================

@router.message(F.text == "🔍 Товары по модели")
async def search_by_car_start(message: types.Message):
    session = get_session()
    try:
        cars = session.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

        if not cars:
            await message.answer("📋 Справочник моделей пуст.")
            return

        brands = {}
        for car in cars:
            if car.brand not in brands:
                brands[car.brand] = []
            brands[car.brand].append(car)

        text = "🔍 <b>Поиск товаров по модели авто</b>\n\nВыберите марку:\n\n"
        keyboard_rows = []

        for brand in sorted(brands.keys()):
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"🚗 {brand} ({len(brands[brand])} моделей)",
                    callback_data=f"search_brand:{brand}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

    finally:
        session.close()


@router.callback_query(F.data.startswith("search_brand:"))
async def search_models_for_brand(callback: types.CallbackQuery):
    brand = callback.data.split(":")[1]

    session = get_session()
    try:
        models = session.query(CarModel).filter(
            func.lower(CarModel.brand) == brand.lower()
        ).order_by(CarModel.model).all()

        text = f"🚗 <b>{brand}</b>\n\nВыберите модель:\n\n"
        keyboard_rows = []

        for m in models[:20]:
            years = ""
            if m.year_from and m.year_to:
                years = f" ({m.year_from}–{m.year_to})"
            elif m.year_from:
                years = f" (с {m.year_from})"

            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{m.model}{years}",
                    callback_data=f"search_model:{m.id}"
                )
            ])

        keyboard_rows.append([
            InlineKeyboardButton(text="🔙 Назад к маркам", callback_data="search_back_to_brands")
        ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline_kb)
        await callback.answer()

    finally:
        session.close()


@router.callback_query(F.data == "search_back_to_brands")
async def search_back_to_brands(callback: types.CallbackQuery):
    session = get_session()
    try:
        cars = session.query(CarModel).order_by(CarModel.brand, CarModel.model).all()

        brands = {}
        for car in cars:
            if car.brand not in brands:
                brands[car.brand] = []
            brands[car.brand].append(car)

        text = "🔍 <b>Поиск товаров по модели авто</b>\n\nВыберите марку:\n\n"
        keyboard_rows = []

        for brand in sorted(brands.keys()):
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"🚗 {brand} ({len(brands[brand])} моделей)",
                    callback_data=f"search_brand:{brand}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline_kb)
        await callback.answer()

    finally:
        session.close()


@router.callback_query(F.data.startswith("search_model:"))
async def show_products_for_model(callback: types.CallbackQuery):
    car_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        car = session.query(CarModel).filter(CarModel.id == car_id).first()

        if not car:
            await callback.answer("Модель не найдена.", show_alert=True)
            return

        products = car.products

        if not products:
            years = ""
            if car.year_from and car.year_to:
                years = f" ({car.year_from}–{car.year_to})"
            elif car.year_from:
                years = f" (с {car.year_from})"

            await callback.message.edit_text(
                f"🔍 <b>{car.brand} {car.model}{years}</b>\n\n"
                f"❌ Нет привязанных товаров.",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        years = ""
        if car.year_from and car.year_to:
            years = f" ({car.year_from}–{car.year_to})"
        elif car.year_from:
            years = f" (с {car.year_from})"

        text = f"🔍 <b>{car.brand} {car.model}{years}</b>\n\n"
        text += f"<b>Подходящие товары ({len(products)}):</b>\n\n"

        for p in products:
            if p.stock_quantity == 0:
                indicator = "⚫"
            elif p.stock_quantity < 10:
                indicator = "🔴"
            else:
                indicator = "🟢"

            brand = f" | 🏭 {p.brand}" if p.brand else ""
            location = f" | 📍 {p.location_code}" if p.location_code else ""

            text += (
                f"{indicator} <b>{p.article}</b> — {p.name}{brand}\n"
                f"   Цена: {p.selling_price:.2f} | Остаток: {p.stock_quantity} шт.{location}\n\n"
            )

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    finally:
        session.close()


# ===============================================
# ОТМЕНА
# ===============================================

@router.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    await message.answer(
        "🚗 <b>Справочник марок и моделей</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=cars_menu_keyboard(),
    )