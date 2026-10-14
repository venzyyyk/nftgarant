import re
import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineQuery, ChosenInlineResult,
    InlineQueryResultArticle, InputTextMessageContent,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

log = logging.getLogger(__name__)

from config import config
from db import (
    is_operator, create_deal, get_deal, get_deal_by_order,
    update_deal_status, set_deal_seller, get_active_deals, get_template,
    delete_template,
)
from utils import generate_order_id, render_template
from keyboards import deal_seller_kb, operator_deal_kb

router = Router()

# паттерн для парсинга ссылки на подарок: https://t.me/nft/SnoopDogg-40651
GIFT_LINK_RE = re.compile(r"https?://t\.me/nft/([A-Za-z0-9_]+)-(\d+)")


def parse_gift_link(text: str) -> tuple[str, str, str] | None:
    """Парсит ссылку -> (slug, name, number). Slug = SnoopDogg, name = Snoop Dogg."""
    m = GIFT_LINK_RE.search(text)
    if not m:
        return None
    slug = m.group(1)
    number = m.group(2)
    # делаем читаемое имя из slug: SnoopDogg -> Snoop Dogg
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", slug)
    return slug, name, number


class NewDeal(StatesGroup):
    gift_link = State()
    stars = State()
    timer = State()


# --- /start ---

@router.message(F.text == "/start")
async def cmd_start(msg: Message):
    if config.is_owner(msg.from_user.id):
        await msg.answer(
            "👋 Бот гарант-сделок запущен.\n\n"
            "Команды владельца:\n"
            "/admin — панель управления\n"
            "/deal — создать сделку\n"
            "/mydeals — активные сделки\n"
            "/send ID USER_ID — отправить пост продавцу\n"
            "/addop USER_ID USERNAME — добавить оператора\n"
            "/rmop USER_ID — удалить оператора"
        )
    elif await is_operator(msg.from_user.id):
        await msg.answer(
            "👋 Привет! Ты оператор.\n\n"
            "/deal — создать сделку\n"
            "/mydeals — мои сделки\n"
            "/send ID USER_ID — отправить пост продавцу"
        )
    else:
        await msg.answer("👋 Бот гарант-сделок Telegram Stars.")


# --- сброс кастомного шаблона на default из config.py ---

@router.message(F.text == "/resettpl")
async def cmd_resettpl(msg: Message):
    if not config.is_owner(msg.from_user.id):
        return
    await delete_template()
    await msg.answer(
        "✅ Кастомный шаблон удалён. Теперь используется default из config.py "
        "(с premium эмодзи)."
    )


# --- создание сделки ---

@router.message(F.text == "/deal")
async def cmd_deal(msg: Message, state: FSMContext):
    if not await is_operator(msg.from_user.id) and not config.is_owner(msg.from_user.id):
        return
    await msg.answer(
        "Вставь ссылку на подарок:\n"
        "Например: https://t.me/nft/SnoopDogg-40651"
    )
    await state.set_state(NewDeal.gift_link)


@router.message(NewDeal.gift_link)
async def deal_gift_link(msg: Message, state: FSMContext):
    parsed = parse_gift_link(msg.text.strip())
    if not parsed:
        await msg.answer(
            "Не могу распарсить ссылку. Нужен формат:\n"
            "https://t.me/nft/SnoopDogg-40651"
        )
        return

    slug, name, number = parsed
    await state.update_data(gift_slug=slug, gift_name=name, gift_number=number)
    await msg.answer(
        f"Подарок: {name} #{number}\n"
        f"Ссылка: https://t.me/nft/{slug}-{number}\n\n"
        f"Сколько звёзд? (число):"
    )
    await state.set_state(NewDeal.stars)


@router.message(NewDeal.stars)
async def deal_stars(msg: Message, state: FSMContext):
    try:
        stars = int(msg.text.strip())
    except ValueError:
        await msg.answer("Введи число.")
        return
    await state.update_data(stars=stars)
    await msg.answer("Таймер резерва (например: 24 часа):\nИли отправь «-» для дефолта.")
    await state.set_state(NewDeal.timer)


