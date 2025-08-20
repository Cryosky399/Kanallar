# database.py
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DB_URL = os.getenv("DB_URL")

if not DB_URL:
    # Егер DB_URL болмаса, басқа параметрлер арқылы қосылу
    DB_CONFIG = {
        'user': os.getenv("DB_USER"),
        'password': os.getenv("DB_PASS"),
        'database': os.getenv("DB_NAME"),
        'host': os.getenv("DB_HOST"),
        'port': os.getenv("DB_PORT", 5432)
    }

db_pool = None

async def init_db():
    global db_pool
    if DB_URL:
        db_pool = await asyncpg.create_pool(dsn=DB_URL)
    else:
        db_pool = await asyncpg.create_pool(**DB_CONFIG)

    async with db_pool.acquire() as conn:
        # Пайдаланушылар кестесі
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                is_confirmed BOOLEAN DEFAULT FALSE,
                registration_time TIMESTAMP
            );
        """)

        # Кодтар кестесі
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kino_codes (
                code TEXT PRIMARY KEY,
                channel TEXT,
                message_id INTEGER,
                post_count INTEGER,
                title TEXT
            );
        """)

        # Статистика кестесі
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                code TEXT PRIMARY KEY,
                searched INTEGER DEFAULT 0,
                viewed INTEGER DEFAULT 0
            );
        """)

        # Админдер кестесі
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY
            );
        """)

        # FAQ кестесі
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS faq (
                id SERIAL PRIMARY KEY,
                question TEXT,
                answer TEXT
            );
        """)

        # Default админдерді қосу
        default_admins = [7483732504, 5959511392]
        for admin_id in default_admins:
            await conn.execute(
                "INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
                admin_id
            )

# === Пайдаланушыларды басқару === #
async def add_user(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, registration_time) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET registration_time = EXCLUDED.registration_time",
            user_id, datetime.now()
        )

async def confirm_user_registration(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_confirmed = TRUE WHERE user_id = $1",
            user_id
        )

async def delete_user_registration(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM users WHERE user_id = $1",
            user_id
        )

async def get_unconfirmed_users():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, is_confirmed, registration_time FROM users WHERE is_confirmed = FALSE")
        return [
            {
                "user_id": row["user_id"],
                "is_confirmed": row["is_confirmed"],
                "registration_time": row["registration_time"]
            }
            for row in rows
        ]

async def get_all_users():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, is_confirmed, registration_time FROM users")
        return [
            {
                "user_id": row["user_id"],
                "is_confirmed": row["is_confirmed"],
                "registration_time": row["registration_time"]
            }
            for row in rows
        ]

# === Кодтарды басқару === #
async def add_kino_code(code, channel, message_id, post_count, title):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO kino_codes (code, channel, message_id, post_count, title)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO UPDATE SET
                channel = EXCLUDED.channel,
                message_id = EXCLUDED.message_id,
                post_count = EXCLUDED.post_count,
                title = EXCLUDED.title;
        """, code, channel, message_id, post_count, title)
        await conn.execute("""
            INSERT INTO stats (code) VALUES ($1)
            ON CONFLICT DO NOTHING
        """, code)

async def get_kino_by_code(code):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT code, channel, message_id, post_count, title
            FROM kino_codes
            WHERE code = $1
        """, code)
        return dict(row) if row else None

async def get_all_codes():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT code, channel, message_id, post_count, title
            FROM kino_codes
        """)
        return [
            {
                "code": row["code"],
                "channel": row["channel"],
                "message_id": row["message_id"],
                "post_count": row["post_count"],
                "title": row["title"]
            }
            for row in rows
        ]

async def delete_kino_code(code):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM stats WHERE code = $1", code)
        result = await conn.execute("DELETE FROM kino_codes WHERE code = $1", code)
        return result.endswith("1")

async def update_anime_code(old_code, new_code, new_title):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE kino_codes SET code = $1, title = $2 WHERE code = $3
        """, new_code, new_title, old_code)

# === Статистиканы басқару === #
async def increment_stat(code, field):
    if field not in ("searched", "viewed", "init"):
        return
    async with db_pool.acquire() as conn:
        if field == "init":
            await conn.execute("""
                INSERT INTO stats (code, searched, viewed) VALUES ($1, 0, 0)
                ON CONFLICT DO NOTHING
            """, code)
        else:
            await conn.execute(f"""
                UPDATE stats SET {field} = {field} + 1 WHERE code = $1
            """, code)

async def get_code_stat(code):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT searched, viewed FROM stats WHERE code = $1", code)

# === Админдерді басқару === #
async def add_admin(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )

async def get_all_admins():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admins")
        return {row["user_id"] for row in rows}

async def remove_admin(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)

# === FAQ-ты басқару === #
async def add_faq(question, answer):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faq (question, answer) VALUES ($1, $2)
        """, question, answer)

async def get_all_faqs():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, question, answer FROM faq")
        return [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"]
            }
            for row in rows
        ]

async def get_faq_by_question(question):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, question, answer FROM faq WHERE question = $1", question)
        return dict(row) if row else None

async def delete_faq(faq_id):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM faq WHERE id = $1", faq_id)
