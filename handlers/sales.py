from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func

from database.engine import get_session
from database.models import Product, Sale

router = Router()


# ===============================================
# Состояния
# ===============================================

class SaleStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_quantity = State()
    managing_cart = State()
    waiting_for_discount_type = State()
    waiting_for_discount_value = State()
    confirm_sale = State()


# ===============================================
# Клавиатуры
# ===============================================

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def cart_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить ещё"), KeyboardButton(text="✅ Завершить продажу")],
            [KeyboardButton(text="🗑 Очистить корзину"), KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def discount_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💯 Проценты"), KeyboardButton(text="💰 Сомони")],
            [KeyboardButton(text="🚫 Без скидки")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def confirm_sale_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить продажу"), KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# НАЧАЛО ПРОДАЖИ
# ===============================================

@router.message(F.text == "🛒 Продажа")
async def sale_start(message: types.Message, state: FSMContext):
    await state.update_data(cart=[], discount_type=None, discount_value=0)
    await state.set_state(SaleStates.waiting_for_search)

    await message.answer(
        "🛒 <b>Продажа товара</b>\n\n"
        "Введите артикул или часть названия товара для поиска:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ===============================================
# ПОИСК ТОВАРА ДЛЯ ПРОДАЖИ
# ===============================================

@router.message(SaleStates.waiting_for_search)
async def search_product_for_sale(message: types.Message, state: FSMContext):
    query = message.text.strip()

    if not query:
        await message.answer("⚠️ Введите артикул или название товара:")
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
                f"🔍 По запросу «{query}» ничего не найдено.",
                reply_markup=cancel_keyboard(),
            )
            return

        if len(products) == 1:
            product = products[0]
            await state.update_data(
                selected_product_id=product.id,
                selected_product_name=product.name,
                selected_product_article=product.article,
                selected_product_price=product.selling_price,
                selected_product_stock=product.stock_quantity
            )
            await state.set_state(SaleStates.waiting_for_quantity)
            await message.answer(
                f"📦 <b>{product.article}</b> — {product.name}\n"
                f"Цена: <b>{product.selling_price:.2f}</b> | Остаток: <b>{product.stock_quantity} шт.</b>\n\n"
                f"Введите количество для продажи:",
                parse_mode="HTML",
                reply_markup=cancel_keyboard(),
            )
            return

        # Несколько товаров
        keyboard_rows = []
        text = "🔍 <b>Найдено несколько товаров, выберите:</b>\n\n"
        for p in products:
            if p.stock_quantity == 0:
                indicator = "⚫"
            elif p.stock_quantity < 10:
                indicator = "🔴"
            else:
                indicator = "🟢"

            text += f"{indicator} <b>{p.article}</b> — {p.name} (остаток: {p.stock_quantity} шт., цена: {p.selling_price:.2f})\n"
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{indicator} {p.article} — {p.name[:35]}{'...' if len(p.name) > 35 else ''}",
                    callback_data=f"sale_select:{p.id}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

    finally:
        session.close()


# ===============================================
# ВЫБОР ТОВАРА ИЗ СПИСКА
# ===============================================

@router.callback_query(F.data.startswith("sale_select:"))
async def select_product_for_sale(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()

        if not product:
            await callback.answer("Товар не найден.", show_alert=True)
            return

        await state.update_data(
            selected_product_id=product.id,
            selected_product_name=product.name,
            selected_product_article=product.article,
            selected_product_price=product.selling_price,
            selected_product_stock=product.stock_quantity
        )
        await state.set_state(SaleStates.waiting_for_quantity)

        await callback.message.edit_text(
            f"📦 <b>{product.article}</b> — {product.name}\n"
            f"Цена: <b>{product.selling_price:.2f}</b> | Остаток: <b>{product.stock_quantity} шт.</b>\n\n"
            f"Введите количество для продажи:",
            parse_mode="HTML",
        )
        await callback.answer()

    finally:
        session.close()


# ===============================================
# ВВОД КОЛИЧЕСТВА И ДОБАВЛЕНИЕ В КОРЗИНУ
# ===============================================

@router.message(SaleStates.waiting_for_quantity)
async def process_sale_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите целое положительное число:")
        return

    data = await state.get_data()
    stock = data["selected_product_stock"]

    if quantity > stock:
        await message.answer(
            f"⚠️ Недостаточно товара! На складе: <b>{stock} шт.</b>\n"
            f"Введите другое количество:",
            parse_mode="HTML",
        )
        return

    cart = data.get("cart", [])
    cart.append({
        "product_id": data["selected_product_id"],
        "article": data["selected_product_article"],
        "name": data["selected_product_name"],
        "price": data["selected_product_price"],
        "quantity": quantity,
        "total": data["selected_product_price"] * quantity,
    })

    await state.update_data(cart=cart)
    await state.set_state(SaleStates.managing_cart)

    await show_cart(message, cart)


async def show_cart(message, cart):
    """Показывает содержимое корзины."""
    if not cart:
        await message.answer("🛒 Корзина пуста.")
        return

    text = "🛒 <b>Корзина:</b>\n\n"
    total_sum = 0
    for i, item in enumerate(cart, 1):
        text += (
            f"{i}. <b>{item['article']}</b> — {item['name']}\n"
            f"   {item['quantity']} шт. × {item['price']:.2f} = <b>{item['total']:.2f}</b>\n\n"
        )
        total_sum += item["total"]

    text += f"<b>Общая сумма: {total_sum:.2f}</b>"

    await message.answer(text, parse_mode="HTML", reply_markup=cart_keyboard())


# ===============================================
# УПРАВЛЕНИЕ КОРЗИНОЙ
# ===============================================

@router.message(SaleStates.managing_cart, F.text == "➕ Добавить ещё")
async def add_more_to_cart(message: types.Message, state: FSMContext):
    await state.set_state(SaleStates.waiting_for_search)
    await message.answer(
        "Введите артикул или название следующего товара:",
        reply_markup=cancel_keyboard(),
    )


@router.message(SaleStates.managing_cart, F.text == "🗑 Очистить корзину")
async def clear_cart(message: types.Message, state: FSMContext):
    await state.update_data(cart=[])
    await state.set_state(SaleStates.waiting_for_search)
    await message.answer(
        "🗑 Корзина очищена.\nВведите артикул или название товара:",
        reply_markup=cancel_keyboard(),
    )


@router.message(SaleStates.managing_cart, F.text == "✅ Завершить продажу")
async def ask_discount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])

    if not cart:
        await message.answer("🛒 Корзина пуста. Нечего завершать.")
        return

    total_sum = sum(item["total"] for item in cart)

    await state.set_state(SaleStates.waiting_for_discount_type)
    await message.answer(
        f"🛒 <b>Общая сумма: {total_sum:.2f}</b>\n\n"
        f"Выберите тип скидки:",
        parse_mode="HTML",
        reply_markup=discount_type_keyboard(),
    )


# ===============================================
# ВЫБОР ТИПА СКИДКИ
# ===============================================

@router.message(SaleStates.waiting_for_discount_type, F.text == "🚫 Без скидки")
async def no_discount(message: types.Message, state: FSMContext):
    await state.update_data(discount_type=None, discount_value=0)
    await show_final_check(message, state)


@router.message(SaleStates.waiting_for_discount_type, F.text.in_(["💯 Проценты", "💰 Сомони"]))
async def discount_type_selected(message: types.Message, state: FSMContext):
    discount_type = "percent" if message.text == "💯 Проценты" else "fixed"

    await state.update_data(discount_type=discount_type)
    await state.set_state(SaleStates.waiting_for_discount_value)

    if discount_type == "percent":
        await message.answer(
            "Введите процент скидки (например: 10 = 10%):",
            reply_markup=cancel_keyboard(),
        )
    else:
        await message.answer(
            "Введите сумму скидки в сомони (например: 50):",
            reply_markup=cancel_keyboard(),
        )


@router.message(SaleStates.waiting_for_discount_value)
async def process_discount_value(message: types.Message, state: FSMContext):
    try:
        value = float(message.text.strip().replace(",", "."))
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число:")
        return

    data = await state.get_data()
    discount_type = data.get("discount_type")

    if discount_type == "percent" and value > 100:
        await message.answer("⚠️ Процент скидки не может быть больше 100%:")
        return

    cart = data.get("cart", [])
    total_sum = sum(item["total"] for item in cart)

    if discount_type == "fixed" and value > total_sum:
        await message.answer(f"⚠️ Скидка не может превышать общую сумму ({total_sum:.2f}):")
        return

    await state.update_data(discount_value=value)
    await show_final_check(message, state)


async def show_final_check(message, state: FSMContext):
    """Показывает итоговый чек с учётом скидки."""
    data = await state.get_data()
    cart = data.get("cart", [])
    discount_type = data.get("discount_type")
    discount_value = data.get("discount_value", 0)

    total_sum = sum(item["total"] for item in cart)

    # Рассчитываем скидку
    if discount_type == "percent":
        discount_amount = total_sum * discount_value / 100
    elif discount_type == "fixed":
        discount_amount = discount_value
    else:
        discount_amount = 0

    final_sum = total_sum - discount_amount

    text = "🧾 <b>ИТОГОВЫЙ ЧЕК</b>\n\n"
    for i, item in enumerate(cart, 1):
        text += (
            f"{i}. <b>{item['article']}</b> — {item['name']}\n"
            f"   {item['quantity']} шт. × {item['price']:.2f} = {item['total']:.2f}\n\n"
        )

    text += f"<b>Общая сумма: {total_sum:.2f}</b>\n"

    if discount_amount > 0:
        if discount_type == "percent":
            text += f"<b>Скидка: {discount_value:.0f}% (-{discount_amount:.2f})</b>\n"
        else:
            text += f"<b>Скидка: -{discount_amount:.2f}</b>\n"

    text += f"<b>ИТОГО К ОПЛАТЕ: {final_sum:.2f}</b>"
    text += f"\n\nПодтвердите продажу:"

    await state.set_state(SaleStates.confirm_sale)
    await message.answer(text, parse_mode="HTML", reply_markup=confirm_sale_keyboard())


# ===============================================
# ПОДТВЕРЖДЕНИЕ ПРОДАЖИ
# ===============================================

@router.message(SaleStates.confirm_sale, F.text == "✅ Подтвердить продажу")
async def confirm_sale(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    discount_type = data.get("discount_type")
    discount_value = data.get("discount_value", 0)

    if not cart:
        await message.answer("🛒 Корзина пуста.")
        return

    total_sum = sum(item["total"] for item in cart)

    if discount_type == "percent":
        discount_amount = total_sum * discount_value / 100
    elif discount_type == "fixed":
        discount_amount = discount_value
    else:
        discount_amount = 0

    final_sum = total_sum - discount_amount

    session = get_session()
    try:
        for item in cart:
            product = session.query(Product).filter(Product.id == item["product_id"]).first()

            if not product:
                await message.answer(f"❌ Товар {item['article']} не найден.")
                session.rollback()
                return

            if product.stock_quantity < item["quantity"]:
                await message.answer(
                    f"❌ Недостаточно товара <b>{product.article}</b>!\n"
                    f"На складе: {product.stock_quantity} шт., нужно: {item['quantity']} шт.",
                    parse_mode="HTML",
                )
                session.rollback()
                return

            product.stock_quantity -= item["quantity"]

            # Цена за единицу с учётом скидки (пропорционально)
            item_discount_share = (item["total"] / total_sum) * discount_amount if total_sum > 0 else 0
            discounted_total = item["total"] - item_discount_share
            discounted_price = discounted_total / item["quantity"] if item["quantity"] > 0 else item["price"]

            sale = Sale(
                product_id=product.id,
                quantity=item["quantity"],
                price=round(discounted_price, 2),
            )
            session.add(sale)

        session.commit()

        # Итоговый чек
        text = "✅ <b>ПРОДАЖА ЗАВЕРШЕНА!</b>\n\n"
        text += "🧾 <b>ЧЕК:</b>\n\n"
        for item in cart:
            text += f"• {item['article']} — {item['quantity']} шт. × {item['price']:.2f} = {item['total']:.2f}\n"

        text += f"\n<b>Сумма: {total_sum:.2f}</b>"
        if discount_amount > 0:
            if discount_type == "percent":
                text += f"\n<b>Скидка: {discount_value:.0f}% (-{discount_amount:.2f})</b>"
            else:
                text += f"\n<b>Скидка: -{discount_amount:.2f}</b>"
        text += f"\n<b>ИТОГО: {final_sum:.2f}</b>"

        from handlers.start import main_keyboard
        await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())

    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

    await state.clear()


# ===============================================
# ОТМЕНА
# ===============================================

@router.message(F.text == "❌ Отмена")
async def cancel_sale(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    from handlers.start import main_keyboard
    await message.answer("❌ Продажа отменена.", reply_markup=main_keyboard())