@router.message(NewDeal.timer)
async def deal_timer(msg: Message, state: FSMContext):
    data = await state.get_data()
    timer = "24 часа" if msg.text.strip() == "-" else msg.text.strip()

    order_id = generate_order_id()
    deal_id = await create_deal(
        order_id=order_id,
        operator_id=msg.from_user.id,
        gift_name=data["gift_name"],
        gift_slug=data["gift_slug"],
        gift_number=data["gift_number"],
        stars=data["stars"],
        timer=timer,
    )

    # рендерим гарант-пост
    tpl = await get_template()
    if not tpl:
        tpl = config.default_template

    post_text = render_template(
        tpl,
        order_id=order_id,
        stars=data["stars"],
        operator_username=msg.from_user.username or "operator",
        gift_name=data["gift_name"],
        gift_slug=data["gift_slug"],
        gift_number=data["gift_number"],
        timer=timer,
    )

    await state.clear()

    await msg.answer(
        f"Сделка #{order_id} создана.\n\n"
        f"Ниже — готовый пост для продавца.\n"
        f"Отправь продавцу: /send {order_id} USER_ID",
    )
    await msg.answer(
        post_text,
        parse_mode="HTML",
        reply_markup=operator_deal_kb(deal_id),
    )

    if config.log_group_id:
        try:
            await msg.bot.send_message(
                config.log_group_id,
                f"📦 Новая сделка #{order_id}\n"
                f"Оператор: @{msg.from_user.username}\n"
                f"Подарок: {data['gift_name']} #{data['gift_number']}\n"
                f"Ссылка: https://t.me/nft/{data['gift_slug']}-{data['gift_number']}\n"
                f"Звёзды: {data['stars']}\n"
                f"Статус: ожидание",
            )
        except Exception:
            pass


# --- отправка поста продавцу ---

@router.message(F.text.startswith("/send"))
async def cmd_send(msg: Message):
    if not await is_operator(msg.from_user.id) and not config.is_owner(msg.from_user.id):
        return

    parts = msg.text.split()
    if len(parts) < 3:
        await msg.answer("Формат: /send ID USER_ID\nID — номер сделки или order_id")
        return

    raw_id = parts[1].lstrip("#")
    try:
        seller_id = int(parts[2])
    except ValueError:
        await msg.answer("USER_ID должен быть числом.")
        return

    # пробуем как числовой deal_id, потом как order_id
    deal = None
    try:
        deal = await get_deal(int(raw_id))
    except ValueError:
        pass
    if not deal:
        deal = await get_deal_by_order(raw_id)
    if not deal:
        await msg.answer("Сделка не найдена.")
        return
    deal_id = deal["id"]

    await set_deal_seller(deal_id, seller_id)

    tpl = await get_template()
    if not tpl:
        tpl = config.default_template

    post_text = render_template(
        tpl,
        order_id=deal["order_id"],
        stars=deal["stars"],
        operator_username=msg.from_user.username or "operator",
        gift_name=deal["gift_name"],
        gift_slug=deal["gift_slug"],
        gift_number=deal["gift_number"],
        timer=deal["timer"],
    )

    try:
        await msg.bot.send_message(
            seller_id,
            post_text,
            parse_mode="HTML",
            reply_markup=deal_seller_kb(deal_id, deal["gift_slug"], deal["gift_number"]),
        )
        await update_deal_status(deal_id, "sent")
        await msg.answer(f"Пост отправлен продавцу (ID: {seller_id}).")

        if config.log_group_id:
            await msg.bot.send_message(
                config.log_group_id,
                f"📨 Пост по сделке #{deal['order_id']} отправлен продавцу (ID: {seller_id})",
            )
    except Exception as e:
        await msg.answer(f"Не удалось отправить: {e}")


# --- оператор подтверждает/отменяет ---

