import aiosqlite

DB_PATH = "kinobot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
                lang TEXT DEFAULT 'uz'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                chat_id TEXT PRIMARY KEY,
                title TEXT
            )
        """)
        await db.commit()


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


# ---------- Movies ----------

async def add_movie(code: str, title: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO movies (code, title, file_id, downloads) "
            "VALUES (?, ?, ?, COALESCE((SELECT downloads FROM movies WHERE code=?), 0))",
            (code, title, file_id, code),
        )
        await db.commit()


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
