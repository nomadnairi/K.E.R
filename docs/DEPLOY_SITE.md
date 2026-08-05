# Как поднять сайт ker-ai.online — от А до Я

Простыми словами, по шагам. Всё делается на вашем VPS, кроме первого шага
(он в панели регистратора домена).

**Что получится в конце:**

| Адрес | Что там |
|---|---|
| `https://ker-ai.online` | Официальный сайт |
| `https://ker-ai.online/api/…` | API — сюда ходят exe, бот, Raspberry Pi |
| `https://dashboard.ker-ai.online` | Веб-кабинет (пока заглушка «скоро») |
| `https://www.ker-ai.online` | Переброс на основной адрес |

---

## Шаг 1. DNS — три записи

Зайдите в панель, где купили домен, и добавьте три **A-записи**. Везде
указывается **IP-адрес вашего VPS** (узнать: `curl -4 ifconfig.me` на сервере).

| Тип | Имя | Значение |
|---|---|---|
| A | `@` | IP вашего сервера |
| A | `www` | IP вашего сервера |
| A | `dashboard` | IP вашего сервера |

> **Все три обязательны.** Сертификат выпускается сразу на три имени, и если
> хоть одно не резолвится — Let's Encrypt откажет во всём запросе.

Записи расходятся по интернету от 5 минут до нескольких часов. Проверить, что
готово:

```bash
dig +short ker-ai.online
dig +short www.ker-ai.online
dig +short dashboard.ker-ai.online
```

Каждая команда должна вернуть IP вашего сервера. **Пока не вернули — дальше
шага 4 не идите**, сертификат не выпустится.

---

## Шаг 2. Забрать код на сервер

Важно: вся работа идёт в ветке `claude/jarvis-repository-9gp7wj`, а не в
`main`. В прошлый раз именно из-за этого `git pull` отвечал «Already up to
date», а сборка не находила файлы.

```bash
cd /root/K.E.R-server

git fetch origin claude/jarvis-repository-9gp7wj
git checkout claude/jarvis-repository-9gp7wj
git pull
```

Проверьте, что нужные файлы на месте:

```bash
ls docker-compose.prod.yml web/site/package.json
```

Обе строчки должны напечататься без ошибок.

---

## Шаг 3. Настройки в `.env`

Откройте файл `.env` в корне проекта (если его нет — `cp .env.example .env`)
и приведите эти строки к такому виду:

```env
DOMAIN=ker-ai.online
LETSENCRYPT_EMAIL=ваша@почта.ру

# Пока проверяете — оставьте 1 (тестовый сертификат, без лимитов).
# Когда всё заработает, поставьте 0 и повторите шаг 5.
CERTBOT_STAGING=1

# Чтобы вход в веб-кабинете работал и на сайте, и на поддомене.
# Точка в начале обязательна.
SESSION_COOKIE_DOMAIN=.ker-ai.online
SESSION_COOKIE_SECURE=true
```

Остальное (ключи ИИ, токен бота) уже стоит — не трогайте.

---

## Шаг 4. Собрать сайт

Сайт — это статические файлы. Их надо собрать один раз, дальше nginx просто
их отдаёт.

**Нужен Node.js 20 или новее.** Проверьте:

```bash
node --version
```

Если команда не найдена или версия ниже 20 — поставьте:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
```

Теперь сборка:

```bash
cd /root/K.E.R-server
make web-install    # только первый раз и после обновлений
make web-build      # собирает и сайт, и веб-кабинет
```

Проверьте, что получилось:

```bash
ls web/site/dist/index.html web/dashboard/dist/index.html
```

Обе строчки должны напечататься. Если да — сайт собран.

> Собрать надо **до** шага 6. Nginx подключает эти две папки как есть; если
> их нет на момент запуска, Docker создаст вместо них пустые папки и сайт
> ответит ошибкой 403.

---

## Шаг 5. Сертификат и HTTPS (автоматически)

Одна команда. Она сама создаст временный сертификат, поднимет nginx, получит
настоящий сертификат от Let's Encrypt на все три имени и перезагрузит nginx:

```bash
cd /root/K.E.R-server
./deploy/nginx/init-letsencrypt.sh
```

Скрипт печатает, что делает, шагами 1/5 … 5/5. В конце должно быть
`Done. Certificate for ker-ai.online is live.`

> **Про `CERTBOT_STAGING=1`.** Сейчас выпустится *тестовый* сертификат —
> браузер будет ругаться «небезопасно». Это нормально и специально: у
> Let's Encrypt жёсткий лимит на настоящие сертификаты (5 попыток в неделю на
> домен), и сначала надо убедиться, что всё работает.
>
> Когда убедились — поставьте в `.env` `CERTBOT_STAGING=0` и запустите скрипт
> ещё раз. Тогда придёт настоящий сертификат и замочек в браузере станет
> зелёным.

**Продление — автоматическое.** В `docker-compose.prod.yml` есть контейнер
`certbot`, который сам обновляет сертификат до истечения. Делать ничего не
нужно.

---

## Шаг 6. Запустить всё

```bash
cd /root/K.E.R-server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Подождите минуту и посмотрите, что всё поднялось:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

