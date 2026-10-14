from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import config
from db import (
    add_operator, remove_operator, get_operators,
    get_all_deals, get_active_deals, get_template, set_template,
)
from utils import TEMPLATE_VARS
from keyboards import admin_menu_kb, back_to_admin_kb

router = Router()


def is_owner(user_id: int) -> bool:
    return config.is_owner(user_id)


class EditTemplate(StatesGroup):
    waiting_template = State()


class AddOperator(StatesGroup):
    waiting_id = State()


class RemoveOperator(StatesGroup):
    waiting_id = State()


# --- /admin ---

@router.message(F.text == "/admin")
async def cmd_admin(msg: Message):
    if not is_owner(msg.from_user.id):
        return
    await msg.answer("⚙️ Админ-панель", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not is_owner(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text("⚙️ Админ-панель", reply_markup=admin_menu_kb())


# --- операторы ---

@router.callback_query(F.data == "admin:operators")
async def cb_operators(cb: CallbackQuery):
    if not is_owner(cb.from_user.id):
        return
    ops = await get_operators()
    if ops:
        lines = [f"• @{o['username']} (ID: {o['user_id']})" for o in ops]
        text = "👥 Операторы:\n\n" + "\n".join(lines)
    else:
        text = "👥 Операторов пока нет."

    text += (
        "\n\n/addop USER_ID USERNAME — добавить"
        "\n/rmop USER_ID — удалить"
    )
    await cb.message.edit_text(text, reply_markup=back_to_admin_kb())


@router.message(F.text.startswith("/addop"))
async def cmd_addop(msg: Message):
    if not is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 3:
        await msg.answer("Формат: /addop USER_ID USERNAME")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await msg.answer("USER_ID должен быть числом.")
        return
    username = parts[2].lstrip("@")
    await add_operator(uid, username)
    await msg.answer(f"Оператор @{username} (ID: {uid}) добавлен.")


@router.message(F.text.startswith("/rmop"))
async def cmd_rmop(msg: Message):
    if not is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("Формат: /rmop USER_ID")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await msg.answer("USER_ID должен быть числом.")
        return
    await remove_operator(uid)
    await msg.answer(f"Оператор (ID: {uid}) удалён.")


# --- шаблон ---

@router.callback_query(F.data == "admin:template")
async def cb_template(cb: CallbackQuery, state: FSMContext):
    if not is_owner(cb.from_user.id):
        return

    tpl = await get_template()
    current = tpl or config.default_template

    vars_text = "\n".join(f"  {{{k}}} — {v}" for k, v in TEMPLATE_VARS.items())

    await cb.message.edit_text(
        f"📝 Текущий шаблон:\n\n{current}\n\n"
        f"Доступные переменные:\n{vars_text}\n\n"
        f"Отправь новый шаблон или /cancel для отмены.",
        reply_markup=back_to_admin_kb(),
    )
    await state.set_state(EditTemplate.waiting_template)


@router.message(EditTemplate.waiting_template, F.text == "/cancel")
async def cancel_template(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Отменено.", reply_markup=admin_menu_kb())


@router.message(EditTemplate.waiting_template)
async def save_template(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id):
        return
    await set_template(msg.text)
    await state.clear()
    await msg.answer("✅ Шаблон обновлён.", reply_markup=admin_menu_kb())


# --- сделки ---

@router.callback_query(F.data == "admin:deals")
async def cb_deals(cb: CallbackQuery):
    if not is_owner(cb.from_user.id):
        return
    deals = await get_all_deals(30)
    if not deals:
        await cb.message.edit_text("Сделок пока нет.", reply_markup=back_to_admin_kb())
        return

    lines = []
    for d in deals:
        status_emoji = {
            "pending": "🕐", "sent": "📨", "confirmed": "✅", "cancelled": "❌"
        }.get(d["status"], "❓")
        lines.append(
            f"{status_emoji} #{d['order_id']} — {d['gift_name']} #{d['gift_number']} — "
            f"{d['stars']}⭐ — {d['status']}"
        )
    await cb.message.edit_text(
        "📊 Последние сделки:\n\n" + "\n".join(lines),
        reply_markup=back_to_admin_kb(),
    )


@router.callback_query(F.data == "admin:active")
async def cb_active(cb: CallbackQuery):
    if not is_owner(cb.from_user.id):
        return
    deals = await get_active_deals()
    if not deals:
        await cb.message.edit_text("Нет активных сделок.", reply_markup=back_to_admin_kb())
        return

    lines = []
    for d in deals:
        lines.append(
            f"#{d['order_id']} — {d['gift_name']} #{d['gift_number']} — "
            f"{d['stars']}⭐ — {d['status']} — оператор ID:{d['operator_id']}"
        )
    await cb.message.edit_text(
        "🔥 Активные сделки:\n\n" + "\n".join(lines),
        reply_markup=back_to_admin_kb(),
    )
