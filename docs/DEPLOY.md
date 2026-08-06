# Развёртывание KER на VPS

Здесь описаны два способа запустить KER на сервере: **Docker** (рекомендуется)
и служба **systemd**. Оба поднимают одни и те же два процесса:

- **API** — HTTP/WebSocket-сервер (`python -m jarvis.api`), к нему ходят
  desktop- и мобильные клиенты и скрипты.
- **Бот** — интерфейс Telegram (`python -m jarvis.interfaces.telegram_bot`).
  Работает через long-polling, **открытый входящий порт не нужен**.

У них общие каталоги `data/` (память в SQLite) и `logs/` (журнал аудита),
поэтому ассистент помнит вас independently от того, откуда вы пришли.

---

## 1. Что нужно заранее

- Linux-VPS (лучше Ubuntu 22.04+ или Debian 12+). Хватит 1 vCPU и 1 ГБ RAM.
- Ключ к языковой модели: `ANTHROPIC_API_KEY` (или `OPENAI_API_KEY`).
- По желанию — токен Telegram-бота от [@BotFather](https://t.me/BotFather).

### Сначала — безопасность

- **Задайте `API_KEY`.** С пустым ключом API *открыт всем*. Сгенерируйте
  стойкий:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Никогда не коммитьте `.env`.** Он живёт только на сервере. В репозитории
  лежит лишь `.env.example`.
- Опасные возможности на сервере держите выключенными (`ALLOW_SHELL`,
  `ALLOW_FILE_WRITE`, `ALLOW_DESKTOP_CONTROL` = `false`), если они вам
  действительно не нужны.

---

## 2. Docker (рекомендуется)

Поставьте Docker и плагин Compose, затем:

```bash
git clone https://github.com/nomadnairi/J.A.R.V.I.S.git jarvis
cd jarvis

cp .env.example .env
nano .env            # впишите ANTHROPIC_API_KEY, API_KEY и (по желанию) TELEGRAM_BOT_TOKEN

docker compose up -d --build
```

Проверка:

```bash
docker compose ps
curl -fsS http://localhost:8000/health | python -m json.tool
docker compose logs -f            # следить за логами (Ctrl-C — перестать следить)
```

Обновление до новой версии:

```bash
git pull
docker compose up -d --build
```

> **Изменения не появляются?** Обычная причина — устаревший образ или
> контейнер, который так и не пересоздали. Возьмите надёжный скрипт
> передеплоя: он делает pull, пересобирает **без кеша**, принудительно
> пересоздаёт контейнеры и печатает стартовый отчёт бота (версия и включён ли
> гейт подписки):
>
> ```bash
> bash deploy/redeploy.sh
> ```
>
> При старте бот пишет строку, начинающуюся с `SUBSCRIPTION GATE:` — `ON` и
> имя канала, если `TELEGRAM_REQUIRED_CHANNEL` задан и бот админ канала, либо
> `OFF`, если гейт не настроен. Если написано OFF — значит, в запущенном
> окружении он просто не включён; никакая правка кода его не включит, пока не
> выставлена эта переменная.

Остановить / удалить:

```bash
docker compose down               # именованные тома (ваши данные) остаются
docker compose down -v            # заодно удаляет тома data и logs
```

> **Нужен только API** (без Telegram-бота)? Оставьте `TELEGRAM_BOT_TOKEN`
> пустым и запустите один сервис: `docker compose up -d --build api`.

### Два бота: публичный (продажи) и личный (ваш)

Один и тот же образ поднимает сколько угодно ботов — достаточно дать каждому
свой токен и свой env-файл. Типовая схема — **два**:

- **Публичный бот** — продающий, для пользователей (сервис `bot` по
  умолчанию): гейт подписки включён, `/buy` работает, клиенты пользуются, вы
  управляете ими через админ-панель. Настраивается в `.env`.
- **Личный бот** — ваш приватный KER с **отдельным токеном** и собственной
  памятью: без гейта, без продаж, только вы.

```bash
cp .env.personal.example .env.personal   # второй токен от @BotFather, ваш id
docker compose --profile personal up -d bot-personal
```

Код один и тот же, изолируют их токен и том с данными — клиенты публичного
бота и ваши личные переписки никогда не смешаются. Тот, кто склонирует
репозиторий, получит только **код**: токены, база и админский id лежат в ваших
`.env` (их не коммитят), так что запустить он сможет лишь свой пустой
экземпляр, а до вашего не дотянется.

### Опции сборки

- **Образ поменьше, без голоса:** `ffmpeg` нужен только для локального Whisper
  (`STT_BACKEND=local`). Пропустить его:
  `docker build --build-arg WITH_VOICE=false -t jarvis-assistant .`
- **За корпоративным прокси с подменой TLS:** положите PEM-бандл вашего прокси
  рядом с Dockerfile под именем `extra-ca.crt` — он сам добавится в хранилище
  доверия контейнера (файл в gitignore, коммитить его нельзя).
- Если Docker Hub у вас заблокирован, сначала вытяните базовый образ через
  зеркало Google:
  `docker pull mirror.gcr.io/library/python:3.11-slim && docker tag mirror.gcr.io/library/python:3.11-slim python:3.11-slim`

---

## 3. systemd (без Docker)

Запуск прямо на хосте, под отдельным пользователем и в virtualenv.

```bash
# Создать служебного пользователя и каталог приложения
sudo useradd --system --create-home --home-dir /opt/jarvis jarvis
sudo -u jarvis git clone https://github.com/nomadnairi/J.A.R.V.I.S.git /opt/jarvis

cd /opt/jarvis
sudo -u jarvis python3 -m venv .venv
sudo -u jarvis .venv/bin/pip install --upgrade pip
sudo -u jarvis .venv/bin/pip install -r requirements.txt
sudo -u jarvis .venv/bin/pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "aiogram>=3.0,<4.0"

# Настроить
sudo -u jarvis cp .env.example .env
sudo -u jarvis nano .env          # впишите свои ключи
sudo -u jarvis mkdir -p data logs

# Установить юниты
sudo cp deploy/systemd/jarvis-api.service /etc/systemd/system/
sudo cp deploy/systemd/jarvis-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-api jarvis-bot
```

Управление:

```bash
systemctl status jarvis-api jarvis-bot
journalctl -u jarvis-api -f
sudo systemctl restart jarvis-api
```

После `git pull` при необходимости переустановите зависимости и перезапустите:

```bash
cd /opt/jarvis && sudo -u jarvis git pull
sudo systemctl restart jarvis-api jarvis-bot
```

---

## 4. Как безопасно выставить API наружу

API слушает `:8000`. Для всего, кроме локальных проверок, ставьте его за
обратный прокси с TLS, а не открывайте порт напрямую.

Минимальный пример для nginx:

```nginx
server {
    listen 443 ssl;
    server_name jarvis.example.com;

    # ssl_certificate / ssl_certificate_key — например, от certbot

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        # Апгрейд до WebSocket для /ws/{session}
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
```

Дальше обращайтесь со своим ключом:

```bash
curl -s https://jarvis.example.com/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Good evening."}'
```

Чек-лист для публичного развёртывания:

- [ ] `API_KEY` — длинный случайный секрет.
- [ ] Файрвол пропускает только 443 (и 22); `:8000` наружу не смотрит.
- [ ] TLS терминируется на прокси.
- [ ] `ALLOW_SHELL` / `ALLOW_FILE_WRITE` / `ALLOW_DESKTOP_CONTROL` остаются
      `false`, если они вам правда не нужны.
- [ ] `TELEGRAM_ALLOWED_USERS` ограничивает бота вашими user id.

---

## 5. Здоровье и разбор проблем

- **Здоровье:** `GET /health` возвращает проверки по подсистемам (модель,
  память, интеграции, состояние безопасности). `ok: true` — всё зелёное.
- **Логи:** Docker — `docker compose logs -f`; systemd —
  `journalctl -u jarvis-api -f`.
- **След аудита:** чувствительные действия пишутся в `logs/audit.log`
  (секреты вымараны).
- **Бот не отвечает:** убедитесь, что `TELEGRAM_BOT_TOKEN` задан и процесс
  живёт; бот работает исходящим long-polling, входящий порт ему не нужен.
