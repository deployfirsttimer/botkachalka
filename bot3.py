import json
import os
from datetime import date, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# === Настройки ===
BOT_TOKEN = "7822163888:AAE7-SSSDO7NjL6ka65gKXg9nF6e7UVyX2o"
DATA_FILE = "pushups.json"
ADMIN_ID = 1983548472
PUSHUP_DAILY_LIMIT = 1000

# === Работа с данными ===

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cleanup_old(data, keep_days=30):
    cutoff = date.today() - timedelta(days=keep_days)
    for rec in data.values():
        rec["daily"] = {d: c for d, c in rec.get("daily", {}).items() if date.fromisoformat(d) >= cutoff}

# === Клавиатура ===
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💪 Push‑up")],
        [KeyboardButton("🙋‍♂️ Мой прогресс"), KeyboardButton("📊 Топ‑день")],
        [KeyboardButton("🏆 Топ‑всё время")],
    ], resize_keyboard=True
)

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот для участников группы день первый https://t.me/+ULGBBuDQd2kzNjZi 🏋️🔥\n"
        "Я бот для отслеживания вашей статистики.\n\n"
        "Пока что я умею только это, но буду расширяться:\n"
        "📥 /pushup  — добавить количество отжиманий\n"
        "🙋‍♂️ /me — показать твой прогресс\n"
        "📊 /stats — таблица всех участников\n"
        "🏆 /alltime Топ‑всё время",
        reply_markup=MAIN_KB,
    )


# --- pushup helper ---
async def add_pushups(update, context, add):
    user = update.effective_user
    uid = str(user.id)
    data = load_data(); cleanup_old(data)

    today = date.today().isoformat()
    rec = data.setdefault(uid, {"name": user.full_name, "daily": {}, "total": 0})
    today_cnt = rec["daily"].get(today, 0)
    available = PUSHUP_DAILY_LIMIT - today_cnt
    if available <= 0:
        await update.message.reply_text(f"🚫 Лимит {PUSHUP_DAILY_LIMIT} достигнут на сегодня.")
        return
    if add > available:
        add = available
    rec["daily"][today] = today_cnt + add
    rec["total"] += add
    save_data(data)
    txt = f"Добавлено {add}! Сегодня {rec['daily'][today]}/{PUSHUP_DAILY_LIMIT}"
    if add < available:
        txt += " (достигнут лимит)"
    await update.message.reply_text(txt)

# --- команды ---
async def pushup(update: Update, context: ContextTypes.DEFAULT_TYPE):   # ← было pushup_cmd
    try:
        add = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Укажи число: /pushup 25")
        return
    await add_pushups(update, context, add)

async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    data = load_data(); cleanup_old(data)
    rec = data.get(uid)
    today = date.today().isoformat()
    if not rec:
        await update.message.reply_text("Статистика пуста.")
        return
    today_cnt = rec["daily"].get(today, 0)
    await update.message.reply_text(f"Сегодня: {today_cnt}/{PUSHUP_DAILY_LIMIT}\nВсего: {rec['total']}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE, today_only=False):
    data = load_data()
    cleanup_old(data)

    if not data:
        await update.message.reply_text("Пока пусто 😴")
        return

    if today_only:
        today = date.today().isoformat()
        board = [(rec["name"], rec.get("daily", {}).get(today, 0)) for rec in data.values()]
        title = "📊 Топ за сегодня"
    else:
        # Используем total если есть, иначе count
        board = [(rec["name"], rec.get("total", rec.get("count", 0))) for rec in data.values()]
        title = "🏆 Топ за всё время"

    board = sorted(board, key=lambda x: x[1], reverse=True)
    msg = f"{title}:\n\n"
    for i, (name, cnt) in enumerate(board, 1):
        msg += f"{i}. {name}: {cnt}\n"

    await update.message.reply_text(msg)


async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Нет прав ❌"); return
    if update.message.reply_to_message:
        target = str(update.message.reply_to_message.from_user.id)
    elif context.args:
        target = context.args[0]
    else:
        await update.message.reply_text("/reset_user <id> или ответом.")
        return
    data = load_data()
    if target in data:
        del data[target]; save_data(data)
        await update.message.reply_text("Статистика сброшена 🗑")
    else:
        await update.message.reply_text("Запись не найдена.")

# === Обработчик текстов ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower().replace("\u200d", "").replace("‑", "-")

    if "push" in text:
        await update.message.reply_text("Сколько отжиманий добавить?")
        context.user_data["await_pushup"] = True
        return

    if context.user_data.get("await_pushup"):
        if text.isdigit():
            await add_pushups(update, context, int(text))
        else:
            await update.message.reply_text("Нужно число, попробуй ещё раз.")
        context.user_data["await_pushup"] = False
        return

    if "прогресс" in text or text == "/me":
        await me(update, context)
    elif "сегодня" in text or "топ-день" in text or "📊" in text or text == "/today":
        await stats(update, context, today_only=True)
    elif "всё время" in text or "топ-всё" in text or "🏆" in text or text == "/alltime":
        await stats(update, context, today_only=False)
    else:
        await update.message.reply_text("Не понял 🤖 Попробуй ещё раз.")

# === Запуск ===

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pushup", pushup))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(CommandHandler("today", lambda u, c: stats(u, c, today_only=True)))
    app.add_handler(CommandHandler("alltime", lambda u, c: stats(u, c, today_only=False)))
    app.add_handler(CommandHandler("reset_user", reset_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен ✅")
    app.run_polling()
if __name__ == "__main__":
    main()