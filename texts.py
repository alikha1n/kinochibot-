TEXTS = {
    "uz": {
        "start": "Salom! Kino kodini yuboring, men sizga kinoni topib beraman.",
        "not_found": "Bunday kodli kino topilmadi.",
        "downloads": "🎬 {title}\n\n⬇️ Yuklab olganlar: {count} kishi",
        "subscribe_required": "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        "check_sub": "✅ Tekshirish",
        "not_subscribed": "Siz hali barcha kanallarga obuna bo'lmadingiz.",
        "lang_switched": "Til o'zbekchaga o'zgartirildi.",
        "admin_panel": "🛠 Admin panel",
        "add_movie_prompt": "Kino videosini yuboring (caption sifatida kod va nomni kiriting: KOD | Nom).",
        "add_movie_bad_format": "Format noto'g'ri. Caption: KOD | Nom",
        "add_movie_done": "✅ Kino qo'shildi: {code} — {title}",
        "del_movie_prompt": "O'chirmoqchi bo'lgan kino kodini yuboring.",
        "del_movie_done": "🗑 Kino o'chirildi: {code}",
        "del_movie_missing": "Bunday kodli kino topilmadi.",
        "stats": "📊 Statistika\n\n👤 Foydalanuvchilar: {users}\n🎬 Kinolar soni: {movies}\n⬇️ Jami yuklamalar: {downloads}",
        "add_channel_prompt": "Kanal ID yoki @username yuboring.",
        "channel_added": "✅ Kanal qo'shildi: {chat}",
        "no_access": "Sizda ruxsat yo'q.",
    },
    "ru": {
        "start": "Привет! Отправьте код фильма, и я его найду.",
        "not_found": "Фильм с таким кодом не найден.",
        "downloads": "🎬 {title}\n\n⬇️ Скачали: {count} человек",
        "subscribe_required": "Для использования бота подпишитесь на каналы:",
        "check_sub": "✅ Проверить",
        "not_subscribed": "Вы ещё не подписались на все каналы.",
        "lang_switched": "Язык переключён на русский.",
        "admin_panel": "🛠 Админ-панель",
        "add_movie_prompt": "Отправьте видео фильма (в подписи укажите код и название: КОД | Название).",
        "add_movie_bad_format": "Неверный формат. Подпись: КОД | Название",
        "add_movie_done": "✅ Фильм добавлен: {code} — {title}",
        "del_movie_prompt": "Отправьте код фильма для удаления.",
        "del_movie_done": "🗑 Фильм удалён: {code}",
        "del_movie_missing": "Фильм с таким кодом не найден.",
        "stats": "📊 Статистика\n\n👤 Пользователей: {users}\n🎬 Фильмов: {movies}\n⬇️ Всего скачиваний: {downloads}",
        "add_channel_prompt": "Отправьте ID канала или @username.",
        "channel_added": "✅ Канал добавлен: {chat}",
        "no_access": "У вас нет доступа.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS["uz"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
