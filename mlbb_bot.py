import json
import logging
import os
import re
import time
from typing import Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

import os 
BOT_TOKEN = os.getenv("BOT_TOKEN")

SEEN_FILE = "seen_orders.json"
DUPLICATE_TTL = 43200  # 3 minute

ID_SERVER_PATTERNS = [
    re.compile(r"\b(\d{6,14})\s*\((\d{3,8})\)"),
    re.compile(r"\b(\d{6,14})\s*/\s*(\d{3,8})"),
]

KEYWORDS = [
    "twilight pass", "weekly elite", "monthly epic",
    "500+500", "250+250", "150+150", "50+50",
    "11483", "9288", "5532", "4390", "3688", "2901", "2195",
    "1755", "1584", "1412", "1220", "1135", "1049", "963",
    "878", "792", "706", "600", "514", "429", "344", "343",
    "257", "172", "110", "86", "wp"
]


def load_seen_orders() -> dict:
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_seen_orders(data: dict) -> None:
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning("Could not save seen orders: %s", e)


SEEN_ORDERS = load_seen_orders()


def cleanup_seen_orders() -> None:
    now = int(time.time())
    expired = [k for k, ts in SEEN_ORDERS.items() if now - int(ts) > DUPLICATE_TTL]
    for k in expired:
        SEEN_ORDERS.pop(k, None)
    if expired:
        save_seen_orders(SEEN_ORDERS)


def contains_keyword(text: str) -> bool:
    text_l = text.lower()
    return any(k in text_l for k in KEYWORDS)


def extract_id_server(text: str) -> Optional[Tuple[str, str]]:
    for pattern in ID_SERVER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1), match.group(2)
    return None


def extract_wp(text: str) -> Optional[str]:
    text_l = text.lower()

    m1 = re.search(r"\bwp\s*(\d+)\b", text_l)
    if m1:
        return f"{m1.group(1)}wp"

    m2 = re.search(r"\b(\d+)\s*wp\b", text_l)
    if m2:
        return f"{m2.group(1)}wp"

    if re.search(r"\bwp\b", text_l):
        return "wp"

    return None


def extract_name(message) -> str:
    user = message.from_user
    if user:
        if user.username:
            return f"@{user.username}"
        full_name = " ".join(
            part for part in [user.first_name, user.last_name] if part
        ).strip()
        if full_name:
            return full_name
    return "Unknown User"


def build_keyboard(id_value: str, server_value: str, wp_value: Optional[str]) -> InlineKeyboardMarkup:
    if wp_value:
        copy_text = f"{id_value}({server_value}) {wp_value}"
    else:
        copy_text = f"{id_value}({server_value})"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ðŸ“‹ Copy", switch_inline_query_current_chat=copy_text)]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("âœ… MLBB Copy Bot Ready")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Seen orders: {len(SEEN_ORDERS)}\nDuplicate TTL: {DUPLICATE_TTL} seconds"
    )


async def clear_seen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SEEN_ORDERS.clear()
    save_seen_orders(SEEN_ORDERS)
    await update.message.reply_text("ðŸ§¹ Duplicate list cleared")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    text = ""
    if message.text:
        text += message.text + "\n"
    if message.caption:
        text += message.caption

    text = text.strip()
    if not text:
        return

    result = extract_id_server(text)
    if not result:
        return

    cleanup_seen_orders()

    id_value, server_value = result
    wp_value = extract_wp(text)
    buyer_name = extract_name(message)

    if wp_value:
        order_key = f"{id_value}({server_value}) {wp_value}".lower()
    else:
        order_key = f"{id_value}({server_value})".lower()

    now = int(time.time())
    last_seen = SEEN_ORDERS.get(order_key)

    if last_seen and (now - int(last_seen) <= DUPLICATE_TTL):
        if wp_value:
            alert_text = f"âš ï¸ Duplicate Receipt\n{buyer_name}\n{id_value}({server_value}) {wp_value}"
        else:
            alert_text = f"âš ï¸ Duplicate Receipt\n{buyer_name}\n{id_value}({server_value})"

        await message.reply_text(alert_text)
        return

    if not contains_keyword(text):
        return

    SEEN_ORDERS[order_key] = now
    save_seen_orders(SEEN_ORDERS)

    if wp_value:
        output = f"{buyer_name}\n{id_value}({server_value}) {wp_value}"
    else:
        output = f"{buyer_name}\n{id_value}({server_value})"

    await message.reply_text(
        output,
        reply_markup=build_keyboard(id_value, server_value, wp_value),
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("clearseen", clear_seen))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