У всех должно быть `Up` (у `api` — ещё и `healthy`).

---

## Шаг 7. Проверка

По порядку. Если какой-то пункт не прошёл — смотрите «Если что-то пошло не
так» ниже.

```bash
# 1. Сайт отдаётся
curl -sI https://ker-ai.online | head -1
# ждём: HTTP/2 200

# 2. API живёт под /api/
curl -s https://ker-ai.online/api/
# ждём: {"name":"KER", ... "status":"online", ...}

# 3. www перебрасывает на основной адрес
curl -sI https://www.ker-ai.online | head -1
# ждём: HTTP/2 301

# 4. Поддомен кабинета отвечает
curl -sI https://dashboard.ker-ai.online | head -1
# ждём: HTTP/2 200
```

> С `CERTBOT_STAGING=1` curl будет ругаться на сертификат — добавьте `-k`,
> чтобы проверить саму работу: `curl -skI https://ker-ai.online | head -1`.

И откройте `https://ker-ai.online` в браузере — должен быть тёмный сайт с
зелёным акцентом.

---

## Шаг 8. Переключить exe на новый адрес

Теперь в настройках desktop-приложения вместо старого IP с портом 8000 надо
указать:

```
https://ker-ai.online/api
```

То же самое для любого другого клиента — Raspberry Pi, скрипт-агент:

```bash
export KER_SERVER_URL=https://ker-ai.online/api
export KER_API_KEY=ваш-ключ
python -m jarvis.desktop.agent
```

> Старый адрес `http://IP:8000` продолжает работать — порт не закрывался.
> Можно переводить клиентов по очереди, не торопясь.

---

## Как обновлять сайт потом

Когда я внесу изменения:

```bash
cd /root/K.E.R-server
git pull
make deploy-web           # пересобрать статику и перезагрузить nginx
```

Если менялся Python-код (бот, API):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## Если что-то пошло не так

**Сайт не открывается, браузер пишет «не удаётся установить соединение»**

Проверьте, что DNS доехал (шаг 1) и что nginx запущен:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx --tail 50
```

**Открывается, но пустая белая страница (или 403)**

Значит статики нет. Пересоберите:
```bash
make web-build && ls web/site/dist/
```
Внутри должны быть `index.html` и папка `assets`. После этого перезапустите
nginx, чтобы он подхватил папку:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate nginx
```

**`/api/` отвечает 502 Bad Gateway**

Не поднялся контейнер `api`. Смотрите его логи:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api --tail 100
```

**Скрипт сертификата ругается на challenge**

Значит одно из трёх имён не резолвится. Вернитесь к шагу 1 и проверьте все
три `dig`-команды.

**Вход по коду из Telegram даёт ошибку**

Сначала посмотрите настоящую причину — она в логах, а не в тексте ошибки:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api --tail 100
```
Учтите: код одноразовый. Если он уже был использован (даже неудачно), нужен
новый из бота.

**Нужно всё перезапустить**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

---

## Что осталось незакрытым (честно)

1. **Два файла бэкенда ещё не в этой ветке** — `jarvis/api/app.py` и
   `jarvis/licensing/service.py`. Из-за этого пока нет эндпоинта
   `GET /api/status` (поэтому в шаге 7 проверка идết на `/api/`),
   `устройства`/`автоматизации` для веб-кабинета и ответа 503 вместо голого
   500 при сбое базы. На работу сайта, бота, exe и входа по коду это не
   влияет — главное исправление HTTP 500 (миграция `ALTER TABLE`) уже в
   ветке.

2. **Шрифт Inter не приложен.** В стилях он указан первым, но файлы не
   лежат в репозитории — сейчас сайт покажется системным шрифтом (на Windows
   это Segoe UI, выглядит достойно). Чтобы поставить настоящий Inter,
   положите `InterVariable.woff2` в `web/site/public/fonts/` и добавьте
   `@font-face` в `web/site/src/styles.css`.

3. **Конфиг nginx не проверен командой `nginx -t`** в моём окружении —
   там не было запущенного Docker. Синтаксис я вычитал, но первый запуск
   стоит делать, глядя в `logs nginx`.

4. **Веб-кабинет — заглушка.** Бэкенд под него готов (вход по коду через
   cookie, память, тарифы), интерфейс — следующая задача.

5. **Цена в тарифах** взята из кода: Plus = 2500 Telegram Stars, Pro = 8000.
   В присланном макете было 299 ₽ и 899 ₽ — это разные величины примерно в
   15 раз. Сайт показывает то, что реально спишет бот. Если цифры в коде
   неверные — скажите, поменяю в одном месте
   (`web/site/src/config/plans.ts` и `jarvis/billing/plans.py`).
