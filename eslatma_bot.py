#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eslatma Bot — shaxsiy vazifa va eslatmalar uchun Telegram bot.

Imkoniyatlari:
  * Matn yoki ovozli xabar orqali vazifa qabul qiladi
  * "Qabul qilindi" deb javob beradi
  * Belgilangan vaqtdan 10 daqiqa oldin eslatadi
  * Eslatma bilan birga hadis / ulamolar hikmati / motivatsiya yuboradi
  * Bajarilganda "Bajarildi" tugmasi bilan bajarilganlar ro'yxatiga o'tkazadi
  * Vazifalar SQLite bazasida saqlanadi (bot qayta ishga tushsa ham yo'qolmaydi)

Ishga tushirish: BOT_TOKEN environment o'zgaruvchisini belgilang va shu faylni ishga tushiring.
"""

import os
import re
import random
import logging
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, Defaults,
)

# ----------------------------- Sozlamalar -----------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
DB_PATH = os.environ.get("DB_PATH", "eslatma.db")
TZ = ZoneInfo("Asia/Tashkent")          # Toshkent vaqti (UTC+5)
REMIND_BEFORE_MIN = 10                  # vazifadan necha daqiqa oldin eslatish
SNOOZE_MIN = 30                         # "keyinroq" tugmasi necha daqiqaga suradi
HTML = ParseMode.HTML

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("eslatma_bot")

# ------------------------- Motivatsion kontent -------------------------------
# Bu ro'yxatlarni xohlaganingizcha o'zgartirib, to'ldirib chiqishingiz mumkin.
MOTIVATSIYA = [
    "💡 «Allohga eng suyukli amal — oz bo'lsa-da, doimiy bajariladiganidir.»\n— Hadis (Buxoriy, Muslim)",
    "💡 «Ikki ne'mat borki, ko'p odamlar ularning qadriga yetmaydi: sog'liq va bo'sh vaqt.»\n— Hadis (Buxoriy)",
    "💡 «Munofiqning belgisi uchta: gapirsa yolg'on so'zlaydi, va'da bersa bajarmaydi, omonatga xiyonat qiladi.»\n— Hadis (Buxoriy, Muslim)",
    "💡 «Har bir ish niyatiga qarab baholanadi.»\n— Hadis (Buxoriy, Muslim)",
    "💡 «Omonati yo'q kishining komil imoni yo'q, ahdiga vafo qilmaganning dini yo'q.»\n— Hadis (Imom Ahmad)",
    "💡 «Qariligingdan oldin yoshligingni, bandlikdan oldin bo'sh vaqtingni g'animat bil.»\n— Hadis (Hokim)",
    "💡 «Kuchli mo'min Allohga zaif mo'mindan ko'ra suyukliroq va yaxshiroqdir.»\n— Hadis (Muslim)",
    "✨ «Vaqt qilichga o'xshaydi: uni kesmasang, u seni kesadi.»\n— Imom Shofe'iy (rahimahulloh)",
    "✨ «Ey inson, sen kunlardan iboratsan. Bir kun o'tsa, sening bir qisming ham o'tib ketadi.»\n— Hasan al-Basriy (rahimahulloh)",
    "✨ «Ilm — amal bilan, amal — ixlos bilan kamol topadi.»\n— Salaf ulamolari hikmatidan",
    "✨ «Bugungi ishni ertaga qoldirgan kishi ko'pincha uni umuman bajarmaydi.»\n— Hikmat",
    "🚀 «Kichik, ammo doimiy qadamlar — eng katta manzillarga ham olib boradi.»",
    "🚀 «Mas'uliyatni his qilgan inson — o'ziga bo'lgan ishonchni oqlaydi.»",
    "🚀 «Ishni boshlash — uni tugatishning yarmidir. Hoziroq boshlang!»",
    "🚀 «Sabr va izchillik — har qanday muvaffaqiyatning kalitidir.»",
    "🚀 «Sizga ishonishdi. Bu ishonchni amalingiz bilan mustahkamlang.»",
]

TABRIK = [
    "🎉 Barakalla! Yana bir vazifa bajarildi.",
    "🎉 Ajoyib! Sizga bo'lgan ishonch yana bir bor oqlandi.",
    "🎉 Zo'r! Bajarilgan ish — tinch vijdon demakdir.",
    "🎉 Mana shu — mas'uliyatli inson belgisi. Davom eting!",
    "🎉 Yana bir qadam oldinga! O'zingiz bilan faxrlaning.",
]

# ------------------------------- Baza ----------------------------------------
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                chat_id       INTEGER NOT NULL,
                text          TEXT,
                voice_file_id TEXT,
                due_ts        TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                created_ts    TEXT NOT NULL,
                completed_ts  TEXT
            )
        """)
    logger.info("Baza tayyor: %s", DB_PATH)


