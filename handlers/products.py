from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.engine import get_session
from database.models import Product

router = Router()


# Состояния для живого поиска
class LiveSearchStates(StatesGroup):
    typing = State()


# Состояния для добавления товара
class AddProductStates(StatesGroup):
    waiting_for_article = State()
    waiting_for_name = State()
    waiting_for_brand = State()
    waiting_for_purchase_price = State()
    waiting_for_selling_price = State()
    waiting_for_location = State()
    confirm = State()


# Состояния для поиска (старый, не используется, но оставлен)
class SearchStates(StatesGroup):
    waiting_for_search_query = State()


# Клавиатура отмены (для добавления товара)
def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


# Клавиатура с кнопкой Назад (для живого поиска)
def back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True,
    )


# Клавиатура для списка товаров
def products_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все товары"), KeyboardButton(text="🔍 Поиск")],
            [KeyboardButton(text="🔴 Критичные остатки"), KeyboardButton(text="🟢 В наличии")],
            [KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# ГЛАВНОЕ МЕНЮ ТОВАРОВ
# ===============================================

@router.message(F.text == "📦 Список товаров")
async def products_menu(message: types.Message):
    await message.answer(
        "📦 <b>Список товаров</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=products_menu_keyboard(),
    )


@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: types.Message):
    from handlers.start import main_keyboard
    await message.answer("Главное меню:", reply_markup=main_keyboard())


# ===============================================
# ВСЕ ТОВАРЫ (с цветовой индикацией)
# ===============================================

@router.message(F.text == "📋 Все товары")
async def list_all_products(message: types.Message):
    session = get_session()
    try:
        products = session.query(Product).order_by(Product.name).all()

        if not products:
            await message.answer("📦 Список товаров пуст.")
            return

        text = "📋 <b>Все товары:</b>\n\n"

        red_products = [p for p in products if p.stock_quantity < 10]
        green_products = [p for p in products if p.stock_quantity >= 10]

        if red_products:
            text += "🔴 <b>Менее 10 шт (нужно пополнить):</b>\n\n"
            for p in red_products:
                brand = f" | 🏭 {p.brand}" if p.brand else ""
                location = f" | 📍 {p.location_code}" if p.location_code else ""
                text += (
                    f"🔴 <b>{p.article}</b> — {p.name}{brand}\n"
                    f"   Цена: {p.selling_price:.2f} | Остаток: <b>{p.stock_quantity} шт.</b>{location}\n\n"
                )

        if green_products:
            text += "🟢 <b>10 и более шт (достаточно):</b>\n\n"
            for p in green_products[:20]:
                brand = f" | 🏭 {p.brand}" if p.brand else ""
                location = f" | 📍 {p.location_code}" if p.location_code else ""
                text += (
                    f"🟢 <b>{p.article}</b> — {p.name}{brand}\n"
                    f"   Цена: {p.selling_price:.2f} | Остаток: {p.stock_quantity} шт.{location}\n\n"
                )

            if len(green_products) > 20:
                text += f"... и ещё {len(green_products) - 20} товаров с достаточным остатком.\n"
                text += "Используйте 🔍 Поиск для проверки конкретного товара."

        await message.answer(text, parse_mode="HTML")

    finally:
        session.close()


# ===============================================
# КРИТИЧНЫЕ ОСТАТКИ (только красные)
# ===============================================

@router.message(F.text == "🔴 Критичные остатки")
async def list_critical_products(message: types.Message):
    session = get_session()
    try:
        products = session.query(Product).filter(Product.stock_quantity < 10).order_by(Product.stock_quantity).all()

        if not products:
            await message.answer("✅ Все товары в достаточном количестве (10+ шт).")
            return

        text = "🔴 <b>Товары с критичным остатком (менее 10 шт):</b>\n\n"
        for p in products:
            brand = f" | 🏭 {p.brand}" if p.brand else ""
            location = f" | 📍 {p.location_code}" if p.location_code else ""
            text += (
                f"🔴 <b>{p.article}</b> — {p.name}{brand}\n"
                f"   Цена: {p.selling_price:.2f} | Остаток: <b>{p.stock_quantity} шт.</b>{location}\n\n"
            )

        await message.answer(text, parse_mode="HTML")

    finally:
        session.close()


# ===============================================
# ТОВАРЫ В НАЛИЧИИ (только зелёные)
# ===============================================

@router.message(F.text == "🟢 В наличии")
async def list_good_products(message: types.Message):
    session = get_session()
    try:
        products = session.query(Product).filter(Product.stock_quantity >= 10).order_by(Product.name).all()

        if not products:
            await message.answer("❌ Нет товаров с достаточным остатком (10+ шт).")
            return

        text = "🟢 <b>Товары в достаточном количестве (10+ шт):</b>\n\n"
        for p in products[:25]:
            brand = f" | 🏭 {p.brand}" if p.brand else ""
            location = f" | 📍 {p.location_code}" if p.location_code else ""
            text += (
                f"🟢 <b>{p.article}</b> — {p.name}{brand}\n"
                f"   Цена: {p.selling_price:.2f} | Остаток: {p.stock_quantity} шт.{location}\n\n"
            )

        if len(products) > 25:
            text += f"... и ещё {len(products) - 25} товаров."

        await message.answer(text, parse_mode="HTML")

    finally:
        session.close()


