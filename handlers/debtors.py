from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.engine import get_session
from database.models import Debtor, Sale, Payment

router = Router()


# ===============================================
# Состояния
# ===============================================

class DebtorStates(StatesGroup):
    waiting_for_payment_amount = State()
    add_name = State()
    add_phone = State()


# ===============================================
# Клавиатуры
# ===============================================

def debtors_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все должники")],
            [KeyboardButton(text="➕ Добавить должника")],
            [KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def skip_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭️ Пропустить")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# ГЛАВНОЕ МЕНЮ ДОЛЖНИКОВ
# ===============================================

@router.message(F.text == "👥 Должники")
async def debtors_menu(message: types.Message):
    await message.answer(
        "👥 <b>Должники</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=debtors_menu_keyboard(),
    )


# ===============================================
# ДОБАВЛЕНИЕ ДОЛЖНИКА
# ===============================================

@router.message(F.text == "➕ Добавить должника")
async def add_debtor_start(message: types.Message, state: FSMContext):
    await state.set_state(DebtorStates.add_name)
    await message.answer(
        "Введите имя должника:",
        reply_markup=cancel_keyboard(),
    )


@router.message(DebtorStates.add_name)
async def process_add_debtor_name(message: types.Message, state: FSMContext):
    name = message.text.strip()

    if not name:
        await message.answer("⚠️ Имя не может быть пустым. Введите имя:")
        return

    await state.update_data(debtor_name=name)
    await state.set_state(DebtorStates.add_phone)
    await message.answer(
        f"Имя: <b>{name}</b>\n\n"
        f"Введите номер телефона (или нажмите Пропустить):",
        parse_mode="HTML",
        reply_markup=skip_phone_keyboard(),
    )


@router.message(DebtorStates.add_phone)
async def process_add_debtor_phone(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text == "⏭️ Пропустить":
        phone = None
    elif text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=debtors_menu_keyboard())
        return
    else:
        phone = text

    data = await state.get_data()
    name = data.get("debtor_name")

    session = get_session()
    try:
        debtor = Debtor(name=name, phone=phone)
        session.add(debtor)
        session.commit()

        phone_text = f"\n📞 {phone}" if phone else ""
        await message.answer(
            f"✅ <b>Должник добавлен!</b>\n\n"
            f"Имя: <b>{name}</b>{phone_text}",
            parse_mode="HTML",
            reply_markup=debtors_menu_keyboard(),
        )
    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        session.close()

    await state.clear()


# ===============================================
# СПИСОК ВСЕХ ДОЛЖНИКОВ
# ===============================================

@router.message(F.text == "📋 Все должники")
async def list_all_debtors(message: types.Message):
    session = get_session()
    try:
        debtors = session.query(Debtor).order_by(Debtor.name).all()

        if not debtors:
            await message.answer("👥 Нет должников. Добавьте первого через кнопку «➕ Добавить должника».")
            return

        text = "👥 <b>Список должников:</b>\n\n"
        keyboard_rows = []

        for d in debtors:
            # Считаем общий долг
            total_debt = 0
            for sale in d.sales:
                paid = sum(p.amount for p in sale.payments)
                remaining = sale.total_amount - paid
                if remaining > 0:
                    total_debt += remaining

            phone = f" | 📞 {d.phone}" if d.phone else ""
            if total_debt > 0:
                text += f"🔴 <b>{d.name}</b>{phone} — долг: <b>{total_debt:.2f}</b>\n"
            else:
                text += f"🟢 <b>{d.name}</b>{phone} — долгов нет\n"

            keyboard_rows.append([
                InlineKeyboardButton(
                    text=f"{'🔴' if total_debt > 0 else '🟢'} {d.name} ({total_debt:.2f})",
                    callback_data=f"debtor_detail:{d.id}"
                )
            ])

        if keyboard_rows:
            inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            await message.answer(text, parse_mode="HTML", reply_markup=inline_kb)
        else:
            await message.answer(text, parse_mode="HTML")

    finally:
        session.close()


# ===============================================
# ДЕТАЛИ ДОЛЖНИКА
# ===============================================

@router.callback_query(F.data.startswith("debtor_detail:"))
async def debtor_detail(callback: types.CallbackQuery):
    debtor_id = int(callback.data.split(":")[1])

    session = get_session()
    try:
        debtor = session.query(Debtor).filter(Debtor.id == debtor_id).first()

        if not debtor:
            await callback.answer("Должник не найден.", show_alert=True)
            return

        text = f"👤 <b>{debtor.name}</b>\n"
        if debtor.phone:
            text += f"📞 {debtor.phone}\n"
        text += "\n<b>Продажи в долг:</b>\n\n"

        keyboard_rows = []
        total_debt = 0
        has_sales = False

        for sale in debtor.sales:
            has_sales = True
            paid = sum(p.amount for p in sale.payments)
            remaining = sale.total_amount - paid

            if remaining > 0:
                status = "🔴"
                total_debt += remaining
            elif remaining == 0 and paid > 0:
                status = "🟢"
            else:
                status = "⚫"

            product_name = sale.product.name if sale.product else "Товар удалён"

            text += (
                f"{status} Продажа №{sale.id} от {sale.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   Товар: {product_name} | Кол-во: {sale.quantity}\n"
                f"   Сумма: {sale.total_amount:.2f} | Оплачено: {paid:.2f} | Остаток: {remaining:.2f}\n\n"
            )

            if remaining > 0:
                keyboard_rows.append([
                    InlineKeyboardButton(
                        text=f"💰 Оплатить (остаток: {remaining:.2f})",
                        callback_data=f"pay_debt:{sale.id}"
                    )
                ])

        if not has_sales:
            text += "Нет продаж в долг.\n"

        text += f"\n<b>Общий долг: {total_debt:.2f}</b>"

        if keyboard_rows:
            inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=inline_kb)
        else:
            await callback.message.edit_text(text, parse_mode="HTML")

        await callback.answer()

    finally:
        session.close()