def db_add_task(user_id, chat_id, text, voice_file_id, due, created):
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, chat_id, text, voice_file_id, due_ts, status, created_ts) "
            "VALUES (?,?,?,?,?, 'pending', ?)",
            (user_id, chat_id, text, voice_file_id, due.isoformat(), created.isoformat()),
        )
        return cur.lastrowid


def db_get_task(task_id):
    with _db() as conn:
        return conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()


def db_update_status(task_id, status):
    completed = datetime.now(TZ).isoformat() if status == "done" else None
    with _db() as conn:
        conn.execute("UPDATE tasks SET status=?, completed_ts=? WHERE id=?",
                     (status, completed, task_id))


def db_update_due(task_id, due):
    with _db() as conn:
        conn.execute("UPDATE tasks SET due_ts=? WHERE id=?", (due.isoformat(), task_id))


def db_list_pending(user_id):
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE user_id=? AND status='pending' ORDER BY due_ts",
            (user_id,),
        ).fetchall()


def db_list_done(user_id, limit=20):
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE user_id=? AND status='done' "
            "ORDER BY completed_ts DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def db_all_pending():
    with _db() as conn:
        return conn.execute("SELECT * FROM tasks WHERE status='pending'").fetchall()


# --------------------------- Vaqtni o'qish -----------------------------------
def parse_time_string(text, now):
    """
    Matndan vaqtni ajratib oladi.
    Qo'llab-quvvatlanadigan formatlar:
        15:30                  -> bugun (agar o'tib ketgan bo'lsa — ertaga)
        ertaga 09:00
        indinga 09:00
        bugun 18:00
        25.05 14:00 / 25.05.2026 14:00
    Natija: (due_datetime | None, qolgan_matn)
    """
    original = text.strip()
    low = original.lower()

    day_offset = 0
    if "ertaga" in low:
        day_offset = 1
    elif re.search(r"indin", low):
        day_offset = 2
    # "bugun" -> offset 0 (alohida amal kerak emas)

    base_date = (now + timedelta(days=day_offset)).date()
    explicit_date = False

    # aniq sana: dd.mm yoki dd.mm.yyyy
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b", low)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = m.group(3)
        if y:
            y = int(y)
            y += 2000 if y < 100 else 0
        else:
            y = now.year
        try:
            base_date = datetime(y, mo, d).date()
            explicit_date = True
        except ValueError:
            pass

    # vaqt: hh:mm
    tm = re.search(r"\b(\d{1,2}):(\d{2})\b", low)
    if not tm:
        return None, original
    hh, mm = int(tm.group(1)), int(tm.group(2))
    if hh > 23 or mm > 59:
        return None, original

    due = datetime(base_date.year, base_date.month, base_date.day,
                   hh, mm, tzinfo=TZ)

    # sana ko'rsatilmagan va vaqt o'tib ketgan bo'lsa -> ertangi kunga
    if day_offset == 0 and not explicit_date and due <= now:
        due += timedelta(days=1)

    # qolgan matnni tozalash (vazifa tavsifi)
    leftover = re.sub(r"\bertaga\b|\bbugun\b|\bindin\w*\b", "", original, flags=re.I)
    if explicit_date:
        leftover = re.sub(r"\b\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b", "", leftover)
    leftover = re.sub(r"\b\d{1,2}:\d{2}\b", "", leftover)
    leftover = leftover.strip(" ,.-—:\n\t")
    return due, leftover


def format_dt(dt):
    now = datetime.now(TZ)
    d = dt.date()
    if d == now.date():
        return f"Bugun {dt.strftime('%H:%M')}"
    if d == (now + timedelta(days=1)).date():
        return f"Ertaga {dt.strftime('%H:%M')}"
    return dt.strftime("%d.%m.%Y %H:%M")


