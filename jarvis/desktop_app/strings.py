"""UI strings for the desktop app (English, Russian, Uzbek)."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "tab_general": "General",
        "opt_tray": "Minimize to tray instead of quitting",
        "opt_boot": "Start with the system",
        "opt_notify": "Notify me when a reply arrives",
        "tray_show": "Open KER",
        "sign_in_telegram": "Sign in with Telegram",
        "tg_code_prompt": "Enter the login code from the bot (Link account → App login code):",
        "check_updates": "Check for updates",
        "tray_quit": "Quit",
        "tray_running": "Still running in the tray.",
        "notify_reply": "KER replied",
        "welcome_title": "Welcome to KER",
        "welcome_body": (
            "Everything lives in Settings: your API key under AI, what I may "
            "touch under PC Access, the look under Interface. Enjoy, Sir."
        ),
        "theme": "Theme",
        "voice_settings": "Voice settings",
        "stt_backend": "Speech-to-text",
        "tts_backend": "Text-to-speech",
        "tts_voice": "Voice (OpenAI)",
        "voice_replies_opt": "Reply with voice",
        "whisper_model": "Local Whisper model",
        "tab_voice": "Voice",
        "voice_record": "🎙 Record",
        "voice_stop": "⏹ Stop",
        "voice_processing": "Processing…",
        "voice_speak_replies": "Speak replies aloud",
        "voice_unavailable_desktop": (
            "Voice needs local mode with voice enabled in settings (STT backend + key)."
        ),
        "voice_no_speech": "I didn't catch any speech — try again.",
        "voice_you_said": "You said",
        "app_title": "KER — Personal AI Assistant",
        "tab_chat": "Chat",
        "tab_assistant": "Assistant",
        "tab_capabilities": "PC Access",
        "tab_integrations": "Integrations",
        "tab_memory": "Memory",
        "tab_logs": "Logs",
        "send": "Send",
        "thinking": "Thinking…",
        "you": "You",
        "language": "Language",
        "mode_local": "Local (this PC)",
        "mode_remote": "Account (server)",
        "login_title": "Sign in to KER",
        "login_remote_hint": "Use the login and password you received after purchase.",
        "server_url": "Server URL",
        "username": "Username",
        "password": "Password",
        "sign_in": "Sign in",
        "login_failed": "Sign-in failed: {error}",
        "login_subtitle": "Sign in with your account, or with a code from the bot.",
        "login_tagline": ("Your assistant runs where you are: on this "
                        "computer, with your keys and your data."),
        "login_tab_account": "Account",
        "login_tab_telegram": "Telegram",
        "login_tab_register": "Register",
        "login_hint_telegram": ("In the bot: Link account → App login code. "
                                "Type that code here. On first use the code "
                                "creates your account — Free tier, no "
                                "registration needed."),
        "login_hint_register": ("Choose a login and a password. The new "
                                "account starts on the Free tier; a "
                                "subscription upgrades it without changing "
                                "how you sign in."),
        "login_cta_telegram": "Sign in with the code",
        "login_cta_register": "Create account and sign in",
        "login_code": "Login code",
        "password_repeat": "Repeat the password",
        "password_mismatch": "The two passwords do not match.",
        "login_no_bridge": ("The app isn't answering. Restart KER and try "
                            "again."),
        "login_foot": "The same login works in the bot and in the app",
        "login_need_server": ("Enter the server address first — where KER is "
                            "running (e.g. http://localhost:8000)."),
        # What the server said about itself, so a refusal can be explained
        # instead of showing a bare "invalid code".
        "probe_checking": "Checking the server…",
        "probe_ready": "{name} {version} — accounts on",
        "probe_no_accounts": ("This server has accounts switched off, so "
                            "neither a login nor a bot code works here. Set "
                            "AUTH_ENABLED=true on the server, or enter the "
                            "address of the one that sells the "
                            "subscriptions."),
        "probe_unreachable": "The server is not answering: {error}",
        "probe_no_signup": ("Registration is closed on this server — get an "
                            "account through the Telegram bot."),
        "provider": "LLM provider",
        "model": "Model (empty = default)",
        "anthropic_key": "Anthropic API key",
        "openai_key": "OpenAI API key",
        "save": "Save",
        "saved": "Saved. Restart the app to apply engine changes.",
        "cap_intro": ("Grant KER access to this computer, function by "
                    "function. Everything dangerous is OFF by default."),
        "cap_file_read": "Read files (inside the workspace)",
        "cap_file_write": "Create and edit files",
        "cap_shell": "Run terminal commands",
        "cap_desktop": "Control keyboard, mouse and screen",
        "workspace": "Workspace folder (sandbox)",
        "int_weather": "Weather (Open-Meteo, free)",
        "int_ha_url": "Home Assistant URL",
        "int_ha_token": "Home Assistant token",
        "int_tg_token": "Telegram bot token",
        "int_tg_send": "Allow sending Telegram messages / channel posts",
        "int_tg_channel": "Channel for posts (@name)",
        "mem_reset": "Clear conversation",
        "mem_forget": "Wipe everything remembered",
        "mem_done": "Done.",
        "link_telegram": "Link Telegram",
        "link_code_info": "Send this to the bot within 10 minutes:  /link {code}",
        "not_signed_in": "Not signed in.",
        "error": "Error: {error}",
    },
    "ru": {
        "tab_general": "Общие",
        "opt_tray": "Сворачивать в трей вместо выхода",
        "opt_boot": "Запускать при старте системы",
        "opt_notify": "Уведомлять о готовом ответе",
        "tray_show": "Открыть KER",
        "sign_in_telegram": "Войти через Telegram",
        "tg_code_prompt": "Введите код из бота (Привязать аккаунт → Код для входа в приложение):",
        "check_updates": "Проверить обновления",
        "tray_quit": "Выход",
        "tray_running": "Работаю в трее.",
        "notify_reply": "KER ответил",
        "welcome_title": "Добро пожаловать в KER",
        "welcome_body": (
            "Всё в Настройках: ключ провайдера — в разделе «AI», что мне "
            "позволено — в «Доступ к ПК», оформление — в «Интерфейс». "
            "Приятной работы."
        ),
        "theme": "Тема",
        "voice_settings": "Настройки голоса",
        "stt_backend": "Распознавание речи",
        "tts_backend": "Синтез речи",
        "tts_voice": "Голос (OpenAI)",
        "voice_replies_opt": "Отвечать голосом",
        "whisper_model": "Локальная модель Whisper",
        "tab_voice": "Голос",
        "voice_record": "🎙 Запись",
        "voice_stop": "⏹ Стоп",
        "voice_processing": "Обрабатываю…",
        "voice_speak_replies": "Озвучивать ответы",
        "voice_unavailable_desktop": (
            "Голос работает в локальном режиме при включённом голосе в настройках (STT + ключ)."
        ),
        "voice_no_speech": "Речь не распознана — попробуйте ещё раз.",
        "voice_you_said": "Вы сказали",
        "app_title": "KER — персональный ИИ-ассистент",
        "tab_chat": "Чат",
        "tab_assistant": "Ассистент",
        "tab_capabilities": "Доступ к ПК",
        "tab_integrations": "Интеграции",
        "tab_memory": "Память",
        "tab_logs": "Логи",
        "send": "Отправить",
        "thinking": "Думаю…",
        "you": "Вы",
        "language": "Язык",
        "mode_local": "Локально (этот ПК)",
        "mode_remote": "Аккаунт (сервер)",
        "login_title": "Вход в KER",
        "login_remote_hint": "Введите логин и пароль, полученные после покупки.",
        "server_url": "Адрес сервера",
        "username": "Логин",
        "password": "Пароль",
        "sign_in": "Войти",
        "login_failed": "Вход не выполнен: {error}",
        "login_subtitle": "Войдите по аккаунту или по коду из бота.",
        "login_tagline": ("Ассистент работает там, где вы: на этом "
                        "компьютере, с вашими ключами и вашими данными."),
        "login_tab_account": "Аккаунт",
        "login_tab_telegram": "Telegram",
        "login_tab_register": "Регистрация",
        "login_hint_telegram": ("В боте: Привязать аккаунт → Код для входа в "
                                "приложение. Введите этот код здесь. При "
                                "первом входе код сам создаёт аккаунт — "
                                "тариф Free, регистрация не нужна."),
        "login_hint_register": ("Придумайте логин и пароль. Новый аккаунт "
                                "начинается с тарифа Free; подписка "
                                "повышает тариф, а вход остаётся тем же."),
        "login_cta_telegram": "Войти по коду",
        "login_cta_register": "Создать аккаунт и войти",
        "login_code": "Код входа",
        "password_repeat": "Повторите пароль",
        "password_mismatch": "Пароли не совпадают.",
        "login_no_bridge": ("Приложение не отвечает. Перезапустите KER и "
                            "попробуйте снова."),
        "login_foot": "Один и тот же логин работает в боте и в приложении",
        "login_need_server": ("Сначала укажите адрес сервера — где запущен "
                            "KER (например, http://localhost:8000)."),
        # Что сервер сказал о себе — чтобы отказ можно было объяснить, а не
        # показывать сухое «неверный код».
        "probe_checking": "Проверяем сервер…",
        "probe_ready": "{name} {version} — аккаунты включены",
        "probe_no_accounts": ("На этом сервере аккаунты выключены, поэтому "
                            "здесь не работают ни логин, ни код из бота. "
                            "Включите AUTH_ENABLED=true на сервере или "
                            "укажите адрес того сервера, который продаёт "
                            "подписки."),
        "probe_unreachable": "Сервер не отвечает: {error}",
        "probe_no_signup": ("Регистрация на этом сервере закрыта — аккаунт "
                            "выдаёт Telegram-бот."),
        "provider": "LLM-провайдер",
        "model": "Модель (пусто = по умолчанию)",
        "anthropic_key": "Ключ Anthropic API",
        "openai_key": "Ключ OpenAI API",
        "save": "Сохранить",
        "saved": "Сохранено. Перезапустите приложение, чтобы применить.",
        "cap_intro": ("Выдавайте KER доступ к компьютеру пофункционально. "
                    "Всё опасное по умолчанию ВЫКЛЮЧЕНО."),
        "cap_file_read": "Читать файлы (внутри рабочей папки)",
        "cap_file_write": "Создавать и изменять файлы",
        "cap_shell": "Выполнять команды терминала",
        "cap_desktop": "Управлять клавиатурой, мышью и экраном",
        "workspace": "Рабочая папка (песочница)",
        "int_weather": "Погода (Open-Meteo, бесплатно)",
        "int_ha_url": "Home Assistant URL",
        "int_ha_token": "Токен Home Assistant",
        "int_tg_token": "Токен Telegram-бота",
        "int_tg_send": "Разрешить отправку сообщений / постов в Telegram",
        "int_tg_channel": "Канал для постов (@имя)",
        "mem_reset": "Очистить диалог",
        "mem_forget": "Стереть всю память",
        "mem_done": "Готово.",
        "link_telegram": "Привязать Telegram",
        "link_code_info": "Отправьте боту в течение 10 минут:  /link {code}",
        "not_signed_in": "Вы не вошли в аккаунт.",
        "error": "Ошибка: {error}",
    },
    "uz": {
        "tab_general": "Umumiy",
        "opt_tray": "Chiqish o'rniga trega yig'ish",
        "opt_boot": "Tizim ishga tushganda ochilsin",
        "opt_notify": "Javob kelganda xabar berish",
        "tray_show": "KER ni ochish",
        "sign_in_telegram": "Telegram orqali kirish",
        "tg_code_prompt": "Botdan olingan kodni kiriting:",
        "check_updates": "Yangilanishlarni tekshirish",
        "tray_quit": "Chiqish",
        "tray_running": "Trede ishlayapman.",
        "notify_reply": "KER javob berdi",
        "welcome_title": "KER ga xush kelibsiz",
        "welcome_body": (
            "Hammasi Sozlamalarda: provayder kaliti — «AI» bo'limida, menga "
            "nima ruxsat etilgani — «Kompyuterga ruxsat»da, ko'rinish — "
            "«Interfeys»da. Yoqimli foydalanish."
        ),
        "theme": "Mavzu",
        "voice_settings": "Ovoz sozlamalari",
        "stt_backend": "Nutqni aniqlash",
        "tts_backend": "Nutq sintezi",
        "tts_voice": "Ovoz (OpenAI)",
        "voice_replies_opt": "Ovoz bilan javob",
        "whisper_model": "Lokal Whisper modeli",
        "tab_voice": "Ovoz",
        "voice_record": "🎙 Yozish",
        "voice_stop": "⏹ To'xtatish",
        "voice_processing": "Qayta ishlanmoqda…",
        "voice_speak_replies": "Javoblarni ovoz bilan aytish",
        "voice_unavailable_desktop": (
            "Ovoz lokal rejimda, sozlamalarda ovoz yoqilganda ishlaydi (STT + kalit)."
        ),
        "voice_no_speech": "Nutq aniqlanmadi — yana urinib ko'ring.",
        "voice_you_said": "Siz aytdingiz",
        "app_title": "KER — shaxsiy AI yordamchi",
        "tab_chat": "Suhbat",
        "tab_assistant": "Yordamchi",
        "tab_capabilities": "Kompyuterga ruxsat",
        "tab_integrations": "Integratsiyalar",
        "tab_memory": "Xotira",
        "tab_logs": "Jurnallar",
        "send": "Yuborish",
        "thinking": "O'ylayapman…",
        "you": "Siz",
        "language": "Til",
        "mode_local": "Lokal (shu kompyuter)",
        "mode_remote": "Hisob (server)",
        "login_title": "KER ga kirish",
        "login_remote_hint": "Xariddan keyin berilgan login va parolni kiriting.",
        "server_url": "Server manzili",
        "username": "Login",
        "password": "Parol",
        "sign_in": "Kirish",
        "login_failed": "Kirish amalga oshmadi: {error}",
        "login_subtitle": "Hisob bilan yoki botdagi kod bilan kiring.",
        "login_tagline": ("Yordamchi siz turgan joyda ishlaydi: shu "
                        "kompyuterda, o'z kalitlaringiz va ma'lumotlaringiz "
                        "bilan."),
        "login_tab_account": "Hisob",
        "login_tab_telegram": "Telegram",
        "login_tab_register": "Ro'yxatdan o'tish",
        "login_hint_telegram": ("Botda: Hisobni ulash → Ilovaga kirish kodi. "
                                "Shu kodni bu yerga kiriting. Birinchi "
                                "kirishda kod hisobni o'zi yaratadi — Free "
                                "tarifi, ro'yxatdan o'tish shart emas."),
        "login_hint_register": ("Login va parol o'ylab toping. Yangi hisob "
                                "Free tarifidan boshlanadi; obuna tarifni "
                                "oshiradi, kirish esa o'zgarmaydi."),
        "login_cta_telegram": "Kod bilan kirish",
        "login_cta_register": "Hisob yaratib kirish",
        "login_code": "Kirish kodi",
        "password_repeat": "Parolni takrorlang",
        "password_mismatch": "Parollar mos kelmadi.",
        "login_no_bridge": ("Ilova javob bermayapti. KER ni qayta ishga "
                            "tushiring."),
        "login_foot": "Bitta login botda ham, ilovada ham ishlaydi",
        "login_need_server": ("Avval server manzilini kiriting — KER ishlab "
                            "turgan joy (masalan, http://localhost:8000)."),
        # Server o'zi haqida nima dedi — rad javobini tushuntirish uchun.
        "probe_checking": "Server tekshirilmoqda…",
        "probe_ready": "{name} {version} — hisoblar yoniq",
        "probe_no_accounts": ("Bu serverda hisoblar o'chirilgan, shuning "
                            "uchun na login, na botdagi kod ishlaydi. "
                            "Serverda AUTH_ENABLED=true qiling yoki "
                            "obunalarni sotadigan server manzilini "
                            "kiriting."),
        "probe_unreachable": "Server javob bermayapti: {error}",
        "probe_no_signup": ("Bu serverda ro'yxatdan o'tish yopiq — hisobni "
                            "Telegram bot beradi."),
        "provider": "LLM provayderi",
        "model": "Model (bo'sh = standart)",
        "anthropic_key": "Anthropic API kaliti",
        "openai_key": "OpenAI API kaliti",
        "save": "Saqlash",
        "saved": "Saqlandi. Qo'llash uchun ilovani qayta ishga tushiring.",
        "cap_intro": ("KER ga kompyuterga ruxsatni funksiya bo'yicha "
                    "bering. Xavfli narsalar sukut bo'yicha O'CHIQ."),
        "cap_file_read": "Fayllarni o'qish (ish papkasi ichida)",
        "cap_file_write": "Fayllar yaratish va o'zgartirish",
        "cap_shell": "Terminal buyruqlarini bajarish",
        "cap_desktop": "Klaviatura, sichqoncha va ekranni boshqarish",
        "workspace": "Ish papkasi (sandbox)",
        "int_weather": "Ob-havo (Open-Meteo, bepul)",
        "int_ha_url": "Home Assistant URL",
        "int_ha_token": "Home Assistant tokeni",
        "int_tg_token": "Telegram bot tokeni",
        "int_tg_send": "Telegram xabarlari / kanal postlariga ruxsat",
        "int_tg_channel": "Postlar kanali (@nomi)",
        "mem_reset": "Suhbatni tozalash",
        "mem_forget": "Butun xotirani o'chirish",
        "mem_done": "Bajarildi.",
        "link_telegram": "Telegram bog'lash",
        "link_code_info": "Botga 10 daqiqa ichida yuboring:  /link {code}",
        "not_signed_in": "Hisobga kirilmagan.",
        "error": "Xato: {error}",
    },
}


def tr(key: str, locale: str = "en", **kwargs: object) -> str:
    """Translate *key* for *locale*, falling back to English."""
    table = STRINGS.get(locale) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
