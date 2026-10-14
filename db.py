import aiosqlite
from pathlib import Path
from config import config

DB = config.db_path


async def init_db():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS operators (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT NOT NULL,
                added_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS deals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id     TEXT UNIQUE NOT NULL,
                operator_id  INTEGER NOT NULL,
                seller_id    INTEGER,
                gift_name    TEXT NOT NULL,
                gift_slug    TEXT NOT NULL DEFAULT '',
                gift_number  TEXT NOT NULL,
                stars        INTEGER NOT NULL,
                timer        TEXT DEFAULT '24 часа',
                status       TEXT DEFAULT 'pending',  -- pending / sent / confirmed / cancelled
                created_at   TEXT DEFAULT (datetime('now')),
                closed_at    TEXT,
                FOREIGN KEY (operator_id) REFERENCES operators(user_id)
            );

            CREATE TABLE IF NOT EXISTS templates (
                id        INTEGER PRIMARY KEY CHECK (id = 1),
                template  TEXT NOT NULL
            );
        """)
        await db.commit()


async def add_operator(user_id: int, username: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO operators (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()


async def remove_operator(user_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM operators WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_operators() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM operators")
        return [dict(r) for r in rows]


async def is_operator(user_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT 1 FROM operators WHERE user_id = ?", (user_id,)
        )
        return await cur.fetchone() is not None


async def create_deal(
    order_id: str,
    operator_id: int,
    gift_name: str,
    gift_slug: str,
    gift_number: str,
    stars: int,
    timer: str = "24 часа",
) -> int:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            """INSERT INTO deals (order_id, operator_id, gift_name, gift_slug, gift_number, stars, timer)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, operator_id, gift_name, gift_slug, gift_number, stars, timer),
        )
        await db.commit()
        return cur.lastrowid


async def get_deal(deal_id: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_deal_by_order(order_id: str) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM deals WHERE order_id = ?", (order_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_deal_status(deal_id: int, status: str):
    closed = ", closed_at = datetime('now')" if status in ("confirmed", "cancelled") else ""
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            f"UPDATE deals SET status = ?{closed} WHERE id = ?",
            (status, deal_id),
        )
        await db.commit()


async def set_deal_seller(deal_id: int, seller_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE deals SET seller_id = ? WHERE id = ?",
            (seller_id, deal_id),
        )
        await db.commit()


async def get_active_deals(operator_id: int | None = None) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        if operator_id:
            rows = await db.execute_fetchall(
                "SELECT * FROM deals WHERE status IN ('pending','sent') AND operator_id = ? ORDER BY id DESC",
                (operator_id,),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM deals WHERE status IN ('pending','sent') ORDER BY id DESC"
            )
        return [dict(r) for r in rows]


async def get_all_deals(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM deals ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]


async def get_template() -> str | None:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT template FROM templates WHERE id = 1")
        row = await cur.fetchone()
        return row[0] if row else None


async def set_template(template: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO templates (id, template) VALUES (1, ?)",
            (template,),
        )
        await db.commit()


async def delete_template():
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM templates WHERE id = 1")
        await db.commit()
