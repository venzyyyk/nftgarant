"""
Telegram Business — оператор пишет команды прямо в чате с клиентом.

Бот подключён к бизнес-аккаунту через Telegram Business → Chatbots.
Все сообщения в бизнес-чатах приходят с полем business_connection_id.

Команды оператора (пишет прямо в чат с клиентом):
  offer <ссылка> <звёзды> [таймер] — создать сделку, отправить пост клиенту
  confirm <order_id>  — подтвердить
  cancel <order_id>   — отменить
  deals               — активные сделки
"""

import re
import logging

from aiogram import Router, F
from aiogram.types import Message, BusinessConnection, CallbackQuery

from config import config
from db import (
    is_operator, create_deal, get_deal, get_deal_by_order,
    update_deal_status, set_deal_seller, get_active_deals, get_template,
)
from utils import generate_order_id, render_template
from keyboards import deal_seller_kb, deal_offer_kb

log = logging.getLogger(__name__)

router = Router()

# mapping business_connection_id -> owner_user_id
# нужно чтобы отличать свой bcid от bcid других бизнес-аккаунтов,
# куда подключен тот же бот
BIZ_CONNECTIONS: dict[str, int] = {}

GIFT_LINK_RE = re.compile(r"https?://t\.me/nft/([A-Za-z0-9_]+)-(\d+)")


def parse_gift_link(text: str) -> tuple[str, str, str] | None:
    m = GIFT_LINK_RE.search(text)
    if not m:
        return None
    slug = m.group(1)
    number = m.group(2)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", slug)
    return slug, name, number


def is_operator_msg(msg: Message) -> bool:
    """Это сообщение оператора (владельца), а не клиента."""
    return msg.from_user and msg.from_user.id == config.owner_id


# --- business_connection ---

