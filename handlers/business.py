"""
Telegram Business — оператор пишет команды прямо в чате с клиентом.

Бот подключён к бизнес-аккаунту через Telegram Business → Chatbots.
Все сообщения в бизнес-чатах приходят как обычные Message,
но с полем business_connection_id.

Команды оператора (пишет прямо в чат с клиентом):
  offer <ссылка> <звёзды> [таймер]
    — создаёт сделку и отправляет пост клиенту в этот же чат

  confirm <order_id>
    — подтверждает сделку

  cancel <order_id>
    — отменяет сделку

  deals
    — показывает активные сделки (ответ виден только оператору)
"""

import re
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BusinessConnection

from config import config
from db import (
    is_operator, create_deal, get_deal, get_deal_by_order,
    update_deal_status, set_deal_seller, get_active_deals, get_template,
)
from utils import generate_order_id, render_template
from keyboards import deal_seller_kb, operator_deal_kb

log = logging.getLogger(__name__)

router = Router()

# паттерн для ссылки на подарок
GIFT_LINK_RE = re.compile(r"https?://t\.me/nft/([A-Za-z0-9_]+)-(\d+)")


def parse_gift_link(text: str) -> tuple[str, str, str] | None:
    m = GIFT_LINK_RE.search(text)
    if not m:
        return None
    slug = m.group(1)
    number = m.group(2)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", slug)
    return slug, name, number


def is_from_operator(msg: Message) -> bool:
    """Проверяет что сообщение от оператора (владельца бизнес-аккаунта),
    а не от клиента."""
    # В business_message: если from_user.id == owner_id или оператор,
    # значит это сообщение оператора.
    # Telegram помечает сообщения оператора через is_from_offline или
    # просто from_user совпадает с владельцем бизнес-аккаунта.
    return msg.from_user.id == config.owner_id


# --- business_connection: бот подключён к бизнес-аккаунту ---

@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    """Когда бот подключается/отключается от бизнес-аккаунта."""
    if event.is_enabled:
        log.info(
            f"Business connected: user={event.user.id} (@{event.user.username}), "
            f"can_reply={event.can_reply}"
        )
        # можно сохранить business_connection_id для дальнейшего использования
        try:
            await event.bot.send_message(
                event.user.id,
                "✅ Бот подключён к бизнес-аккаунту.\n\n"
                "Теперь пиши в чатах с клиентами:\n"
                "<code>offer ССЫЛКА ЗВЁЗДЫ</code> — создать сделку\n"
                "<code>confirm ORDER_ID</code> — подтвердить\n"
                "<code>cancel ORDER_ID</code> — отменить\n"
                "<code>deals</code> — активные сделки",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        log.info(f"Business disconnected: user={event.user.id}")


# --- фильтр: только бизнес-сообщения ---
# business_connection_id != None означает что это сообщение из бизнес-чата

@router.message(F.business_connection_id, F.text.casefold().startswith("offer"))
async def biz_offer(msg: Message):
    """offer <ссылка> <звёзды> [таймер]
    Создаёт сделку прямо в чате с клиентом."""

    if not is_from_operator(msg):
        return  # игнорируем сообщения клиентов с "offer"

    parts = msg.text.split(maxsplit=3)
    # offer https://t.me/nft/SnoopDogg-40651 100 24 часа
    if len(parts) < 3:
        # отвечаем оператору (в тот же бизнес-чат)
        await msg.answer(
            "Формат: <code>offer ССЫЛКА ЗВЁЗДЫ [ТАЙМЕР]</code>\n"
            "Пример: <code>offer https://t.me/nft/SnoopDogg-40651 100</code>",
            parse_mode="HTML",
            business_connection_id=msg.business_connection_id,
        )
        return

    link = parts[1]
    parsed = parse_gift_link(link)
    if not parsed:
        await msg.answer(
            "Не могу распарсить ссылку. Нужен формат:\n"
            "https://t.me/nft/SnoopDogg-40651",
            business_connection_id=msg.business_connection_id,
        )
        return

    try:
        stars = int(parts[2])
    except ValueError:
        await msg.answer(
            "Количество звёзд должно быть числом.",
            business_connection_id=msg.business_connection_id,
        )
        return

    timer = parts[3] if len(parts) > 3 else "24 часа"
    slug, name, number = parsed

    order_id = generate_order_id()
    deal_id = await create_deal(
        order_id=order_id,
        operator_id=msg.from_user.id,
        gift_name=name,
        gift_slug=slug,
        gift_number=number,
        stars=stars,
        timer=timer,
    )

    # сохраняем клиента как seller (chat.id в бизнес-чате = id клиента)
    client_id = msg.chat.id
    await set_deal_seller(deal_id, client_id)

    # рендерим гарант-пост
    tpl = await get_template()
    if not tpl:
        tpl = config.default_template

    post_text = render_template(
        tpl,
        order_id=order_id,
        stars=stars,
        operator_username=msg.from_user.username or "operator",
        gift_name=name,
        gift_slug=slug,
        gift_number=number,
        timer=timer,
    )

    # отправляем пост клиенту в этот же бизнес-чат
    await msg.bot.send_message(
        chat_id=msg.chat.id,
        text=post_text,
        parse_mode="HTML",
        reply_markup=deal_seller_kb(deal_id, slug, number),
        business_connection_id=msg.business_connection_id,
    )

    log.info(f"Business deal #{order_id} created in chat {msg.chat.id}")

    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"📦 Бизнес-сделка #{order_id}\n"
                f"Оператор: @{msg.from_user.username}\n"
                f"Клиент: {msg.chat.id}\n"
                f"Подарок: {name} #{number}\n"
                f"Звёзды: {stars}",
            )
        except Exception:
            pass


