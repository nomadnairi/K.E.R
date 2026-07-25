<div align="center">

# KER

**O'zingizning shaxsiy AI yordamchingiz — nomini o'zingiz beradigan, o'zingiz ishga tushiradigan va haqiqatan ham o'zingizniki bo'lgan.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/Version-1.9.6-orange)](https://github.com/nomadnairi/K.E.R/releases)

[English](README.md) · [Русский](README.ru.md) · **O'zbek**

</div>

---

## Bu nima

KER — bu o'zingizda joylashtiriladigan shaxsiy AI yordamchi. U bilan Telegramda
yoki desktop ilovada suhbatlashasiz, ortida esa haqiqiy dvigatel ishlaydi:
suhbatlaringizni eslab qoladi, biror ishni haqiqatan bajarish uchun
vositalarni chaqiradi, gapiradi va eshitadi, vazifalarni jadval bo'yicha
bajaradi hamda aqlli uyga ulanadi.

Uni "navbatdagi chat ustidan qobiq"dan ikki narsa ajratib turadi:

- **U sizniki.** Hech qanday nom qat'iy o'rnatilmagan. Uni KER deb ataysizmi,
  boshqacha deysizmi — har kim o'z yordamchisiga o'z nomini berishi mumkin va u
  o'sha nomga (istasangiz, ikkinchi taxallusga ham) javob beradi. O'z kalitingiz,
  o'z serveringiz, o'z ma'lumotlaringiz.
- **Bu skript emas, yaxlit mahsulot.** Buyruqlar o'rniga tugmalar bilan ishlaydigan
  ozoda Telegram-bot, jonli boshqaruv paneli bilan desktop "Command Deck",
  akkauntlar va tariflar, avto-yangilanishlar — buni boshqalarga berish (yoki
  sotish) uchun kerak bo'ladigan hamma narsa.

Hammasi lokal ishlaydi. Oddiy narsalar (vaqt, kalkulyator, diagnostika) API
kalitisiz ham ishlaydi.

