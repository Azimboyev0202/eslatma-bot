# 🤖 Eslatma Bot — shaxsiy vazifa va eslatmalar boti

Boshliq yoki yaqinlaringiz bergan vazifalarni unutmaslik uchun Telegram bot.
Vazifani yuborasiz → bot "qabul qilindi" deydi → belgilangan vaqtdan **10 daqiqa
oldin** sizni eslatadi (hadis va motivatsion so'zlar bilan) → bajarganingizda
"✅ Bajarildi" tugmasi orqali bajarilganlar ro'yxatiga o'tadi.

---

## ✨ Imkoniyatlari

- 📝 **Matn** yoki 🎤 **ovozli xabar** orqali vazifa qabul qiladi
- ✅ Har bir vazifaga "Qabul qilindi" deb javob beradi
- 🔔 Vaqtdan **10 daqiqa oldin** eslatadi + vazifa vaqti kelganda tekshiradi
- 💡 Eslatma bilan birga **hadis, ulamolar hikmati va motivatsion so'zlar** yuboradi
- ✅ "Bajarildi" / "⏰ Keyinroq" / "❌ Bekor qilish" tugmalari
- 📋 `/vazifalar` va `/bajarilgan` ro'yxatlari
- 💾 Hammasi SQLite bazasida saqlanadi — bot qayta ishga tushsa ham eslatmalar yo'qolmaydi

---

## 🚀 O'rnatish (5 qadam)

### 1. Bot tokenini oling
Telegramda **@BotFather** ga `/newbot` yozing, bot nomini bering va sizga
beriladigan tokenni (masalan `123456789:ABCdef...`) nusxalab oling.

### 2. Python o'rnating
Python 3.9 yoki undan yangi versiya kerak (`python --version` bilan tekshiring).

### 3. Kutubxonani o'rnating
```bash
pip install -r requirements.txt
```

### 4. Tokenni belgilang
Linux / macOS:
```bash
export BOT_TOKEN="123456789:ABCdef..."
```
Windows (PowerShell):
```powershell
$env:BOT_TOKEN="123456789:ABCdef..."
```

### 5. Botni ishga tushiring
```bash
python eslatma_bot.py
```
Endi Telegramda botingizga `/start` yozing.

---

## 📱 Qanday foydalanish

| Siz yuborasiz | Bot nima qiladi |
|---|---|
| `Boshliqqa hisobot yuborish` | "Qachon eslatay?" deb so'raydi |
| `15:30` (so'rovga javoban) | Vazifani qabul qiladi va eslatma qo'yadi |
| `ertaga 10:00 Filialga kitob yetkazish` | Vaqt + vazifani birdaniga qabul qiladi |
| 🎤 ovozli xabar | Saqlaydi, vaqt so'raydi, eslatmada o'sha ovozni qaytaradi |

**Vaqt formatlari:** `15:30` · `ertaga 09:00` · `indinga 18:00` · `25.05 14:00`

**Buyruqlar:** `/vazifalar` · `/bajarilgan` · `/bekor` · `/yordam`

---

## 🌐 Doimiy ishlashi uchun (server)

Bot kompyuter o'chganda to'xtaydi. **24 soat ishlashi uchun** uni doimiy yoqilgan
serverga (VPS) yoki always-on xizmatga joylashtirish kerak. Linux serverda
`systemd` xizmati misoli:

```ini
# /etc/systemd/system/eslatma-bot.service
[Unit]
Description=Eslatma Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/youruser/eslatma-bot
Environment=BOT_TOKEN=123456789:ABCdef...
ExecStart=/usr/bin/python3 /home/youruser/eslatma-bot/eslatma_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now eslatma-bot
```

---

## ⚙️ Sozlash

`eslatma_bot.py` faylining yuqori qismida:

- `REMIND_BEFORE_MIN = 10` — necha daqiqa oldin eslatish
- `SNOOZE_MIN = 30` — "keyinroq" tugmasi necha daqiqaga suradi
- `MOTIVATSIYA` va `TABRIK` ro'yxatlari — hadis va motivatsion so'zlarni
  xohlaganingizcha qo'shing yoki o'zgartiring

---

## 📌 Eslatma

Hozir ovozli xabar **saqlanadi va eslatmada qaytarib yuboriladi** (ya'ni topshiriqni
o'z ovozingizda yana eshitasiz). Agar ovozni avtomatik **matnga aylantirish**
(transkripsiya) kerak bo'lsa — buni alohida qo'shish mumkin, ayting.