# ===============================================
# ОПЛАТА ДОЛГА
# ===============================================

@router.callback_query(F.data.startswith("pay_debt:"))
async def start_payment(callback: types.CallbackQuery, state: FSMContext):
    sale_id = int(callback.data.split(":")[1])
    await state.update_data(paying_sale_id=sale_id)
    await state.set_state(DebtorStates.waiting_for_payment_amount)

    await callback.answer()
    await callback.message.answer(
        "💰 Введите сумму оплаты:",
        reply_markup=cancel_keyboard(),
    )


@router.message(DebtorStates.waiting_for_payment_amount)
async def process_payment(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректную сумму:")
        return

    data = await state.get_data()
    sale_id = data.get("paying_sale_id")

    session = get_session()
    try:
        sale = session.query(Sale).filter(Sale.id == sale_id).first()

        if not sale:
            await message.answer("❌ Продажа не найдена.")
            await state.clear()
            return

        # Проверяем остаток долга
        paid = sum(p.amount for p in sale.payments)
        remaining = sale.total_amount - paid

        if amount > remaining:
            await message.answer(
                f"⚠️ Сумма превышает остаток долга!\n"
                f"Остаток: <b>{remaining:.2f}</b>\n"
                f"Введите другую сумму:",
                parse_mode="HTML",
            )
            return

        # Создаём платёж
        payment = Payment(
            sale_id=sale.id,
            amount=amount,
        )
        session.add(payment)
        session.commit()

        new_remaining = remaining - amount
        debtor_name = sale.debtor.name if sale.debtor else "Неизвестно"

        from handlers.start import main_keyboard
        await message.answer(
            f"✅ <b>Оплата принята!</b>\n\n"
            f"Должник: <b>{debtor_name}</b>\n"
            f"Сумма оплаты: <b>{amount:.2f}</b>\n"
            f"Остаток долга: <b>{new_remaining:.2f}</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

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
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
    await message.answer(
        "👥 <b>Должники</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=debtors_menu_keyboard(),
    )