# --------------------------- Ish rejalashtirish ------------------------------
def schedule_task_jobs(job_queue, task_id, chat_id, due):
    """Vazifa uchun eslatma (10 daq oldin) va tekshiruv (vaqtida) joblarini qo'yadi."""
    now = datetime.now(TZ)
    data = {"task_id": task_id, "chat_id": chat_id}
    reminder_at = due - timedelta(minutes=REMIND_BEFORE_MIN)

    if reminder_at > now:
        job_queue.run_once(reminder_job, reminder_at, data=data, name=f"rem_{task_id}")
    elif due > now:
        job_queue.run_once(reminder_job, 3, data=data, name=f"rem_{task_id}")

    if due > now:
        job_queue.run_once(due_job, due, data=data, name=f"due_{task_id}")
    else:
        job_queue.run_once(due_job, 5, data=data, name=f"due_{task_id}")


def cancel_task_jobs(job_queue, task_id):
    for name in (f"rem_{task_id}", f"due_{task_id}"):
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()


def task_keyboard(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Bajarildi", callback_data=f"done_{task_id}")],
        [
            InlineKeyboardButton(f"⏰ {SNOOZE_MIN} daqiqaga sur", callback_data=f"snooze_{task_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{task_id}"),
        ],
    ])


# ------------------------------ Job callbacklar ------------------------------
async def _send_task_notice(context, task, header):
    """Vazifa eslatmasini matn yoki ovoz ko'rinishida yuboradi."""
    motiv = random.choice(MOTIVATSIYA)
    body = f"{header}\n\n📌 <b>{task['text']}</b>\n\n{motiv}"
    kb = task_keyboard(task["id"])
    chat_id = task["chat_id"]
    if task["voice_file_id"]:
        await context.bot.send_voice(chat_id, task["voice_file_id"],
                                     caption=body, parse_mode=HTML, reply_markup=kb)
    else:
        await context.bot.send_message(chat_id, body, parse_mode=HTML, reply_markup=kb)


async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    task = db_get_task(context.job.data["task_id"])
    if not task or task["status"] != "pending":
        return
    await _send_task_notice(
        context, task,
        f"🔔 <b>Eslatma!</b> {REMIND_BEFORE_MIN} daqiqadan so'ng quyidagi vazifa bor:")


async def due_job(context: ContextTypes.DEFAULT_TYPE):
    task = db_get_task(context.job.data["task_id"])
    if not task or task["status"] != "pending":
        return
    await _send_task_notice(
        context, task,
        "⏰ <b>Vaqti keldi!</b> Ushbu vazifani bajardingizmi?")


# ------------------------------- Buyruqlar -----------------------------------
START_TEXT = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "Men — sizning shaxsiy <b>eslatma botingizman</b>. Boshliq yoki yaqinlaringiz "
    "bergan vazifalarni unutmasligingizga yordam beraman.\n\n"
    "📝 <b>Qanday foydalanish kerak:</b>\n"
    "1. Menga vazifani <b>matn</b> yoki <b>ovozli xabar</b> qilib yuboring.\n"
    "2. Men «Qachon eslatay?» deb so'rayman — vaqtni yozing.\n"
    "3. Belgilangan vaqtdan <b>10 daqiqa oldin</b> sizni eslatib qo'yaman "
    "(motivatsiya va hikmatli so'zlar bilan).\n"
    "4. Bajarib bo'lsangiz «✅ Bajarildi» tugmasini bosing — vazifa "
    "bajarilganlar ro'yxatiga o'tadi.\n\n"
    "⏰ <b>Vaqt formatlari:</b>\n"
    "• <code>15:30</code> — bugun\n"
    "• <code>ertaga 09:00</code>\n"
    "• <code>25.05 14:00</code>\n\n"
    "Vazifani to'g'ridan-to'g'ri vaqt bilan ham yozsangiz bo'ladi, masalan:\n"
    "<code>ertaga 10:00 Boshliqqa hisobot yuborish</code>\n\n"
    "📋 <b>Buyruqlar:</b>\n"
    "/vazifalar — bajarilmagan vazifalar\n"
    "/bajarilgan — bajarilgan vazifalar\n"
    "/bekor — joriy kiritishni bekor qilish\n"
    "/yordam — yordam"
)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT, parse_mode=HTML)


async def bekor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Joriy kiritish bekor qilindi.")


