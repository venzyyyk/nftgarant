from dataclasses import dataclass, field
from os import getenv


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: getenv("BOT_TOKEN", ""))
    owner_id: int = field(default_factory=lambda: int(getenv("OWNER_ID", "0")))
    log_group_id: int = field(default_factory=lambda: int(getenv("LOG_GROUP_ID", "0")))
    db_path: str = "data/bot.db"

    # короткий шаблон первого сообщения (офер — Отклонить/Принять)
    short_offer_template: str = (
        '@{operator_username} предлагает вам <b>{stars}'
        '<tg-emoji emoji-id="5406812184359507637">⭐</tg-emoji></b> '
        'за подарок <a href="https://t.me/nft/{gift_slug}-{gift_number}">'
        '{gift_name} #{gift_number}</a>.\n\n'
        'Предложение действует ещё <b>{timer}</b>...'
    )

    # полный шаблон (после Принять — показывается инструкция)
    default_template: str = (
        '<tg-emoji emoji-id="5318901904686754959">🙂</tg-emoji> <b>Безопасная сделка Telegram Stars</b>\n'
        'Заказ: <a href="https://t.me/nft/{gift_slug}-{gift_number}"><b>#TG-{order_id}</b></a>\n\n'
        'Покупатель зарезервировал <b>{stars}<tg-emoji emoji-id="5406812184359507637">⭐</tg-emoji></b> '
        'через гарантийную систему Telegram.\n'
        'Средства находятся на специальном счёте удержания '
        'и будут зачислены на ваш баланс Telegram звёзд '
        'сразу после передачи подарка.\n\n'
        '<b>Инструкция для завершения сделки:</b>\n'
        '1. Передайте подарок @{operator_username}\n'
        '2. Нажмите «Передать подарок» и выберите '
        '<a href="https://t.me/nft/{gift_slug}-{gift_number}">'
        '{gift_name} #{gift_number}</a>\n'
        '3. Подтвердите передачу подарка\n\n'
        '<tg-emoji emoji-id="5406812184359507637">⭐</tg-emoji> Система Telegram зафиксирует транзакцию '
        'и моментально зачислит <b>{stars}<tg-emoji emoji-id="5406812184359507637">⭐</tg-emoji></b> '
        'на ваш баланс Telegram звёзд\n\n'
        '<tg-emoji emoji-id="5357069174512303778">✅</tg-emoji> Резерв действует <b>{timer}</b>'
    )


config = Config()
