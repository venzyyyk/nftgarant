import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import config
from db import init_db
from handlers import operator, admin, business

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main():
    if not config.bot_token:
        log.error("BOT_TOKEN не задан. Установи переменную окружения BOT_TOKEN.")
        return

    await init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)
    dp.include_router(business.router)  # business ПЕРЕД operator — ловит business_connection_id первым
    dp.include_router(operator.router)

    log.info("Бот запущен.")
    # явно указываем все типы апдейтов включая inline_query и chosen_inline_result
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message", "callback_query",
            "inline_query", "chosen_inline_result",
            "business_connection", "business_message",
            "edited_business_message",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
