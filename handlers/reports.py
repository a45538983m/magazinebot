from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import os
from datetime import datetime, timedelta

from database.engine import get_session
from database.models import Product, Sale, Debtor, Payment

router = Router()


# ===============================================
# Клавиатуры
# ===============================================

def reports_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Остатки (Excel)")],
            [KeyboardButton(text="📈 Продажи сегодня"), KeyboardButton(text="📈 Продажи за месяц")],
            [KeyboardButton(text="📋 Продажи за период")],
            [KeyboardButton(text="🔙 Главное меню")],
        ],
        resize_keyboard=True,
    )


# ===============================================
# ГЛАВНОЕ МЕНЮ ОТЧЁТОВ
# ===============================================

@router.message(F.text == "📥 Выгрузить")
async def reports_menu(message: types.Message):
    await message.answer(
        "📥 <b>Выгрузка отчётов</b>\n\n"
        "Выберите отчёт:",
        parse_mode="HTML",
        reply_markup=reports_menu_keyboard(),
    )


# ===============================================
# ЭКСПОРТ ОСТАТКОВ В EXCEL
# ===============================================

@router.message(F.text == "📊 Остатки (Excel)")
async def export_stock_excel(message: types.Message):
    session = get_session()
    try:
        products = session.query(Product).order_by(Product.name).all()

        if not products:
            await message.answer("📦 Нет товаров для выгрузки.")
            return

        # Создаём Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Остатки"

        # Стили
        header_font = Font(bold=True, color="FFFFFF", size=12)
        header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        center_align = Alignment(horizontal="center")

        # Заголовки
        headers = ["№", "Артикул", "Название", "Бренд", "Закуп. цена", "Розн. цена", "Остаток", "Место", "Подходит для"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = center_align

        # Данные
        for i, p in enumerate(products, 2):
            # Совместимость
            compat = ""
            if p.compatible_models:
                models = [f"{cm.brand} {cm.model}" for cm in p.compatible_models[:5]]
                compat = ", ".join(models)
                if len(p.compatible_models) > 5:
                    compat += f" и ещё {len(p.compatible_models) - 5}"

            row_data = [
                i - 1,
                p.article,
                p.name,
                p.brand or "",
                p.purchase_price,
                p.selling_price,
                p.stock_quantity,
                p.location_code or "",
                compat,
            ]

            for col, value in enumerate(row_data, 1):
                cell = ws.cell(row=i, column=col, value=value)
                cell.border = thin_border
                if col in [5, 6]:
                    cell.number_format = "#,##0.00"
                elif col == 7:
                    cell.alignment = center_align

            # Цвет строки по остатку
            if p.stock_quantity == 0:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=i, column=col).fill = red_fill
            elif p.stock_quantity < 10:
                for col in range(1, len(headers) + 1):
                    ws.cell(row=i, column=col).fill = PatternFill(start_color="FFFFCC", end_color="FFFFCC", fill_type="solid")

        # Ширина столбцов
        widths = [5, 18, 35, 15, 12, 12, 10, 10, 40]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

        # Сохраняем
        filename = f"stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = f"temp/{filename}"
        os.makedirs("temp", exist_ok=True)
        wb.save(filepath)

        # Отправляем
        file = FSInputFile(filepath)
        await message.answer_document(
            file,
            caption=f"📊 Остатки товаров на {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        )

        # Удаляем файл
        os.remove(filepath)

    finally:
        session.close()


# ===============================================
# ПРОДАЖИ ЗА СЕГОДНЯ
# ===============================================

@router.message(F.text == "📈 Продажи сегодня")
async def sales_today(message: types.Message):
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    session = get_session()
    try:
        sales = session.query(Sale).filter(Sale.created_at >= today_start).order_by(Sale.created_at.desc()).all()

        if not sales:
            await message.answer("📈 Сегодня продаж не было.")
            return

        await send_sales_report(message, sales, "сегодня")

    finally:
        session.close()


# ===============================================
# ПРОДАЖИ ЗА МЕСЯЦ
# ===============================================

@router.message(F.text == "📈 Продажи за месяц")
async def sales_month(message: types.Message):
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    session = get_session()
    try:
        sales = session.query(Sale).filter(Sale.created_at >= month_start).order_by(Sale.created_at.desc()).all()

        if not sales:
            await message.answer("📈 В этом месяце продаж не было.")
            return

        await send_sales_report(message, sales, "за месяц")

    finally:
        session.close()


# ===============================================
# ПРОДАЖИ ЗА ПЕРИОД (ПОСЛЕДНИЕ 7 ДНЕЙ)
# ===============================================

@router.message(F.text == "📋 Продажи за период")
async def sales_week(message: types.Message):
    week_start = datetime.now() - timedelta(days=7)

    session = get_session()
    try:
        sales = session.query(Sale).filter(Sale.created_at >= week_start).order_by(Sale.created_at.desc()).all()

        if not sales:
            await message.answer("📋 За последние 7 дней продаж не было.")
            return

        await send_sales_report(message, sales, "за 7 дней")

    finally:
        session.close()


# ===============================================
# ФОРМИРОВАНИЕ EXCEL С ПРОДАЖАМИ
# ===============================================

async def send_sales_report(message, sales, period_name):
    wb = Workbook()
    ws = wb.active
    ws.title = "Продажи"

    # Стили
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    center_align = Alignment(horizontal="center")

    # Заголовки
    headers = ["№", "Дата", "Товар", "Артикул", "Кол-во", "Цена за ед.", "Сумма", "Должник", "Оплачено", "Долг"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    total_sum = 0
    total_paid = 0
    total_debt = 0

    for i, s in enumerate(sales, 2):
        product_name = s.product.name if s.product else "Товар удалён"
        product_article = s.product.article if s.product else "-"
        debtor_name = s.debtor.name if s.debtor else ""
        paid_amount = sum(p.amount for p in s.payments) if s.debtor_id else s.total_amount
        debt_amount = s.total_amount - paid_amount if s.debtor_id else 0

        row_data = [
            i - 1,
            s.created_at.strftime('%d.%m.%Y %H:%M'),
            product_name,
            product_article,
            s.quantity,
            s.price,
            s.total_amount,
            debtor_name,
            paid_amount,
            debt_amount,
        ]

        for col, value in enumerate(row_data, 1):
            cell = ws.cell(row=i, column=col, value=value)
            cell.border = thin_border
            if col in [6, 7, 9, 10]:
                cell.number_format = "#,##0.00"

        total_sum += s.total_amount
        total_paid += paid_amount
        total_debt += debt_amount

    # Итоговая строка
    summary_row = len(sales) + 2
    ws.cell(row=summary_row, column=6, value="ИТОГО:").font = Font(bold=True)
    ws.cell(row=summary_row, column=7, value=total_sum).font = Font(bold=True)
    ws.cell(row=summary_row, column=7).number_format = "#,##0.00"
    ws.cell(row=summary_row, column=9, value=total_paid).font = Font(bold=True)
    ws.cell(row=summary_row, column=9).number_format = "#,##0.00"
    ws.cell(row=summary_row, column=10, value=total_debt).font = Font(bold=True)
    ws.cell(row=summary_row, column=10).number_format = "#,##0.00"

    for col in range(1, len(headers) + 1):
        ws.cell(row=summary_row, column=col).border = thin_border

    # Ширина столбцов
    widths = [5, 18, 30, 18, 8, 12, 12, 15, 12, 10]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    # Сохраняем
    filename = f"sales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = f"temp/{filename}"
    os.makedirs("temp", exist_ok=True)
    wb.save(filepath)

    # Отправляем
    file = FSInputFile(filepath)

    # Текстовый отчёт
    text = f"📈 <b>Продажи {period_name}</b>\n\n"
    text += f"Количество продаж: <b>{len(sales)}</b>\n"
    text += f"Общая сумма: <b>{total_sum:.2f}</b>\n"
    text += f"Оплачено: <b>{total_paid:.2f}</b>\n"
    if total_debt > 0:
        text += f"Осталось долгов: <b>{total_debt:.2f}</b>\n"

    await message.answer(text, parse_mode="HTML")
    await message.answer_document(file, caption=f"📋 Детальный отчёт {period_name}")

    os.remove(filepath)