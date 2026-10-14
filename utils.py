import random
import string


def generate_order_id() -> str:
    """Генерирует ID заказа XXXXXXXXXX"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=10))


def make_gift_slug(gift_name: str) -> str:
    """Делает slug для ссылки на подарок: Instant Ramen -> Instantramen"""
    return gift_name.replace(" ", "")


def render_template(template: str, **kwargs) -> str:
    """Рендерит шаблон гарант-поста"""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        return f"Ошибка шаблона: отсутствует переменная {e}"


# доступные переменные для шаблона
TEMPLATE_VARS = {
    "order_id": "ID заказа (XXXXXXXXXX)",
    "stars": "Количество звёзд",
    "operator_username": "Username оператора (без @)",
    "gift_name": "Название подарка",
    "gift_slug": "Slug подарка для ссылки (без пробелов)",
    "gift_number": "Номер подарка",
    "timer": "Время действия резерва",
}
