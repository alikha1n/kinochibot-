import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

import db
from texts import t

BOT_TOKEN = "8788152698:AAHDHXUsX_YicMqWNtepMory7VlC4C58ets"
ADMIN_IDS = {7434706702}

router = Router()


# ---------------- FSM states ----------------

class AddMovie(StatesGroup):
    waiting_video = State()
    waiting_code = State()


class DeleteMovie(StatesGroup):
    waiting_code = State()


class AddChannel(StatesGroup):
    waiting_channel = State()


# ---------------- Keyboards ----------------

def admin_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish" if lang == "uz" else "➕ Добавить фильм",
                               callback_data="admin_add_movie")],
        [InlineKeyboardButton(text="➖ Kino o'chirish" if lang == "uz" else "➖ Удалить фильм",
                               callback_data="admin_del_movie")],
        [InlineKeyboardButton(text="📊 Statistika" if lang == "uz" else "📊 Статистика",
                               callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Kanal qo'shish" if lang == "uz" else "📢 Добавить канал",
                               callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="🌐 Til: UZ/RU" if lang == "uz" else "🌐 Язык: UZ/RU",
                               callback_data="admin_toggle_lang")],
    ])


def sub_check_kb(lang: str, channels) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title or chat_id, url=f"https://t.me/{chat_id.lstrip('@')}")]
            for chat_id, title in channels]
    rows.append([InlineKeyboardButton(text=t(lang, "check_sub"), callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------- Force-subscribe check ----------------

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    channels = await db.list_required_channels()
    for chat_id, _ in channels:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("left", "kicked"):
                return False
        except TelegramBadRequest:
            # bot kanalga admin qilib qo'shilmagan bo'lishi mumkin — o'tkazib yuboramiz
            continue
    return True


async def require_subscription(message_or_cb, bot: Bot, lang: str) -> bool:
    user_id = message_or_cb.from_user.id
    if await is_subscribed(bot, user_id):
        return True
    channels = await db.list_required_channels()
    if not channels:
        return True
    text = t(lang, "subscribe_required")
    kb = sub_check_kb(lang, channels)
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.answer(text, reply_markup=kb)
    else:
        await message_or_cb.answer(text, reply_markup=kb)
    return False


# ---------------- User handlers ----------------

@router.message(CommandStart())
async def start(message: Message):
    await db.add_user(message.from_user.id)
    lang = await db.get_lang(message.from_user.id)
    if not await require_subscription(message, message.bot, lang):
        return
    await message.answer(t(lang, "start"))


@router.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if await is_subscribed(callback.bot, callback.from_user.id):
        await callback.message.edit_text(t(lang, "start"))
    else:
        await callback.answer(t(lang, "not_subscribed"), show_alert=True)


@router.message(StateFilter(None), F.text.regexp(r"^[A-Za-z0-9_-]{2,20}$"))
async def get_movie_by_code(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await require_subscription(message, message.bot, lang):
        return
    movie = await db.get_movie(message.text.strip())
    if not movie:
        await message.answer(t(lang, "not_found"))
        return
    code, title, file_id, _ = movie
    count = await db.bump_downloads(code)
    await message.answer_video(
        file_id,
        caption=t(lang, "downloads", title=title, count=count),
    )


# ---------------- Admin panel ----------------

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(message.from_user.id)
    await message.answer(t(lang, "admin_panel"), reply_markup=admin_kb(lang))


@router.callback_query(F.data == "admin_toggle_lang")
async def admin_toggle_lang(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    current = await db.get_lang(callback.from_user.id)
    new_lang = "ru" if current == "uz" else "uz"
    await db.set_lang(callback.from_user.id, new_lang)
    await callback.message.edit_text(t(new_lang, "admin_panel"), reply_markup=admin_kb(new_lang))
    await callback.answer(t(new_lang, "lang_switched"))


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    users = await db.total_users()
    movies = await db.total_movies()
    downloads = await db.total_downloads()
    await callback.message.answer(t(lang, "stats", users=users, movies=movies, downloads=downloads))
    await callback.answer()


@router.callback_query(F.data == "admin_add_movie")
async def admin_add_movie(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(t(lang, "add_movie_prompt"))
    await state.set_state(AddMovie.waiting_video)
    await callback.answer()


@router.message(AddMovie.waiting_video, F.video)
async def admin_add_movie_video(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    title = (message.caption or "").strip() or "Nomsiz kino"
    await state.update_data(title=title, file_id=message.video.file_id)
    await state.set_state(AddMovie.waiting_code)
    await message.answer(t(lang, "enter_code_prompt"))


@router.message(AddMovie.waiting_code, F.text)
async def admin_add_movie_code(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    code = message.text.strip()
    if not code.isdigit():
        await message.answer(t(lang, "code_must_be_number"))
        return
    if await db.get_movie(code):
        await message.answer(t(lang, "code_taken"))
        return
    data = await state.get_data()
    await db.add_movie(code, data["title"], data["file_id"])
    await message.answer(t(lang, "add_movie_done", code=code, title=data["title"]))
    await state.clear()


@router.callback_query(F.data == "admin_del_movie")
async def admin_del_movie(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(t(lang, "del_movie_prompt"))
    await state.set_state(DeleteMovie.waiting_code)
    await callback.answer()


@router.message(DeleteMovie.waiting_code)
async def admin_del_movie_code(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    code = message.text.strip()
    ok = await db.delete_movie(code)
    await message.answer(t(lang, "del_movie_done", code=code) if ok else t(lang, "del_movie_missing"))
    await state.clear()


@router.callback_query(F.data == "admin_add_channel")
async def admin_add_channel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(t(lang, "add_channel_prompt"))
    await state.set_state(AddChannel.waiting_channel)
    await callback.answer()


@router.message(AddChannel.waiting_channel)
async def admin_add_channel_value(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    chat_id = message.text.strip()
    try:
        chat = await message.bot.get_chat(chat_id)
        title = chat.title or chat_id
    except TelegramBadRequest:
        title = chat_id
    await db.add_required_channel(chat_id, title)
    await message.answer(t(lang, "channel_added", chat=chat_id))
    await state.clear()


# ---------------- Entrypoint ----------------

async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
