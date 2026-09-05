import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

import db
from texts import t

# Token — avval environment'dan (systemd Environment=) olinadi, topilmasa shu yerdagi
# standart qiymat ishlatiladi. Xavfsizlik uchun buni ham systemd'ga ko'chirish tavsiya etiladi.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8788152698:AAHDHXUsX_YicMqWNtepMory7VlC4C58ets")
ADMIN_IDS = {7434706702}

router = Router()

# Foydalanuvchi kod yuborgan, lekin promo'ni hali tasdiqlamagan bo'lsa —
# kodi shu yerda vaqtincha saqlanadi (bot restart bo'lsa tozalanadi, bu qabul qilinadi).
pending_codes: dict[int, str] = {}


# ---------------- FSM states ----------------

class AddMovie(StatesGroup):
    waiting_video = State()
    waiting_code = State()


class DeleteMovie(StatesGroup):
    waiting_code = State()


class AddChannel(StatesGroup):
    waiting_channel = State()


class PromoLink(StatesGroup):
    waiting_link = State()


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
        [InlineKeyboardButton(text="📣 Reklama sozlamalari" if lang == "uz" else "📣 Настройки рекламы",
                               callback_data="admin_promo_menu")],
        [InlineKeyboardButton(text="🌐 Til: UZ/RU" if lang == "uz" else "🌐 Язык: UZ/RU",
                               callback_data="admin_toggle_lang")],
    ])


def promo_admin_kb(lang: str, enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = ("🚫 O'chirish" if lang == "uz" else "🚫 Выключить") if enabled else \
                  ("✅ Yoqish" if lang == "uz" else "✅ Включить")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Havolani o'zgartirish" if lang == "uz" else "🔗 Изменить ссылку",
                               callback_data="promo_set_link")],
        [InlineKeyboardButton(text=toggle_text, callback_data="promo_toggle")],
        [InlineKeyboardButton(text="⬅️ Orqaga" if lang == "uz" else "⬅️ Назад",
                               callback_data="admin_back")],
    ])


def sub_check_kb(lang: str, channels) -> InlineKeyboardMarkup:
    rows = []
    for chat_id, title in channels:
        label = title or chat_id
        if chat_id.startswith("@"):
            # Faqat @username kanallar uchun to'g'ri link yasash mumkin
            rows.append([InlineKeyboardButton(text=label, url=f"https://t.me/{chat_id.lstrip('@')}")])
        else:
            # Raqamli/xususiy chat_id uchun link yasab bo'lmaydi — informatsion tugma
            rows.append([InlineKeyboardButton(text=label, callback_data="noop")])
    rows.append([InlineKeyboardButton(text=t(lang, "check_sub"), callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_user_kb(lang: str, link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "promo_btn_open"), url=link)],
        [InlineKeyboardButton(text=t(lang, "promo_btn_confirm"), callback_data="promo_confirm")],
    ])


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


async def deliver_movie(message_or_cb, lang: str, code: str):
    """Kinoni topib, foydalanuvchiga yuboradi (yuklamalar sonini +1 qiladi)."""
    movie = await db.get_movie(code)
    target = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    if not movie:
        await target.answer(t(lang, "not_found"))
        return
    _, title, file_id, _ = movie
    count = await db.bump_downloads(code)
    await target.answer_video(
        file_id,
        caption=t(lang, "downloads", title=title, count=count),
    )


# ---------------- User handlers ----------------

@router.message(CommandStart())
async def start(message: Message):
    await db.add_user(message.from_user.id)
    lang = await db.get_lang(message.from_user.id)
    if not await require_subscription(message, message.bot, lang):
        return
    await message.answer(t(lang, "start"))


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()


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

    code = message.text.strip()
    movie = await db.get_movie(code)
    if not movie:
        await message.answer(t(lang, "not_found"))
        return

    # ---- Promo (reklama bot) tekshiruvi ----
    promo_enabled = (await db.get_setting("promo_enabled", "0")) == "1"
    promo_link = await db.get_setting("promo_link", "")
    already_confirmed = await db.is_promo_confirmed(message.from_user.id)

    if promo_enabled and promo_link and not already_confirmed:
        pending_codes[message.from_user.id] = code
        await message.answer(t(lang, "promo_prompt"), reply_markup=promo_user_kb(lang, promo_link))
        return

    await deliver_movie(message, lang, code)


@router.callback_query(F.data == "promo_confirm")
async def promo_confirm(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    code = pending_codes.pop(callback.from_user.id, None)
    await db.set_promo_confirmed(callback.from_user.id)
    await callback.answer()
    if not code:
        await callback.message.answer(t(lang, "promo_expired"))
        return
    await deliver_movie(callback, lang, code)


# ---------------- Admin panel ----------------

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(message.from_user.id)
    await message.answer(t(lang, "admin_panel"), reply_markup=admin_kb(lang))


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.edit_text(t(lang, "admin_panel"), reply_markup=admin_kb(lang))
    await callback.answer()


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


# ---------------- Admin: promo (reklama bot) sozlamalari ----------------

@router.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    enabled = (await db.get_setting("promo_enabled", "0")) == "1"
    link = await db.get_setting("promo_link", "") or t(lang, "promo_not_set")
    status = (("✅ ON") if enabled else ("🚫 OFF"))
    await callback.message.edit_text(
        t(lang, "admin_promo_menu", status=status, link=link),
        reply_markup=promo_admin_kb(lang, enabled),
    )
    await callback.answer()


@router.callback_query(F.data == "promo_set_link")
async def promo_set_link(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.answer(t(lang, "promo_link_prompt"))
    await state.set_state(PromoLink.waiting_link)
    await callback.answer()


@router.message(PromoLink.waiting_link)
async def promo_link_received(message: Message, state: FSMContext):
    lang = await db.get_lang(message.from_user.id)
    link = message.text.strip()
    await db.set_setting("promo_link", link)
    await message.answer(t(lang, "promo_link_saved"))
    await state.clear()


@router.callback_query(F.data == "promo_toggle")
async def promo_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    lang = await db.get_lang(callback.from_user.id)
    enabled = (await db.get_setting("promo_enabled", "0")) == "1"
    new_value = "0" if enabled else "1"
    await db.set_setting("promo_enabled", new_value)
    await callback.answer(t(lang, "promo_toggle_off" if enabled else "promo_toggle_on"))
    # Menyuni yangilab qo'yamiz
    enabled_now = new_value == "1"
    link = await db.get_setting("promo_link", "") or t(lang, "promo_not_set")
    status = "✅ ON" if enabled_now else "🚫 OFF"
    await callback.message.edit_text(
        t(lang, "admin_promo_menu", status=status, link=link),
        reply_markup=promo_admin_kb(lang, enabled_now),
    )


# ---------------- Entrypoint ----------------

async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.getLogger(__name__).info("Kino Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
