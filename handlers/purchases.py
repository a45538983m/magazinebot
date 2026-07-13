from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func

from database.engine import get_session
from database.models import Product, Purchase

router = Router()


# Состояния для прихода
class PurchaseStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_quantity = State()
    confirm = State()


# Клавиатура отмены
def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


# Клавиатура подтверждения
def confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Подтвердить"), KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# НАЧАЛО ПРИХОДА
# ===============================================

@router.message(F.text == "📥 Приход")
async def purchase_start(message: types.Message, state: FSMContext):
    await state.set_state(PurchaseStates.waiting_for_search)

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
        "📥 <b>Приход товара</b>\n\n"
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


# ===============================================
# ПОИСК ТОВАРА ДЛЯ ПРИХОДА (обычный, регистронезависимый)
# ===============================================

@router.message(PurchaseStates.waiting_for_search)
async def search_product_for_purchase(message: types.Message, state: FSMContext):
    query = message.text.strip()

    if not query:
        await message.answer("⚠️ Введите артикул или название товара:")
        return

    session = get_session()
    try:
        # РЕГИСТРОНЕЗАВИСИМЫЙ ПОИСК
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
            await state.update_data(product_id=product.id, product_name=product.name, product_article=product.article)
            await state.set_state(PurchaseStates.waiting_for_quantity)
            await message.answer(
                f"📦 Выбран товар:\n\n"
                f"<b>{product.article}</b> — {product.name}\n"
                f"Текущий остаток: <b>{product.stock_quantity} шт.</b>\n\n"
                f"Введите количество для прихода:",
                parse_mode="HTML",
                reply_markup=cancel_keyboard(),
            )
            return

        keyboard_rows = []
        text = "🔍 <b>Найдено несколько товаров, выберите:</b>\n\n"
        for p in products:
            if p.stock_quantity == 0:
                indicator = "⚫"
            elif p.stock_quantity < 10:
                indicator = "🔴"
            else:
                indicator = "🟢"

            text += f"{indicator} <b>{p.article}</b> — {p.name} (остаток: {p.stock_quantity} шт.)\n"
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{indicator} {p.article} — {p.name[:35]}{'...' if len(p.name) > 35 else ''}",
                    callback_data=f"purchase_select:{p.id}"
                )
            ])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)

    finally:
        session.close()


# ===============================================
# ВЫБОР ТОВАРА ИЗ СПИСКА (inline-кнопка)
# ===============================================

@router.callback_query(F.data.startswith("purchase_select:"))
async def select_product_for_purchase(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()

        if not product:
            await callback.answer("Товар не найден.", show_alert=True)
            return

        await state.update_data(product_id=product.id, product_name=product.name, product_article=product.article)
        await state.set_state(PurchaseStates.waiting_for_quantity)

        await callback.message.edit_text(
            f"📦 Выбран товар:\n\n"
            f"<b>{product.article}</b> — {product.name}\n"
            f"Текущий остаток: <b>{product.stock_quantity} шт.</b>\n\n"
            f"Введите количество для прихода:",
            parse_mode="HTML",
        )
        await callback.answer()

    finally:
        session.close()


# ===============================================
# ВВОД КОЛИЧЕСТВА
# ===============================================

@router.message(PurchaseStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите целое положительное число (например: 5):")
        return

    await state.update_data(quantity=quantity)
    data = await state.get_data()

    await state.set_state(PurchaseStates.confirm)

    await message.answer(
        f"📋 <b>Подтвердите приход:</b>\n\n"
        f"Товар: <b>{data['product_article']}</b> — {data['product_name']}\n"
        f"Количество: <b>+{quantity} шт.</b>\n\n"
        f"Подтвердить?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard(),
    )


# ===============================================
# ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
# ===============================================

@router.message(PurchaseStates.confirm, F.text == "✅ Подтвердить")
async def save_purchase(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    quantity = data["quantity"]

    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()

        if not product:
            await message.answer("❌ Товар не найден в базе.")
            await state.clear()
            return

        purchase = Purchase(
            product_id=product.id,
            quantity=quantity,
            price=product.purchase_price,
        )
        session.add(purchase)

        product.stock_quantity += quantity

        session.commit()

        from handlers.start import main_keyboard
        await message.answer(
            f"✅ <b>Приход оформлен!</b>\n\n"
            f"Товар: <b>{product.article}</b> — {product.name}\n"
            f"Добавлено: <b>+{quantity} шт.</b>\n"
            f"Новый остаток: <b>{product.stock_quantity} шт.</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Ошибка при сохранении: {e}")
    finally:
        session.close()

    await state.clear()


# ===============================================
# ОТМЕНА
# ===============================================

@router.message(F.text == "❌ Отмена")
async def cancel_purchase(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    from handlers.start import main_keyboard
    await message.answer("❌ Приход отменён.", reply_markup=main_keyboard())