@router.message(F.business_connection_id, F.text.casefold().startswith("confirm"))
async def biz_confirm(msg: Message):
    """confirm ORDER_ID — подтвердить сделку."""
    if not is_from_operator(msg):
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(
            "Формат: <code>confirm ORDER_ID</code>",
            parse_mode="HTML",
            business_connection_id=msg.business_connection_id,
        )
        return

    raw_id = parts[1].lstrip("#")
    deal = await get_deal_by_order(raw_id.upper())
    if not deal:
        try:
            deal = await get_deal(int(raw_id))
        except ValueError:
            pass
    if not deal:
        await msg.answer(
            "Сделка не найдена.",
            business_connection_id=msg.business_connection_id,
        )
        return

    await update_deal_status(deal["id"], "confirmed")
    await msg.answer(
        f"✅ Сделка #{deal['order_id']} подтверждена.",
        business_connection_id=msg.business_connection_id,
    )

    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"✅ Сделка #{deal['order_id']} подтверждена (бизнес-чат)",
            )
        except Exception:
            pass


@router.message(F.business_connection_id, F.text.casefold().startswith("cancel"))
async def biz_cancel(msg: Message):
    """cancel ORDER_ID — отменить сделку."""
    if not is_from_operator(msg):
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(
            "Формат: <code>cancel ORDER_ID</code>",
            parse_mode="HTML",
            business_connection_id=msg.business_connection_id,
        )
        return

    raw_id = parts[1].lstrip("#")
    deal = await get_deal_by_order(raw_id.upper())
    if not deal:
        try:
            deal = await get_deal(int(raw_id))
        except ValueError:
            pass
    if not deal:
        await msg.answer(
            "Сделка не найдена.",
            business_connection_id=msg.business_connection_id,
        )
        return

    await update_deal_status(deal["id"], "cancelled")
    await msg.answer(
        f"❌ Сделка #{deal['order_id']} отменена.",
        business_connection_id=msg.business_connection_id,
    )

    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"❌ Сделка #{deal['order_id']} отменена (бизнес-чат)",
            )
        except Exception:
            pass


@router.message(F.business_connection_id, F.text.casefold() == "deals")
async def biz_deals(msg: Message):
    """deals — список активных сделок."""
    if not is_from_operator(msg):
        return

    deals = await get_active_deals(msg.from_user.id)
    if not deals:
        await msg.answer(
            "Нет активных сделок.",
            business_connection_id=msg.business_connection_id,
        )
        return

    lines = []
    for d in deals:
        lines.append(
            f"#{d['order_id']} — {d['gift_name']} #{d['gift_number']} — "
            f"{d['stars']}⭐ — {d['status']}"
        )
    await msg.answer(
        "Активные сделки:\n\n" + "\n".join(lines),
        business_connection_id=msg.business_connection_id,
    )
