import os
import json
from io import BytesIO
from datetime import time
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# إعدادات البوت
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]

SOURCE_URL = "https://www.gtamap.net/gta-online/daily/gun-van"

SAUDI_TZ = ZoneInfo("Asia/Riyadh")

DATA_FILE = "chats.json"

KEYWORDS = {
    "شاحنة الأسلحة",
    "شاحنة الاسلحة",
    "تاجر الأسلحة",
    "تاجر الاسلحة",
    "شاحنة",
    "تاجر",
}


# =========================
# حفظ القروبات
# =========================

def load_chats():

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_chat(chat_id):

    chats = load_chats()

    chat_id = str(chat_id)

    if chat_id not in chats:
        chats.append(chat_id)

        with open(
            DATA_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                chats,
                file,
                ensure_ascii=False,
                indent=2
            )


# =========================
# جلب موقع الشاحنة
# =========================

async def get_gun_van():

    headers = {
        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
    }

    async with aiohttp.ClientSession(
        headers=headers
    ) as session:

        async with session.get(
            SOURCE_URL,
            timeout=30
        ) as response:

            response.raise_for_status()

            html = await response.text()

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    # البحث عن Spot والإحداثيات

    import re

    pattern = re.search(
        r"Spot\s*#(\d+).*?"
        r"(-?\d+(?:\.\d+)?)\s*,\s*"
        r"(-?\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )

    if not pattern:

        raise ValueError(
            "لم يتم العثور على موقع الشاحنة."
        )

    spot = int(pattern.group(1))

    x = float(pattern.group(2))

    y = float(pattern.group(3))

    return spot, x, y


# =========================
# إنشاء صورة صغيرة
# =========================

def create_map_image(
    spot,
    x,
    y
):

    width = 700
    height = 420

    image = Image.new(
        "RGB",
        (width, height),
        "#202020"
    )

    draw = ImageDraw.Draw(image)

    # شبكة الخريطة

    for i in range(
        0,
        width,
        50
    ):
        draw.line(
            (i, 0, i, height),
            fill="#383838",
            width=1
        )

    for i in range(
        0,
        height,
        50
    ):
        draw.line(
            (0, i, width, i),
            fill="#383838",
            width=1
        )

    # نطاق إحداثيات GTA

    min_x = -3500
    max_x = 4500

    min_y = -4500
    max_y = 8000

    px = int(
        (x - min_x)
        / (max_x - min_x)
        * width
    )

    py = int(
        (1 - (y - min_y)
        / (max_y - min_y))
        * height
    )

    px = max(
        25,
        min(width - 25, px)
    )

    py = max(
        70,
        min(height - 25, py)
    )

    # عنوان

    draw.rectangle(
        (0, 0, width, 55),
        fill="#111111"
    )

    draw.text(
        (20, 18),
        f"Gun Van — الموقع #{spot}",
        fill="white"
    )

    # علامة الموقع

    r = 20

    draw.ellipse(
        (
            px - r,
            py - r,
            px + r,
            py + r
        ),
        fill="#e53935",
        outline="white",
        width=4
    )

    # علامة 🚐 بشكل بسيط

    draw.rectangle(
        (
            px - 12,
            py - 8,
            px + 12,
            py + 8
        ),
        fill="white"
    )

    draw.ellipse(
        (
            px - 10,
            py + 5,
            px - 3,
            py + 12
        ),
        fill="#111111"
    )

    draw.ellipse(
        (
            px + 3,
            py + 5,
            px + 10,
            py + 12
        ),
        fill="#111111"
    )

    # الإحداثيات

    draw.text(
        (20, height - 30),
        f"X: {x}   Y: {y}",
        fill="white"
    )

    output = BytesIO()

    image.save(
        output,
        format="PNG"
    )

    output.seek(0)

    return output


# =========================
# إرسال موقع الشاحنة
# =========================

async def send_gun_van(
    bot,
    chat_id
):

    try:

        spot, x, y = (
            await get_gun_van()
        )

        image = create_map_image(
            spot,
            x,
            y
        )

        caption = (
            "🚐 شاحنة الأسلحة اليوم\n\n"
            f"📍 الموقع رقم: {spot}\n"
            f"🗺️ الإحداثيات: {x}, {y}\n\n"
            "⏰ التحديث اليومي: 9:00 صباحًا 🇸🇦\n"
            "🔎 المصدر: GTAMap.net"
        )

        await bot.send_photo(
            chat_id=chat_id,
            photo=image,
            caption=caption
        )

    except Exception as error:

        print(
            "Gun Van Error:",
            repr(error)
        )

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ ما قدرت أجيب موقع "
                "شاحنة الأسلحة حاليًا."
            )
        )


# =========================
# /start
# =========================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    if not chat:
        return

    save_chat(chat.id)

    await update.message.reply_text(
        "✅ تم تسجيل القروب.\n\n"
        "🚐 البوت جاهز لشاحنة الأسلحة.\n"
        "⏰ التحديث يوميًا الساعة 9:00 صباحًا.\n\n"
        "اكتب «شاحنة» أو «تاجر» للحصول على الموقع."
    )


# =========================
# /شاحنة
# =========================

async def truck_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    if not chat:
        return

    save_chat(chat.id)

    await send_gun_van(
        context.bot,
        chat.id
    )


# =========================
# الكلمات
# =========================

async def keyword_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat = update.effective_chat

    if not chat:
        return

    text = (
        update.message.text
        .strip()
        .lower()
    )

    keywords = {
        word.lower()
        for word in KEYWORDS
    }

    if text in keywords:

        save_chat(chat.id)

        await send_gun_van(
            context.bot,
            chat.id
        )


# =========================
# التحديث اليومي
# =========================

async def daily_update(
    context: ContextTypes.DEFAULT_TYPE
):

    chats = load_chats()

    print(
        f"Daily update: {len(chats)} chats"
    )

    for chat_id in chats:

        try:

            await send_gun_van(
                context.bot,
                int(chat_id)
            )

            # تأخير بسيط بين القروبات

            await asyncio.sleep(1)

        except Exception as error:

            print(
                "Chat Error:",
                chat_id,
                repr(error)
            )


# =========================
# تشغيل البوت
# =========================

def main():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /start

    app.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    # /شاحنة

    app.add_handler(
        CommandHandler(
            "شاحنة",
            truck_command
        )
    )

    # الكلمات

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            keyword_handler
        )
    )

    # الساعة 9 صباحًا

    app.job_queue.run_daily(
        daily_update,
        time=time(
            hour=9,
            minute=0,
            tzinfo=SAUDI_TZ
        ),
        name="gun_van_daily"
    )

    print(
        "🚐 Gun Van Bot Started"
    )

    print(
        "⏰ Daily: 09:00 Asia/Riyadh"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