@router.callback_query(F.data.startswith("op_confirm:"))
async def op_confirm(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    deal = await get_deal(deal_id)
    if not deal:
        await cb.answer("Сделка не найдена.", show_alert=True)
        return

    if cb.from_user.id != deal["operator_id"] and not config.is_owner(cb.from_user.id):
        await cb.answer("Не твоя сделка.", show_alert=True)
        return

    await update_deal_status(deal_id, "confirmed")
    await cb.message.edit_text(
        cb.message.text + "\n\n✅ <b>СДЕЛКА ЗАВЕРШЕНА</b>",
        parse_mode="HTML",
    )
    await cb.answer("Сделка подтверждена.")

    if config.log_group_id:
        try:
            await cb.bot.send_message(
                config.log_group_id,
                f"✅ Сделка #{deal['order_id']} завершена оператором @{cb.from_user.username}",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("op_cancel:"))
async def op_cancel(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    deal = await get_deal(deal_id)
    if not deal:
        await cb.answer("Сделка не найдена.", show_alert=True)
        return

    if cb.from_user.id != deal["operator_id"] and not config.is_owner(cb.from_user.id):
        await cb.answer("Не твоя сделка.", show_alert=True)
        return

    await update_deal_status(deal_id, "cancelled")
    await cb.message.edit_text(
        cb.message.text + "\n\n❌ <b>СДЕЛКА ОТМЕНЕНА</b>",
        parse_mode="HTML",
    )
    await cb.answer("Сделка отменена.")

    if config.log_group_id:
        try:
            await cb.bot.send_message(
                config.log_group_id,
                f"❌ Сделка #{deal['order_id']} отменена оператором @{cb.from_user.username}",
            )
        except Exception:
            pass


# --- продавец подтверждает передачу ---

@router.callback_query(F.data.startswith("deal_accept:"))
async def deal_accept(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    deal = await get_deal(deal_id)
    if not deal:
        await cb.answer("Сделка не найдена.", show_alert=True)
        return

    # сохраняем продавца если ещё не сохранён (inline-случай)
    if not deal.get("seller_id"):
        await set_deal_seller(deal_id, cb.from_user.id)

    seller_tag = f"@{cb.from_user.username}" if cb.from_user.username else f"ID:{cb.from_user.id}"
    try:
        await cb.bot.send_message(
            deal["operator_id"],
            f"🔔 Продавец {seller_tag} подтвердил передачу по сделке #{deal['order_id']}!\n"
            f"Подарок: {deal['gift_name']} #{deal['gift_number']}\n"
            f"Ссылка: https://t.me/nft/{deal['gift_slug']}-{deal['gift_number']}\n"
            f"Проверь и подтверди получение.",
            reply_markup=operator_deal_kb(deal_id),
        )
    except Exception:
        pass

    # редактируем сообщение (обычное или inline)
    try:
        if cb.inline_message_id:
            await cb.bot.edit_message_reply_markup(
                inline_message_id=cb.inline_message_id,
                reply_markup=None,
            )
        elif cb.message:
            await cb.message.edit_text(
                (cb.message.html_text or cb.message.text or "") + "\n\n⏳ <b>Ожидание подтверждения оператора...</b>",
                parse_mode="HTML",
            )
    except Exception:
        pass

    await cb.answer("Оператор уведомлён. Ожидайте подтверждения.")

    if config.log_group_id:
        try:
            await cb.bot.send_message(
                config.log_group_id,
                f"🔔 Продавец подтвердил передачу по сделке #{deal['order_id']}",
            )
        except Exception:
            pass


# --- список активных сделок оператора ---

@router.message(F.text == "/mydeals")
async def cmd_mydeals(msg: Message):
    if not await is_operator(msg.from_user.id) and not config.is_owner(msg.from_user.id):
        return

    deals = await get_active_deals(msg.from_user.id)
    if not deals:
        await msg.answer("Нет активных сделок.")
        return

    lines = []
    for d in deals:
        lines.append(
            f"#{d['order_id']} — {d['gift_name']} #{d['gift_number']} — "
            f"{d['stars']}⭐ — {d['status']}"
        )
    await msg.answer("Твои активные сделки:\n\n" + "\n".join(lines))


# --- inline-режим: отправка поста прямо в чат с продавцом ---

async def _build_deal_result(deal: dict, username: str | None) -> InlineQueryResultArticle:
    """Собирает inline-результат для одной сделки."""
    tpl = await get_template()
    if not tpl:
        tpl = config.default_template

    post_text = render_template(
        tpl,
        order_id=deal["order_id"],
        stars=deal["stars"],
        operator_username=username or "operator",
        gift_name=deal["gift_name"],
        gift_slug=deal["gift_slug"],
        gift_number=deal["gift_number"],
        timer=deal["timer"],
    )
    return InlineQueryResultArticle(
        id=str(deal["id"]),
        title=f"#{deal['order_id']} — {deal['gift_name']} #{deal['gift_number']}",
        description=f"{deal['stars']}⭐ · резерв {deal['timer']}",
        input_message_content=InputTextMessageContent(
            message_text=post_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        ),
        reply_markup=deal_seller_kb(deal["id"], deal["gift_slug"], deal["gift_number"]),
    )


@router.inline_query()
async def inline_deal_query(query: InlineQuery):
    log.info(f"INLINE QUERY from {query.from_user.id} (@{query.from_user.username}): '{query.query}'")

    # только оператор/владелец
    if not await is_operator(query.from_user.id) and not config.is_owner(query.from_user.id):
        log.info(f"inline: user {query.from_user.id} is not operator")
        await query.answer([], cache_time=1, is_personal=True)
        return

    text = query.query.strip().lstrip("#").upper()
    results: list[InlineQueryResultArticle] = []

    if not text:
        deals = await get_active_deals(query.from_user.id)
        log.info(f"inline: showing {len(deals)} active deals")
        for d in deals[:20]:
            results.append(await _build_deal_result(d, query.from_user.username))
    else:
        deal = await get_deal_by_order(text)
        if deal and (deal["operator_id"] == query.from_user.id or config.is_owner(query.from_user.id)):
            results.append(await _build_deal_result(deal, query.from_user.username))
        log.info(f"inline: query '{text}' matched {len(results)} deals")

    await query.answer(results, cache_time=1, is_personal=True)
    log.info(f"inline: answered with {len(results)} results")


@router.chosen_inline_result()
async def inline_chosen(result: ChosenInlineResult):
    log.info(f"CHOSEN INLINE RESULT: deal_id={result.result_id} by @{result.from_user.username}, inline_message_id={result.inline_message_id}")