@router.business_connection()
async def on_business_connection(event: BusinessConnection):
    log.info(
        f"BUSINESS CONNECTION: user={event.user.id} (@{event.user.username}), "
        f"id={event.id}, enabled={event.is_enabled}, can_reply={event.can_reply}"
    )
    if event.is_enabled:
        BIZ_CONNECTIONS[event.id] = event.user.id
    else:
        BIZ_CONNECTIONS.pop(event.id, None)

    if event.is_enabled and event.user.id == config.owner_id:
        try:
            await event.bot.send_message(
                event.user.id,
                "✅ Бот подключён к бизнес-аккаунту.\n\n"
                "Пиши в чатах с клиентами:\n"
                "<code>offer ССЫЛКА ЗВЁЗДЫ</code>\n"
                "<code>confirm ORDER_ID</code>\n"
                "<code>cancel ORDER_ID</code>\n"
                "<code>deals</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            log.error(f"notify owner failed: {e}")


# --- business_message catch-all ---
# ловим ВСЁ что имеет business_connection_id, разбираем сами

@router.business_message()
async def on_business_message(msg: Message):
    text = (msg.text or "").strip()
    log.info(
        f"BIZ MSG: from={msg.from_user.id if msg.from_user else '?'}, "
        f"chat={msg.chat.id}, bcid={msg.business_connection_id}, "
        f"text={text[:100]!r}"
    )

    # игнорируем сообщения клиентов — команды только от оператора
    if not is_operator_msg(msg):
        return

    # игнорируем сообщения из ЧУЖИХ бизнес-аккаунтов,
    # куда подключен тот же бот (защита от дублей)
    bcid_owner = BIZ_CONNECTIONS.get(msg.business_connection_id)
    if bcid_owner is not None and bcid_owner != config.owner_id:
        log.info(
            f"BIZ MSG: skip, bcid belongs to {bcid_owner}, not owner {config.owner_id}"
        )
        return

    if not text:
        return

    low = text.lower()
    bcid = msg.business_connection_id

    if low.startswith("offer"):
        await handle_offer(msg, text, bcid)
    elif low.startswith("confirm"):
        await handle_confirm(msg, text, bcid)
    elif low.startswith("cancel"):
        await handle_cancel(msg, text, bcid)
    elif low == "deals":
        await handle_deals(msg, bcid)


# --- offer ---

async def handle_offer(msg: Message, text: str, bcid: str):
    parts = text.split(maxsplit=3)
    if len(parts) < 3:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text=("Формат: <code>offer ССЫЛКА ЗВЁЗДЫ [ТАЙМЕР]</code>\n"
                  "Пример: <code>offer https://t.me/nft/SnoopDogg-40651 100</code>"),
            parse_mode="HTML",
            business_connection_id=bcid,
        )
        return

    parsed = parse_gift_link(parts[1])
    if not parsed:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text="Не могу распарсить ссылку. Формат: https://t.me/nft/SnoopDogg-40651",
            business_connection_id=bcid,
        )
        return

    try:
        stars = int(parts[2])
    except ValueError:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text="Количество звёзд должно быть числом.",
            business_connection_id=bcid,
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
    await set_deal_seller(deal_id, msg.chat.id)

    # для первого шага используем короткий офер
    post_text = render_template(
        config.short_offer_template,
        order_id=order_id,
        stars=stars,
        operator_username=msg.from_user.username or "operator",
        gift_name=name,
        gift_slug=slug,
        gift_number=number,
        timer=timer,
    )

    # удаляем команду оператора "offer ..." чтобы не светилась в чате
    try:
        await msg.bot.delete_business_messages(
            business_connection_id=bcid,
            message_ids=[msg.message_id],
        )
    except Exception as e:
        log.warning(f"BIZ offer: delete operator msg failed: {e}")

    try:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text=post_text,
            parse_mode="HTML",
            reply_markup=deal_offer_kb(deal_id, slug, number),
            business_connection_id=bcid,
        )
        log.info(f"BIZ offer: deal #{order_id} created in chat {msg.chat.id}")
    except Exception as e:
        log.error(f"BIZ offer send failed: {e}")
        # fallback — отправляем как обычный бот напрямую клиенту (без бизнес-соединения)
        try:
            await msg.bot.send_message(
                chat_id=msg.chat.id,
                text=post_text,
                parse_mode="HTML",
                reply_markup=deal_offer_kb(deal_id, slug, number),
            )
            log.info(f"BIZ offer: deal #{order_id} fallback-sent to {msg.chat.id}")
        except Exception as e2:
            log.error(f"BIZ offer fallback failed: {e2}")
            # сообщаем оператору в тот же чат от его имени (через бизнес)
            try:
                await msg.bot.send_message(
                    chat_id=msg.from_user.id,
                    text=(f"⚠️ Сделка #{order_id} создана, но пост отправить не смог:\n"
                          f"<code>{e}</code>\n\n"
                          f"Причины: клиент в Excluded Chats, заблокировал бота, "
                          f"или настройки приватности. "
                          f"Попроси клиента написать /start боту @{(await msg.bot.me()).username}, "
                          f"потом: <code>/send {order_id} {msg.chat.id}</code>"),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"📦 Бизнес-сделка #{order_id}\n"
                f"Оператор: @{msg.from_user.username}\n"
                f"Клиент: {msg.chat.id}\n"
                f"Подарок: {name} #{number}\nЗвёзды: {stars}",
            )
        except Exception:
            pass


# --- callback: клиент принял офер — раскрываем полный текст с инструкцией ---