> **⚡ Bepul va to'liq versiya.** Bu yerda, GitHubda, faqat **bepul yadro** —
> o'z yordamchingizni ishga tushirish uchun yetarli. **To'liq versiya** (barcha
> premium imkoniyatlar va yuqori limitlar) **faqat Telegram-bot orqali**,
> obuna asosida mavjud. Botni ishga tushiring: [@jar_v1_s](https://t.me/jar_v1_s).

---

## Variantlar (Editions)

KER dan qanchasini olishni tanlaysiz. Tariflar (Free / Plus / Pro) har qanday
variant *ichida* ishlaydi — ular variantdan alohida.

| Variant | Nima kiradi | Holati |
|---|---|---|
| 🤖 **KER Bot** | Telegram yordamchi | ✅ mavjud |
| 💻 **KER Desktop** | Telegram-bot + desktop (`.exe`) | ✅ mavjud |
| 🏠 **KER Home** | Telegram-bot + desktop + Raspberry Pi ovoz | 🔜 tez orada |

---

## U nima qila oladi

**Gaplashish va eslab qolish.** Matn yoki ovoz bilan suhbat. Uning haqiqiy
xotirasi bor — qayta ishga tushgach ham suhbatlaringizni eslaydi va ulardan siz
haqingizdagi barqaror faktlarni ajratib oladi. Joylashtirilgan parollar,
tokenlar va karta raqamlari saqlanishdan oldin olib tashlanadi.

**Haqiqatan ish bajarish.** Model shunchaki javob bermaydi — u vositalarni
chaqira oladi: internetdan qidirish, fayllarni o'qish va yozish, terminalda
buyruqlar bajarish, kompyuterni boshqarish, ob-havoni ko'rish, aqlli uy bilan
gaplashish. Xavfli imkoniyatlar sukut bo'yicha o'chirilgan va bittalab yoqiladi.

**Yangi vositalarni ulash (MCP).** KER Model Context Protocol tilida
gaplashadi, shuning uchun istalgan MCP-server vositalari yordamchining o'z
ko'nikmalariga aylanadi. Konfiguratsiyani ko'rsating yoki serverni to'g'ridan-
to'g'ri paneldan qo'shing.

**Mustaqil ishlash.** "Har kuni soat 9:00 da xulosa qil" yoki "har 3 soatda
pochtani tekshir" deng — u vazifani jadvalga qo'yadi, bajaradi, natijani
yuboradi va keyingi ishga tushishni o'zi qayta rejalashtiradi.

**Tilingizni tushunish.** Butun interfeys va javoblar o'zbek, rus va ingliz
tillarida. Ovozli xabar yuboring — u tanib oladi, javob beradi va javobni siz
gapirgan tilda ovozda aytib berishi mumkin. Ovozni to'liq bepul va oflayn ishga
tushirish mumkin.

**"Miya"ni tanlash.** Anthropic (Claude), OpenAI (GPT), OpenRouter yoki lokal
model (Ollama, LM Studio, vLLM, llama.cpp) bilan ishlaydi — lokalni olsangiz,
bulut kaliti umuman kerak emas. Qayta urinish va provayderlar o'rtasida
almashishni o'zi qiladi, router esa oson savollarni tez modelga, murakkablarini
kuchli modelga yuboradi.

---

## Uni o'zingizniki qiling (white-label)

Aynan boshqa yordamchilar bermaydigan narsa.

- **Nom bering.** Sukut bo'yicha — **KER**, lekin har bir foydalanuvchi
  yordamchisini bot sozlamalaridan qayta nomlashi mumkin: yangi nom menyuda,
  javoblarda va desktop panelda ko'rinadi. Operator butun o'rnatma uchun sukut
  nomini belgilashi mumkin.
- **Qo'shimcha nomlar.** `ASSISTANT_ALIASES` ni belgilang — u bir nechta nomga
  javob beradi (shaxsiy "uyg'otish so'zi" sifatida qulay). Sukut bo'yicha bo'sh,
  toki birovga bergan nusxangiz "toza" qolsin.
- **O'z kalitingiz, serveringiz, ma'lumotingiz.** Foydalanuvchi hatto o'z
  API-kalitini ulashi mumkin (BYOK). Hech narsa yashirincha jo'natilmaydi.

```env
ASSISTANT_NAME=KER
ASSISTANT_ALIASES=Jarvis   # ixtiyoriy — ikkalasiga ham javob beradi
```

---

## Tez boshlash

**Kerak bo'ladi:** Python 3.10+ va API kalit (yoki lokal model).

```bash
git clone https://github.com/nomadnairi/K.E.R.git
cd K.E.R

python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # ANTHROPIC_API_KEY (yoki OPENAI_API_KEY) qo'shing,
                                 # yoki lokal modelni ko'rsating
python -m jarvis
```

`make` yoqadimi? `make install`, `make run`, `make test`, `make lint`.

---

## Telegramda suhbat — to'liq versiya

KER dan foydalanishning eng qulay va eng to'liq yo'li — **tayyor bot**:
**[@jar_v1_s](https://t.me/jar_v1_s)**. Hech narsa o'rnatish yoki ko'tarish shart
emas — bu boshqariladigan mahsulot. Tugmali bot (buyruqsiz), har kimni alohida
eslaydi, ovozda javob beradi, va tariflar (Free / Plus / Pro) premium
imkoniyatlar hamda yuqori limitlarni ochadi.

Sozlamalar ozoda ichma-ich menyularda: til, yordamchi nomi, AI modeli, xotira,
ovoz, integratsiyalar va boshqalar.

---

## Desktop — "Command Deck"

`jarvis-desktop` — bu haqiqiy desktop ilova (PySide6, Windows `.exe` ga
yig'iladi), ichida jonli veb-panel bilan: animatsiyali reaktor bilan bosh ekran
va tizim telemetriyasi, tarixli chat, modellar katalogi, MCP-serverlar va
sozlamalar — hammasi ichki lokal API orqali haqiqiy dvigatelga ulangan va real
vaqtda yangilanadi.

Egasi uni lokal, kompyuterini to'liq boshqarib ishga tushiradi; boshqalar login/
parol yoki bot bergan **Telegram kirish kodi** bilan kirib, cheklangan versiyani
oladi. Ilova yangilanishlarni o'zi tekshirib o'rnata oladi.

Yuklab olishlar (Windows o'rnatuvchisi + portativ yig'ma) —
[**Releases**](https://github.com/nomadnairi/K.E.R/releases) sahifasida.

---

## Raspberry Pi (tez orada)

Raspberry Pi da doim tinglaydigan ovozli yordamchi — xonaning istalgan
joyidan nomi bilan chaqirasiz, u javob beradi (Toni Stark uslubida). O'rnatish
qo'llanmasi va image shu yerda paydo bo'ladi.

---

## Open core

Bu repozitoriy — **ochiq yadro**: dvigatel va desktop-mijoz, MIT ostida.
**To'liq boshqariladigan mahsulot** (tayyor bot, obunalar, akkauntlar va
yangilanishlar) — bu xizmat, [@jar_v1_s](https://t.me/jar_v1_s) orqali. Yadroni
o'zingiz ham ishga tushirishingiz mumkin; siz tayyor xizmat qulayligi uchun
to'laysiz.

---

## Ichki tuzilishi

Python 3.10+, hammasi asinxron. Provayderdan mustaqil LLM-mijoz qayta urinish va
zaxira bilan, tez determinatsiyalangan yo'lli ko'nikma/vosita tizimi, semantik
qidiruvli SQLite xotira, pub/sub hodisalar shinasi, imkoniyatlarni cheklovchi
xavfsizlik qatlami, FastAPI + WebSocket va aiogram Telegram-boti. Konfiguratsiya
tiplashtirilgan (pydantic-settings). Testlar — pytest, lint — har commitda ruff.

To'liq manzara va komponentlar holati — [VISION.md](VISION.md) va
[ROADMAP.md](ROADMAP.md) da, arxitektura — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) da.

---

## Keyingi qadamlar

Tayyor: yordamchi yadrosi, xotira, Telegram-bot, ovoz, integratsiyalar, API,
desktop Command Deck, MCP, vazifalarni avtomatlashtirish, avto-yangilanishlar,
akkauntlar va tariflar, hamda nom bo'yicha to'liq white-label.

Rejada: Raspberry Pi da doim tinglaydigan ovozli yordamchi (xonaning istalgan
joyidan nomi bilan chaqirish), yangi integratsiyalar (kalendar, pochta) va
ko'p-xonali stsenariylar.

---

## Hissa va aloqa

Hissa qo'shishga xush kelibsiz — [CONTRIBUTING.md](CONTRIBUTING.md) ga qarang va,
iltimos, avval `make test` va `make lint` ni ishga tushiring.

- Telegram: [@deathgu11](https://t.me/deathgu11)
- Kanal: [@jar_v1_s](https://t.me/jar_v1_s)
- Xatolar va g'oyalar: [GitHub Issues](https://github.com/nomadnairi/K.E.R/issues)

Litsenziya — [MIT](LICENSE).
