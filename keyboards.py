from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def deal_seller_kb(deal_id: int, gift_slug: str, gift_number: str) -> InlineKeyboardMarkup:
    """Клавиатура для продавца — показать подарок + трансфер + подтвердить"""
    gift_url = f"https://t.me/nft/{gift_slug}-{gift_number}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Передать подарок", url=gift_url)],
        [InlineKeyboardButton(text="✅ Подтвердить передачу", callback_data=f"deal_accept:{deal_id}")],
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