@router.callback_query(F.data.startswith("deal_offer_accept:"))
async def cb_offer_accept(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    deal = await get_deal(deal_id)
    if not deal:
        await cb.answer("Сделка не найдена.", show_alert=True)
        return

    tpl = await get_template()
    if not tpl:
        tpl = config.default_template

    # оператор по которому делаем username
    op_username = "operator"
    try:
        op_chat = await cb.bot.get_chat(deal["operator_id"])
        op_username = op_chat.username or "operator"
    except Exception:
        pass

    full_text = render_template(
        tpl,
        order_id=deal["order_id"],
        stars=deal["stars"],
        operator_username=op_username,
        gift_name=deal["gift_name"],
        gift_slug=deal["gift_slug"],
        gift_number=deal["gift_number"],
        timer=deal["timer"],
    )

    new_kb = deal_seller_kb(deal_id, deal["gift_slug"], deal["gift_number"])

    bcid = getattr(cb.message, "business_connection_id", None) if cb.message else None
    log.info(f"cb_offer_accept: deal_id={deal_id}, bcid={bcid}, msg_id={cb.message.message_id if cb.message else None}")

    try:
        if bcid:
            await cb.bot.edit_message_text(
                business_connection_id=bcid,
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=full_text,
                parse_mode="HTML",
                reply_markup=new_kb,
            )
        elif cb.message:
            await cb.message.edit_text(
                full_text,
                parse_mode="HTML",
                reply_markup=new_kb,
            )
    except Exception as e:
        log.error(f"cb_offer_accept edit failed: {e}")
        # fallback: отправляем новое сообщение
        try:
            if bcid:
                await cb.bot.send_message(
                    chat_id=cb.message.chat.id,
                    text=full_text,
                    parse_mode="HTML",
                    reply_markup=new_kb,
                    business_connection_id=bcid,
                )
            elif cb.message:
                await cb.bot.send_message(
                    chat_id=cb.message.chat.id,
                    text=full_text,
                    parse_mode="HTML",
                    reply_markup=new_kb,
                )
        except Exception as e2:
            log.error(f"cb_offer_accept fallback send failed: {e2}")

    await cb.answer("Офер принят. Готово к передаче подарка.")
    await update_deal_status(deal_id, "sent")

    # уведомляем оператора
    try:
        await cb.bot.send_message(
            deal["operator_id"],
            f"✅ Клиент принял офер по сделке #{deal['order_id']}",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("deal_decline:"))
async def cb_offer_decline(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    deal = await get_deal(deal_id)
    if not deal:
        await cb.answer("Сделка не найдена.", show_alert=True)
        return

    await update_deal_status(deal_id, "cancelled")

    bcid = getattr(cb.message, "business_connection_id", None) if cb.message else None
    new_text = (cb.message.html_text if cb.message and cb.message.html_text else
                (cb.message.text if cb.message else "")) + "\n\n<b>❌ Предложение отклонено</b>"

    try:
        if bcid:
            await cb.bot.edit_message_text(
                business_connection_id=bcid,
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=new_text,
                parse_mode="HTML",
            )
        elif cb.message:
            await cb.message.edit_text(new_text, parse_mode="HTML")
    except Exception as e:
        log.error(f"cb_offer_decline edit failed: {e}")

    await cb.answer("Предложение отклонено.")

    try:
        await cb.bot.send_message(
            deal["operator_id"],
            f"❌ Клиент отклонил офер по сделке #{deal['order_id']}",
        )
    except Exception:
        pass


# --- confirm ---

async def handle_confirm(msg: Message, text: str, bcid: str):
    parts = text.split()
    if len(parts) < 2:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text="Формат: <code>confirm ORDER_ID</code>",
            parse_mode="HTML",
            business_connection_id=bcid,
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
        await msg.bot.send_message(
            chat_id=msg.chat.id, text="Сделка не найдена.",
            business_connection_id=bcid,
        )
        return

    await update_deal_status(deal["id"], "confirmed")
    await msg.bot.send_message(
        chat_id=msg.chat.id,
        text=f"✅ Сделка #{deal['order_id']} подтверждена.",
        business_connection_id=bcid,
    )
    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"✅ Сделка #{deal['order_id']} подтверждена (бизнес)",
            )
        except Exception:
            pass


# --- cancel ---

async def handle_cancel(msg: Message, text: str, bcid: str):
    parts = text.split()
    if len(parts) < 2:
        await msg.bot.send_message(
            chat_id=msg.chat.id,
            text="Формат: <code>cancel ORDER_ID</code>",
            parse_mode="HTML",
            business_connection_id=bcid,
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
        await msg.bot.send_message(
            chat_id=msg.chat.id, text="Сделка не найдена.",
            business_connection_id=bcid,
        )
        return

    await update_deal_status(deal["id"], "cancelled")
    await msg.bot.send_message(
        chat_id=msg.chat.id,
        text=f"❌ Сделка #{deal['order_id']} отменена.",
        business_connection_id=bcid,
    )
    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"❌ Сделка #{deal['order_id']} отменена (бизнес)",
            )
        except Exception:
            pass


# --- deals ---

async def handle_deals(msg: Message, bcid: str):
    deals = await get_active_deals(msg.from_user.id)
    if not deals:
        await msg.bot.send_message(
            chat_id=msg.chat.id, text="Нет активных сделок.",
            business_connection_id=bcid,
        )
        return
    lines = [
        f"#{d['order_id']} — {d['gift_name']} #{d['gift_number']} — "
        f"{d['stars']}⭐ — {d['status']}"
        for d in deals
    ]
    await msg.bot.send_message(
        chat_id=msg.chat.id,
        text="Активные сделки:\n\n" + "\n".join(lines),
        business_connection_id=bcid,
    )
