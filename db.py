import random

import aiosqlite

DB_PATH = "kinobot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                downloads INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'uz',
                promo_confirmed INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                chat_id TEXT PRIMARY KEY,
                title TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

        # Eski bazalarda promo_confirmed ustuni bo'lmasligi mumkin — qo'shamiz
        try:
            await db.execute("ALTER TABLE users ADD COLUMN promo_confirmed INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # ustun allaqachon bor


# ---------- Users ----------

async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def get_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else "uz"


async def set_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang",
            (user_id, lang),
        )
        await db.commit()


async def total_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        return (await cur.fetchone())[0]


async def is_promo_confirmed(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT promo_confirmed FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_promo_confirmed(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, promo_confirmed) VALUES (?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET promo_confirmed=1",
            (user_id,),
        )
        await db.commit()


# ---------- Movies ----------

async def add_movie(code: str, title: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO movies (code, title, file_id, downloads) "
            "VALUES (?, ?, ?, COALESCE((SELECT downloads FROM movies WHERE code=?), 0))",
            (code, title, file_id, code),
        )
        await db.commit()


async def next_code() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        while True:
            code = str(random.randint(1000, 9999))
            cur = await db.execute("SELECT 1 FROM movies WHERE code=?", (code,))
            if not await cur.fetchone():
                return code


async def delete_movie(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM movies WHERE code=?", (code,))
        await db.commit()
        return cur.rowcount > 0


async def get_movie(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code, title, file_id, downloads FROM movies WHERE code=?", (code,)
        )
        return await cur.fetchone()


async def bump_downloads(code: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE movies SET downloads = downloads + 1 WHERE code=?", (code,)
        )
        await db.commit()
        cur = await db.execute("SELECT downloads FROM movies WHERE code=?", (code,))
        return (await cur.fetchone())[0]


async def total_movies() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM movies")
        return (await cur.fetchone())[0]


async def total_downloads() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(SUM(downloads),0) FROM movies")
        return (await cur.fetchone())[0]


# ---------- Required channels (majburiy obuna) ----------

async def add_required_channel(chat_id: str, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO required_channels (chat_id, title) VALUES (?, ?)",
            (chat_id, title),
        )
        await db.commit()


async def remove_required_channel(chat_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM required_channels WHERE chat_id=?", (chat_id,))
        await db.commit()
        return cur.rowcount > 0


async def list_required_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT chat_id, title FROM required_channels")
        return await cur.fetchall()


# ---------- Settings (reklama boti sozlamalari) ----------

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