async def vazifalar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db_list_pending(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("📭 Hozircha bajarilmagan vazifalar yo'q. Barakalla!")
        return
    lines = ["📋 <b>Bajarilmagan vazifalar:</b>\n"]
    rows = []
    for i, t in enumerate(tasks, 1):
        due = datetime.fromisoformat(t["due_ts"])
        mark = "🎤 " if t["voice_file_id"] else ""
        lines.append(f"{i}. {mark}{t['text']} — 🗓 {format_dt(due)}")
        short = (t["text"][:22] + "…") if len(t["text"]) > 22 else t["text"]
        rows.append([InlineKeyboardButton(f"✅ {short}", callback_data=f"done_{t['id']}")])
    await update.message.reply_text("\n".join(lines), parse_mode=HTML,
                                    reply_markup=InlineKeyboardMarkup(rows))


async def bajarilgan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = db_list_done(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("📭 Hali bajarilgan vazifalar yo'q.")
        return
    lines = ["✅ <b>Bajarilgan vazifalar:</b>\n"]
    for i, t in enumerate(tasks, 1):
        when = ""
        if t["completed_ts"]:
            when = " — " + datetime.fromisoformat(t["completed_ts"]).strftime("%d.%m %H:%M")
        lines.append(f"{i}. {t['text']}{when}")
    await update.message.reply_text("\n".join(lines), parse_mode=HTML)


# --------------------------- Vazifa yaratish ---------------------------------
async def create_task(update, context, text, voice, due):
    user = update.effective_user
    chat_id = update.effective_chat.id
    now = datetime.now(TZ)
    task_id = db_add_task(user.id, chat_id, text or "🎤 Ovozli vazifa", voice, due, now)
    schedule_task_jobs(context.job_queue, task_id, chat_id, due)

    reminder_at = due - timedelta(minutes=REMIND_BEFORE_MIN)
    note = ""
    if due <= now:
        note = "\n\n⚠️ <i>E'tibor bering: bu vaqt allaqachon o'tib ketgan.</i>"
    await update.message.reply_text(
        "✅ <b>Qabul qilindi!</b>\n\n"
        f"📌 Vazifa: {text or '🎤 Ovozli vazifa'}\n"
        f"🗓 Vaqti: {format_dt(due)}\n"
        f"🔔 Eslatma: {format_dt(reminder_at)} da ({REMIND_BEFORE_MIN} daqiqa oldin)"
        f"{note}",
        parse_mode=HTML,
    )


# ----------------------------- Xabar handlerlari -----------------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (update.message.text or "").strip()
    if not msg:
        return
    ud = context.user_data
    state = ud.get("state")
    now = datetime.now(TZ)

    # 1) Vaqt kutilmoqda (vazifa matni allaqachon olingan)
    if state == "await_time":
        due, _ = parse_time_string(msg, now)
        if not due:
            await update.message.reply_text(
                "⏰ Vaqtni tushunolmadim. Masalan: <code>15:30</code>, "
                "<code>ertaga 09:00</code>, <code>25.05 14:00</code>",
                parse_mode=HTML)
            return
        await create_task(update, context,
                           text=ud.get("pending_text"),
                           voice=ud.get("pending_voice"),
                           due=due)
        ud.clear()
        return

    # 2) Vazifa matni kutilmoqda (vaqt allaqachon olingan)
    if state == "await_text":
        due = datetime.fromisoformat(ud["pending_due"])
        await create_task(update, context, text=msg, voice=None, due=due)
        ud.clear()
        return

    # 3) Yangi vazifa
    due, leftover = parse_time_string(msg, now)
    if due and leftover:
        await create_task(update, context, text=leftover, voice=None, due=due)
        return
    if due and not leftover:
        ud.clear()
        ud["state"] = "await_text"
        ud["pending_due"] = due.isoformat()
        await update.message.reply_text("✍️ Vaqtni oldim. Endi vazifa matnini yozing:")
        return

    # vaqt topilmadi -> matnni saqlab, vaqt so'raymiz
    ud.clear()
    ud["state"] = "await_time"
    ud["pending_text"] = msg
    ud["pending_voice"] = None
    await update.message.reply_text(
        f"📥 Vazifa qabul qilindi:\n«{msg}»\n\n"
        "⏰ Qachon eslatay? (masalan: <code>15:30</code>, <code>ertaga 09:00</code>)",
        parse_mode=HTML)


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    media = update.message.voice or update.message.audio
    if not media:
        return
    ud = context.user_data
    ud.clear()
    ud["state"] = "await_time"
    ud["pending_voice"] = media.file_id
    ud["pending_text"] = (update.message.caption or "🎤 Ovozli vazifa").strip()
    await update.message.reply_text(
        "🎤 Ovozli xabar qabul qilindi. Eslatma vaqtida uni sizga qaytarib yuboraman.\n\n"
        "⏰ Qachon eslatay? (masalan: <code>15:30</code>, <code>ertaga 09:00</code>)",
        parse_mode=HTML)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, _, sid = query.data.partition("_")
    try:
        task_id = int(sid)
    except ValueError:
        return
    task = db_get_task(task_id)
    if not task:
        await query.answer("Vazifa topilmadi.", show_alert=True)
        return

    if action == "done":
        db_update_status(task_id, "done")
        cancel_task_jobs(context.job_queue, task_id)
        await _finalize(query, f"{random.choice(TABRIK)}\n\n📌 {task['text']}\n"
                               "<i>Bajarilganlar ro'yxatiga o'tkazildi.</i>")

    elif action == "snooze":
        new_due = datetime.now(TZ) + timedelta(minutes=SNOOZE_MIN)
        db_update_due(task_id, new_due)
        cancel_task_jobs(context.job_queue, task_id)
        schedule_task_jobs(context.job_queue, task_id, task["chat_id"], new_due)
        await _finalize(query, f"⏰ <b>{SNOOZE_MIN} daqiqaga keyinga surildi.</b>\n"
                               f"Yangi vaqt: {format_dt(new_due)}")

    elif action == "cancel":
        db_update_status(task_id, "cancelled")
        cancel_task_jobs(context.job_queue, task_id)
        await _finalize(query, f"❌ <b>Bekor qilindi:</b> {task['text']}")


async def _finalize(query, text):
    """Tugma bosilgach, xabarni yangilaydi (matn yoki ovoz bo'lishidan qat'i nazar)."""
    try:
        if query.message.text is not None:
            await query.edit_message_text(text, parse_mode=HTML)
        elif query.message.caption is not None:
            await query.edit_message_caption(caption=text, parse_mode=HTML)
        else:
            await query.edit_message_reply_markup(None)
            await query.message.reply_text(text, parse_mode=HTML)
    except Exception as e:
        logger.warning("Xabarni yangilashda xatolik: %s", e)
        try:
            await query.edit_message_reply_markup(None)
        except Exception:
            pass
        await query.message.reply_text(text, parse_mode=HTML)


async def error_handler(update, context):
    logger.error("Xatolik: %s", context.error, exc_info=context.error)


# ------------------------------ Ishga tushish --------------------------------
async def on_startup(app: Application):
    """Bot qayta ishga tushganda kutilayotgan vazifalarni qaytadan rejalashtiradi."""
    init_db()
    now = datetime.now(TZ)
    count = 0
    for task in db_all_pending():
        due = datetime.fromisoformat(task["due_ts"])
        if due > now:
            schedule_task_jobs(app.job_queue, task["id"], task["chat_id"], due)
        else:
            # vaqti o'tib ketgan — ishga tushgach darhol eslatamiz
            app.job_queue.run_once(due_job, 5,
                                   data={"task_id": task["id"], "chat_id": task["chat_id"]},
                                   name=f"due_{task['id']}")
        count += 1
    logger.info("Qayta rejalashtirildi: %d ta vazifa", count)


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "XATO: BOT_TOKEN belgilanmagan!\n"
            "Avval @BotFather dan token oling, so'ng:\n"
            "  export BOT_TOKEN='123456:ABC...'\n"
            "buyrug'i bilan o'rnating."
        )
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(Defaults(tzinfo=TZ))
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler(["start"], start_cmd))
    app.add_handler(CommandHandler(["yordam", "help"], start_cmd))
    app.add_handler(CommandHandler("vazifalar", vazifalar_cmd))
    app.add_handler(CommandHandler("bajarilgan", bajarilgan_cmd))
    app.add_handler(CommandHandler("bekor", bekor_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi. To'xtatish uchun Ctrl+C bosing.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
