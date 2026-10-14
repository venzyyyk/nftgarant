from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def deal_offer_kb(deal_id: int, gift_slug: str, gift_number: str) -> InlineKeyboardMarkup:
    """Первый вид — короткий офер: Показать подарок + Отклонить/Принять"""
    gift_url = f"https://t.me/nft/{gift_slug}-{gift_number}"
    return InlineKeyboardMarkup(inline_keyboard=[

        [
            InlineKeyboardButton(text="✗ Отклонить", callback_data=f"deal_decline:{deal_id}"),
            InlineKeyboardButton(text="✓ Принять", callback_data=f"deal_offer_accept:{deal_id}"),
        ],
    ])


def deal_seller_kb(deal_id: int, gift_slug: str, gift_number: str) -> InlineKeyboardMarkup:
    """Второй вид — после Принять: Показать подарок + Подтвердить передачу"""
    gift_url = f"https://t.me/nft/{gift_slug}-{gift_number}"
    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="✓ Передать подарок", callback_data=f"deal_accept:{deal_id}")],
    ])


def operator_deal_kb(deal_id: int) -> InlineKeyboardMarkup:
    """Клавиатура оператора — подтвердить/отменить сделку"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"op_confirm:{deal_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"op_cancel:{deal_id}"),
        ],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Операторы", callback_data="admin:operators")],
        [InlineKeyboardButton(text="📝 Шаблон поста", callback_data="admin:template")],
        [InlineKeyboardButton(text="📊 Все сделки", callback_data="admin:deals")],
        [InlineKeyboardButton(text="🔥 Активные сделки", callback_data="admin:active")],
    ])


def back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад", callback_data="admin:menu")],
    ])
