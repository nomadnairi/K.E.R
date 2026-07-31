# K.E.R. — Production-инфраструктура

Reverse proxy (Nginx), автоматический HTTPS (Let's Encrypt), защищённая
Docker-сеть и готовая база (Postgres/Redis) для будущего Admin Dashboard.

Это чисто инфраструктурная фаза: код `jarvis/` не менялся, замечания
Security Audit (Critical/High/Medium) не исправлялись — см. раздел
["Рекомендации для фазы Security Audit Fix"](#рекомендации-для-фазы-security-audit-fix)
в конце документа.

Всё описанное здесь — конфигурационные файлы в репозитории. У меня (агента)
нет SSH-доступа к вашему VPS, поэтому применяете вы сами по шагам ниже.

## Содержание

1. [Схема инфраструктуры](#1-схема-инфраструктуры)
2. [Схема сети Docker](#2-схема-сети-docker)
3. [Быстрый старт](#3-быстрый-старт)
4. [Настройка домена](#4-настройка-домена)
5. [Настройка DNS](#5-настройка-dns)
6. [Настройка Nginx](#6-настройка-nginx)
7. [Настройка HTTPS (Let's Encrypt)](#7-настройка-https-lets-encrypt)
8. [Автоматическое продление сертификатов](#8-автоматическое-продление-сертификатов)
9. [Проверка успешного продления](#9-проверка-успешного-продления)
10. [Обновление / принудительный перевыпуск сертификата](#10-обновление--принудительный-перевыпуск-сертификата)
11. [Резервное копирование конфигурации](#11-резервное-копирование-конфигурации)
12. [Обслуживание](#12-обслуживание)
13. [Postgres / Redis — задел для Admin Dashboard](#13-postgres--redis--задел-для-admin-dashboard)
14. [Порт 8000 — переходный период](#14-порт-8000--переходный-период)
15. [Рекомендации для фазы Security Audit Fix](#15-рекомендации-для-фазы-security-audit-fix)

---

## 1. Схема инфраструктуры

```mermaid
flowchart LR
    U["Пользователи /\nDesktop-клиент"] -->|HTTPS :443| N[Nginx]
    U -.->|"HTTP :8000\n(временно, см. §14)"| API
    LE["Let's Encrypt"] <-->|ACME HTTP-01| N
    N -->|proxy_pass| API[api\nFastAPI + WebSocket]
    N -.->|"будущее: /admin"| AD["Admin Dashboard\n(ещё не реализован)"]
    N -.->|"будущее: www.domain"| SITE["Официальный сайт\n(ещё не реализован)"]
    API --> BOT[bot\nTelegram]
    API -.->|"не используется\nсегодня"| PG[(Postgres)]
    API -.->|"не используется\nсегодня"| RD[(Redis)]
    API --> DB[("SQLite\ndata/*.db\n(volume)")]
    CB[certbot] <-->|обновление сертификата| LE
    CB -->|"пишет в общий volume"| N
```

- **Nginx** — единственная точка входа снаружи (порты 80/443).
- **api** — существующий FastAPI-контейнер (без изменений кода).
- **certbot** — отдельный контейнер, только продлевает сертификат.
- **Postgres/Redis** — подняты, но ничем сегодня не используются (задел).
- **Admin Dashboard** и **официальный сайт** — будущие проекты, места под
  них зарезервированы в конфиге Nginx (закомментированы, см. §6).

## 2. Схема сети Docker

```mermaid
flowchart TB
    subgraph host["Хост (VPS)"]
        subgraph edge["Docker-сеть: ker_edge"]
            NGINX[nginx]
        end
        subgraph backend["Docker-сеть: ker_backend"]
            NGINX
            API[api]
            BOT[bot / bot-personal]
            PG[(postgres)]
            RD[(redis)]
            CB[certbot]
        end
    end
    INTERNET((Интернет)) -->|"80/443\n(published)"| NGINX
    INTERNET -.->|"8000\n(published, временно)"| API
```

Правило простое и проверяемое: **только у `nginx` (и временно у `api`, см.
§14) есть `ports:` наружу**. У `postgres`, `redis`, `bot`, `certbot` портов
наружу нет вообще — снаружи хоста они недостижимы в принципе, а не благодаря
файрволу. Проверка:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
# в колонке PORTS у postgres/redis/bot/certbot должно быть пусто
```

## 3. Быстрый старт

```bash
cp .env.example .env
# заполните DOMAIN, LETSENCRYPT_EMAIL, POSTGRES_PASSWORD, при желании REDIS_PASSWORD

# когда DNS уже указывает на этот сервер (см. §4-5):
deploy/nginx/init-letsencrypt.sh        # один раз

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Без домена (проверить, что всё поднимается, ничего не сломав) можно
пропустить `init-letsencrypt.sh` и просто не запускать `nginx`/`certbot`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api bot postgres redis
```

Обычный `docker compose -f docker-compose.yml up -d` (без оверлея) продолжает
работать ровно как раньше — оверлей ничего не ломает.

## 4. Настройка домена

Let's Encrypt не выпускает сертификаты на голый IP — нужен домен.

1. Купите домен у любого регистратора (Namecheap, Reg.ru, Cloudflare
   Registrar и т.д.).
2. Пропишите в `.env`:
   ```
   DOMAIN=ваш-домен.ru
   LETSENCRYPT_EMAIL=ваш-email@пример.com
   ```
3. Дальше см. §5 (DNS) и §7 (HTTPS).

## 5. Настройка DNS

У регистратора/DNS-провайдера добавьте A-запись, указывающую на текущий IP
сервера (`#####`, если это по-прежнему тот же VPS):

| Тип | Имя | Значение | TTL   |
|-----|-----|----------|-------|
| A   | @   | #####    | 3600  |
| A   | www | #####    | 3600  |

Проверка распространения DNS перед запуском `init-letsencrypt.sh`:

```bash
dig +short ваш-домен.ru
# должно вернуть #####
```

Если возвращает пусто или старый IP — подождите (обычно 5 минут – несколько
часов, зависит от TTL и провайдера) и проверьте снова. Certbot откажет в
выпуске сертификата, пока DNS не указывает на сервер.

## 6. Настройка Nginx

Всё лежит в `deploy/nginx/`:

- `nginx.conf` — общие настройки (gzip, HTTP/2, таймауты, безопасный формат
  логов, `server_tokens off`).
- `templates/ker.conf.template` — серверные блоки; `${DOMAIN}` подставляется
  автоматически образом `nginx` при старте контейнера (встроенный механизм
  `envsubst`, ограниченный только переменной `DOMAIN` через
  `NGINX_ENVSUBST_FILTER` — остальные `$-переменные` Nginx не трогаются).
- `snippets/ssl-params.conf` — параметры TLS (см. §7).
- `snippets/security-headers.conf` — HTTP security-заголовки (см. ниже).

Что проксируется в `location`-блоках `ker.conf.template` (сверено с реальным
кодом `jarvis/api/app.py`, ничего не выдумано):

| Путь | Назначение | Особенность |
|---|---|---|
| `/ws/` | Чат-стриминг, `@app.websocket("/ws/{session_id}")` (app.py:318) | `Upgrade`/`Connection: upgrade`, `proxy_read_timeout 3600s` |
| `= /dashboard/ws` | Живой дашборд, `@app.websocket("/dashboard/ws")` (app.py:445) | То же самое |
| `\.(js\|css\|png\|...)$` | Статика | `expires 30d`, кэш на клиенте |
| `/` | Всё остальное: REST API, `/app`, `/auth/*`, `/health` | Стандартный proxy_pass |

**Security Headers** (`snippets/security-headers.conf`), включены на все
ответы `:443`: `Strict-Transport-Security`, `Content-Security-Policy`,
`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`,
`Permissions-Policy`. CSP подобран под то, что реально есть в статических
страницах (`jarvis/api/static/*.html` используют инлайновые `<script>`, без
внешних CDN/шрифтов — проверено чтением файлов) — поэтому
`script-src`/`style-src` включают `'unsafe-inline'`, иначе дашборд
сломается. Ужесточение CSP (уход от `unsafe-inline` на nonce/hash) —
отдельная задача, требующая правки самих HTML-страниц, вне рамок этой фазы.

Проверить синтаксис конфига в любой момент:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -t
```

## 7. Настройка HTTPS (Let's Encrypt)

Реализовано в `deploy/nginx/init-letsencrypt.sh` (запускается один раз,
вручную, когда DNS уже настроен):

1. Генерирует временный self-signed сертификат — иначе Nginx не сможет
   стартовать (нужен хоть какой-то файл сертификата для блока `443 ssl`).
2. Запускает Nginx с этим временным сертификатом.
3. Удаляет временный сертификат и запрашивает настоящий у Let's Encrypt
   методом `webroot` (ACME HTTP-01 challenge через `/.well-known/acme-challenge/`,
   который Nginx уже обслуживает на порту 80).
4. Перезагружает Nginx с настоящим сертификатом.

```bash
chmod +x deploy/nginx/init-letsencrypt.sh   # уже выставлено в репозитории
deploy/nginx/init-letsencrypt.sh
```

По умолчанию `.env` содержит `CERTBOT_STAGING=1` — вы получите **staging**
сертификат Let's Encrypt (не вызывает доверия у браузера, но не имеет лимитов
на количество попыток — безопасно гонять сколько угодно раз, пока всё не
заработает). Когда всё проверено:

```bash
# в .env: CERTBOT_STAGING=0
deploy/nginx/init-letsencrypt.sh   # безопасно перезапускать — сам удалит старый сертификат
```

TLS-параметры (`snippets/ssl-params.conf`) — профиль Mozilla "Intermediate":
TLS 1.2 + 1.3, современные шифры, OCSP stapling, `ssl_session_tickets off`.

## 8. Автоматическое продление сертификатов

Без единого ручного действия после первоначальной настройки:

- Контейнер `certbot` каждые **12 часов** выполняет `certbot renew`. Certbot
  сам решает, нужно ли реально продлевать — он делает это только в последние
  **30 дней** до истечения срока действия, так что этот цикл — дешёвый и
  безопасный опрос, а не постоянный перевыпуск.
- Nginx **сам себя перезагружает** каждые 6 часов
  (`deploy/nginx/docker-entrypoint-wrapper.sh`) — так подхватывается
  обновлённый сертификат из общего volume без общения между контейнерами
  напрямую (никакого монтирования Docker-сокета — меньше поверхность атаки).
  Перезагрузка с неизменившимся сертификатом безвредна (Nginx просто
  перечитывает те же файлы).

Итого: с момента продления сертификата до его фактического подхвата Nginx
проходит не больше 6 часов — при том что до истечения остаётся ещё до 30
дней запаса. Ручных действий не требуется никогда, если только Let's
Encrypt не меняет протокол ACME или у сервера не пропадает доступ в
интернет/DNS не рвётся.

## 9. Проверка успешного продления

**Автоматически:** у контейнера `certbot` настроен Docker `healthcheck`
(`deploy/nginx/check-cert-renewal.sh`), который проверяет, что до истечения
сертификата осталось не меньше 20 дней. Если продление тихо перестало
работать, это сразу видно:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
# столбец STATUS у certbot покажет "unhealthy"
```

**Вручную, в любой момент:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    exec certbot /scripts/check-cert-renewal.sh
```

Выведет дату истечения сертификата и статус (`OK`/`FAIL`). Также можно
посмотреть логи самого certbot:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs certbot --tail 50
```

## 10. Обновление / принудительный перевыпуск сертификата

Обычно ничего делать не нужно (см. §8). Если нужно принудительно перевыпустить
(например, поменяли домен, или подозреваете компрометацию приватного ключа):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" -d "$DOMAIN" --force-renewal \
    --rsa-key-size 4096 --agree-tos --no-eff-email

docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```

Переход с staging на боевой сертификат — см. конец §7 (`CERTBOT_STAGING=0` +
повторный запуск `init-letsencrypt.sh`).

## 11. Резервное копирование конфигурации

Что нужно сохранять (инфраструктурные файлы — не данные приложения, у тех
свой volume-бэкап):

| Что | Где | Как забэкапить |
|---|---|---|
| `.env` (домен, пароли, ключи) | корень репозитория, **не в git** | `cp .env /безопасное/место/.env.bak-$(date +%F)` — храните отдельно от репозитория, это секреты |
| `deploy/nginx/**` | в git | уже версионируется — `git log`/откат стандартными средствами git |
| `docker-compose*.yml` | в git | то же самое |
| Сертификаты Let's Encrypt | named volume `ker_certbot_etc` | `docker run --rm -v ker_certbot_etc:/etc/letsencrypt -v $(pwd):/backup alpine tar czf /backup/letsencrypt-$(date +%F).tar.gz -C / etc/letsencrypt` |
| Логи Nginx | `./logs/nginx/` (bind mount) | обычный файловый бэкап хоста, если нужно; логи и так ротируются (§12) |

Восстановление сертификатов из бэкапа:

```bash
docker run --rm -v ker_certbot_etc:/etc/letsencrypt -v $(pwd):/backup alpine \
    tar xzf /backup/letsencrypt-ДАТА.tar.gz -C /
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

`.env` **никогда** не коммитьте — он в `.gitignore` (проверено:
`.env`/`.env.local`/`*.env`/`.env.*` игнорируются, кроме `.env.example`).

## 12. Обслуживание

**Логи.** Nginx пишет реальные файлы (не просто в stdout) в `./logs/nginx/`
(`access.log`, `error.log`), формат — безопасный, без query-строк (см. §15).
Ротация — стандартный `logrotate` на хосте:

```bash
sudo cp deploy/nginx/logrotate/ker-nginx /etc/logrotate.d/ker-nginx
# отредактируйте путь /opt/ker внутри файла, если репозиторий лежит не там
sudo logrotate -d /etc/logrotate.d/ker-nginx   # тестовый прогон (dry-run)
```

Ежедневная ротация, хранится 14 дней со сжатием, `postrotate`-хук сам
командует Nginx переоткрыть файлы (`nginx -s reopen`).

**Обновление образов** (Nginx/Postgres/Redis/Certbot):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull nginx postgres redis certbot
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx postgres redis certbot
```

**Безопасный перезапуск Nginx** (без разрыва соединений — graceful reload):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```

**Место на диске.** Логи ротируются автоматически; Postgres/Redis volumes
растут только если что-то реально начнёт их использовать (сегодня — нет).
Периодически проверяйте:

```bash
docker system df
du -sh logs/nginx/
```

**Проверка состояния всего стека:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -I https://ваш-домен.ru/health
```

## 13. Postgres / Redis — задел для Admin Dashboard

Подняты в `docker-compose.prod.yml`, сеть `ker_backend`, без публикации
портов наружу. `jarvis/` их сегодня **не использует** — `settings.py`'s
`database_url`/`redis_url` остались как были (неиспользуемые дефолты), и
менять их в рамках этой фазы не входило в задачу.

Когда бэкенд Admin Dashboard будет готов подключаться, из любого контейнера
на сети `ker_backend` (например, будущего `admin-dashboard` сервиса,
добавленного в `docker-compose.prod.yml` тем же способом, что и остальные)
строки подключения будут такими:

```
postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
redis://:${REDIS_PASSWORD}@redis:6379/0     # или без пароля, если REDIS_PASSWORD пуст
```

(`postgres`/`redis` — это DNS-имена контейнеров внутри сети `ker_backend`,
не публичные адреса — снаружи Docker-сети они недостижимы.)

## 14. Порт 8000 — переходный период

Существующий десктоп-клиент K.E.R. зашит на `http://#####:8000` напрямую
(`jarvis/desktop_app/assets.py`). Чтобы не сломать уже установленные копии,
`docker-compose.yml` **не менялся** — порт 8000 продолжает публиковаться
напрямую из контейнера `api`, параллельно с новым входом через Nginx на
80/443.

Когда выйдет новая сборка десктоп-клиента с адресом
`https://ваш-домен.ru` (это отдельная задача — правка `assets.py`, вне рамок
текущей инфраструктурной фазы), порт 8000 можно закрыть:

```yaml
# в docker-compose.yml, сервис api — удалить или закомментировать:
    ports:
      - "8000:8000"
```

и на файрволе хоста (`ufw deny 8000` / аналог), если он используется.

## 15. Рекомендации для фазы Security Audit Fix

Не исправлялось в этой фазе (по прямому указанию — инфраструктура и
безопасность приложения разделены на разные фазы). Переносится в список
для следующей фазы:

1. **uvicorn access-log всё ещё пишет query-string.** Nginx теперь не
   логирует query-строки в своём access.log (см. `nginx.conf` — `log_format
   ker_safe` логирует `$uri`, а не `$request`) — это закрывает утечку токена
   `?key=...` (High #2 из прошлого Security Audit) для тех, кто читает **логи
   Nginx**. Но сам `uvicorn` внутри контейнера `api` по-прежнему пишет полный
   `$request`, включая query-string, в свой access-лог (`jarvis/api/__main__.py:30`,
   `uvicorn.run(...)` без `access_log=False`). Это правка кода приложения —
   не делалась.
2. **uvicorn не знает о прокси.** `jarvis/api/__main__.py` не передаёт
   `proxy_headers=True`/`forwarded_allow_ips` в `uvicorn.run(...)`, поэтому
   приложение не доверяет `X-Forwarded-For`/`X-Forwarded-Proto` от Nginx —
   значит `request.client.host` в логах/аудите приложения будет показывать
   IP контейнера Nginx, а не реального пользователя, и приложение не может
   надёжно узнать, что запрос пришёл по HTTPS. Однобайтовая правка
   (`uvicorn.run(..., proxy_headers=True, forwarded_allow_ips="*")`), но это
   код приложения — оставлено на усмотрение следующей фазы.
3. Порт 8000 (см. §14) — закрыть после выхода новой сборки клиента.
4. Остальные пункты (Critical #1 — argon2-cffi/cryptography отсутствуют в
   образе; Medium #3 — нет rate-limiting на auth-эндпоинтах; Medium #4 — 422
   эхает входные данные) — без изменений, как и было зафиксировано в
   `docs/SECURITY_AUDIT_REPORT.md` / отчёте от 31.07.2026. Инфраструктура
   этой фазы их не устраняет и не маскирует.