# ===============================================
# ЖИВОЙ ПОИСК (автодополнение)
# ===============================================

@router.message(F.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(LiveSearchStates.typing)
    await state.update_data(last_search_msg_id=None)
    await message.answer(
        "🔍 <b>Живой поиск</b>\n\n"
        "Вводите буквы — бот покажет совпадения.\n"
        "Чем больше букв, тем точнее результат.\n\n"
        "Для выхода нажмите кнопку Назад.",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


@router.message(LiveSearchStates.typing, F.text == "🔙 Назад")
async def back_from_search(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📦 <b>Список товаров</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=products_menu_keyboard(),
    )


@router.message(LiveSearchStates.typing)
async def live_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    data = await state.get_data()
    last_msg_id = data.get("last_search_msg_id")

    # Удаляем предыдущее сообщение с результатами
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except:
            pass

    if not query or len(query) < 1:
        await state.update_data(last_search_msg_id=None)
        return

    session = get_session()
    try:
        products = (
            session.query(Product)
            .filter(
                (Product.name.ilike(f"{query}%")) |
                (Product.article.ilike(f"{query}%")) |
                (Product.name.ilike(f"%{query}%")) |
                (Product.article.ilike(f"%{query}%")) |
                (Product.brand.ilike(f"{query}%"))
            )
            .order_by(Product.name)
            .limit(15)
            .all()
        )

        if not products:
            not_found_msg = await message.answer(
                f"🔍 По запросу «<b>{query}</b>» ничего не найдено.\n"
                f"Продолжайте ввод или нажмите Назад.",
                parse_mode="HTML",
                reply_markup=back_keyboard(),
            )
            await state.update_data(last_search_msg_id=not_found_msg.message_id)
            return

        text = f"🔍 <b>Поиск: «{query}»</b> — найдено {len(products)}:\n\n"
        keyboard_rows = []

        for p in products:
            if p.stock_quantity == 0:
                indicator = "⚫"
            elif p.stock_quantity < 10:
                indicator = "🔴"
            else:
                indicator = "🟢"

            brand = f" | {p.brand}" if p.brand else ""
            location = f" | 📍 {p.location_code}" if p.location_code else ""

            text += (
                f"{indicator} <b>{p.article}</b> — {p.name}{brand}\n"
                f"   Цена: {p.selling_price:.2f} | Остаток: {p.stock_quantity} шт.{location}\n\n"
            )

            callback_data = f"product_info:{p.id}"
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{indicator} {p.article} — {p.name[:30]}{'...' if len(p.name) > 30 else ''}",
                    callback_data=callback_data
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        result_msg = await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)
        await state.update_data(last_search_msg_id=result_msg.message_id)

    finally:
        session.close()


# ===============================================
# КАРТОЧКА ТОВАРА (по клику в поиске)
# ===============================================

@router.callback_query(F.data.startswith("product_info:"))
async def show_product_info(callback: types.CallbackQuery):
    product_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()

        if not product:
            await callback.answer("Товар не найден.", show_alert=True)
            return

        if product.stock_quantity == 0:
            indicator = "⚫ Нет в наличии"
        elif product.stock_quantity < 10:
            indicator = "🔴 Мало (менее 10)"
        else:
            indicator = "🟢 Достаточно"

        brand_text = f"\n🏭 Бренд: <b>{product.brand}</b>" if product.brand else ""
        location_text = f"\n📍 Место: <b>{product.location_code}</b>" if product.location_code else ""

        # Совместимые модели
        compat_text = ""
        if product.compatible_models:
            models = []
            for cm in product.compatible_models:
                years = ""
                if cm.year_from and cm.year_to:
                    years = f" ({cm.year_from}–{cm.year_to})"
                elif cm.year_from:
                    years = f" (с {cm.year_from})"
                elif cm.year_to:
                    years = f" (до {cm.year_to})"
                models.append(f"{cm.brand} {cm.model}{years}")
            compat_text = "\n🚗 <b>Подходит для:</b>\n" + "\n".join(f"  • {m}" for m in models[:5])
            if len(models) > 5:
                compat_text += f"\n  ... и ещё {len(models) - 5}"

        text = (
            f"📋 <b>Информация о товаре:</b>\n\n"
            f"📌 Артикул: <b>{product.article}</b>\n"
            f"📦 Название: <b>{product.name}</b>{brand_text}\n"
            f"💰 Закупочная цена: <b>{product.purchase_price:.2f}</b>\n"
            f"💵 Розничная цена: <b>{product.selling_price:.2f}</b>\n"
            f"📊 Остаток: <b>{product.stock_quantity} шт.</b> ({indicator}){location_text}\n"
            f"{compat_text}"
        )

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    finally:
        session.close()


# ===============================================
# ДОБАВЛЕНИЕ ТОВАРА
# ===============================================

@router.message(F.text == "➕ Добавить товар")
async def add_product_start(message: types.Message, state: FSMContext):
    await state.set_state(AddProductStates.waiting_for_article)
    await message.answer(
        "Введите артикул товара (например: 2108-1003010):",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    from handlers.start import main_keyboard
    await message.answer("❌ Действие отменено.", reply_markup=main_keyboard())


@router.message(AddProductStates.waiting_for_article)
async def process_article(message: types.Message, state: FSMContext):
    article = message.text.strip()

    if not article:
        await message.answer("⚠️ Артикул не может быть пустым. Введите артикул:")
        return

    session = get_session()
    try:
        existing = session.query(Product).filter(Product.article == article).first()
        if existing:
            await message.answer(
                f"⚠️ Товар с артикулом {article} уже существует!\n"
                f"Название: {existing.name}\n"
                f"Введите другой артикул:"
            )
            return
    finally:
        session.close()

    await state.update_data(article=article)
    await state.set_state(AddProductStates.waiting_for_name)
    await message.answer("Введите название товара:")


@router.message(AddProductStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()

    if not name:
        await message.answer("⚠️ Название не может быть пустым. Введите название:")
        return

    await state.update_data(name=name)
    await state.set_state(AddProductStates.waiting_for_brand)
    await message.answer(
        "Введите бренд/производителя (например: Bosch, Febest, CTR)\n"
        "Или нажмите ⏭️ Пропустить:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⏭️ Пропустить")],
                [KeyboardButton(text="❌ Отмена")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(AddProductStates.waiting_for_brand)
async def process_brand(message: types.Message, state: FSMContext):
    brand = message.text.strip()

    if brand == "⏭️ Пропустить":
        brand = None
    elif brand == "❌ Отмена":
        await state.clear()
        from handlers.start import main_keyboard
        await message.answer("❌ Действие отменено.", reply_markup=main_keyboard())
        return

    await state.update_data(brand=brand)
    await state.set_state(AddProductStates.waiting_for_purchase_price)
    await message.answer(
        "Введите закупочную цену (например: 150.50):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddProductStates.waiting_for_purchase_price)
async def process_purchase_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например: 150.50):")
        return

    await state.update_data(purchase_price=price)
    await state.set_state(AddProductStates.waiting_for_selling_price)
    await message.answer(
        "Введите розничную цену (например: 250.00):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddProductStates.waiting_for_selling_price)
async def process_selling_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например: 250.00):")
        return

    await state.update_data(selling_price=price)
    await state.set_state(AddProductStates.waiting_for_location)
    await message.answer(
        "Введите место на полке (например: A-3, B-12)\n"
        "Или нажмите ⏭️ Пропустить:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⏭️ Пропустить")],
                [KeyboardButton(text="❌ Отмена")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(AddProductStates.waiting_for_location)
async def process_location(message: types.Message, state: FSMContext):
    location = message.text.strip()

    if location == "⏭️ Пропустить":
        location = None
    elif location == "❌ Отмена":
        await state.clear()
        from handlers.start import main_keyboard
        await message.answer("❌ Действие отменено.", reply_markup=main_keyboard())
        return

    await state.update_data(location=location)
    data = await state.get_data()

    brand_text = data["brand"] if data.get("brand") else "не указан"
    location_text = data["location"] if data.get("location") else "не указано"
    await state.set_state(AddProductStates.confirm)

    await message.answer(
        f"📋 <b>Подтвердите данные товара:</b>\n\n"
        f"Артикул: <b>{data['article']}</b>\n"
        f"Название: <b>{data['name']}</b>\n"
        f"Бренд: <b>{brand_text}</b>\n"
        f"Закупочная цена: <b>{data['purchase_price']:.2f}</b>\n"
        f"Розничная цена: <b>{data['selling_price']:.2f}</b>\n"
        f"Место: <b>{location_text}</b>\n\n"
        f"Сохранить товар?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Сохранить"), KeyboardButton(text="❌ Отмена")],
            ],
            resize_keyboard=True,
        ),
    )


@router.message(AddProductStates.confirm, F.text == "✅ Сохранить")
async def save_product(message: types.Message, state: FSMContext):
    data = await state.get_data()

    session = get_session()
    try:
        product = Product(
            article=data["article"],
            name=data["name"],
            brand=data.get("brand"),
            purchase_price=data["purchase_price"],
            selling_price=data["selling_price"],
            stock_quantity=0,
            location_code=data.get("location"),
        )
        session.add(product)
        session.commit()

        brand_text = f"\n🏭 Бренд: {data['brand']}" if data.get("brand") else ""
        location_text = f"\n📍 Место: {data['location']}" if data.get("location") else ""
        from handlers.start import main_keyboard
        await message.answer(
            f"✅ Товар сохранён!\n\n"
            f"Артикул: <b>{product.article}</b>\n"
            f"Название: <b>{product.name}</b>{brand_text}\n"
            f"Цена продажи: <b>{product.selling_price:.2f}</b>{location_text}",
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Ошибка при сохранении: {e}")
    finally:
        session.close()

    await state.clear()