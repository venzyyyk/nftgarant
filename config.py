from dataclasses import dataclass, field
from os import getenv


def _parse_owner_ids() -> list[int]:
    raw = getenv("OWNER_ID", "0")
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            pass
    return ids or [0]


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: getenv("BOT_TOKEN", ""))
    owner_ids: list[int] = field(default_factory=_parse_owner_ids)
    log_group_id: int = field(default_factory=lambda: int(getenv("LOG_GROUP_ID", "0")))
    db_path: str = "data/bot.db"

    @property
    def owner_id(self) -> int:
        """Для обратной совместимости — первый owner."""
        return self.owner_ids[0] if self.owner_ids else 0

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owner_ids

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
