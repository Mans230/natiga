# -*- coding: utf-8 -*-
"""
بوت تليجرام لنتيجة الثانوية العامة 2026 (نظام حديث + نظام قديم).

بحث تلقائي بالكامل: المستخدم يرسل رقم الجلوس أو الاسم، والبوت يبحث
في النظامين تلقائيًا ويعرض النتيجة بدرجات المواد التفصيلية.

التشغيل:
    export BOT_TOKEN="التوكن_من_BotFather"
    python bot.py

يعتمد على python-telegram-bot v21+ (واجهة async) و long polling.
"""

import asyncio
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from youm7 import fetch_subjects, format_subjects_result

from search import (
    DATASETS,
    MAX_NAME_RESULTS,
    format_result,
    format_summary,
    load_all,
    search_auto,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 أهلًا بك في <b>بوت نتيجة الثانوية العامة 2026</b>\n\n"
    "🔍 <b>طريقة الاستخدام:</b>\n"
    "• أرسل <b>رقم الجلوس</b> (مثال: 2001970) للبحث المباشر.\n"
    "• أو أرسل <b>اسم الطالب</b> (كاملًا أو جزءًا منه) للبحث بالاسم.\n\n"
    "💡 يمكنك كتابة الأرقام بالعربية (٢٠٠١٩٧٠) أو الإنجليزية.\n"
    "✍️ ومش لازم تدقق في الحروف — البحث بيتجاهل تلقائيًا:\n"
    "الهمزات (أ / إ / آ / ا) والتاء المربوطة (ة / ه) "
    "والألف المقصورة (ى / ي)، يعني «أحمد» زي «احمد» بالظبط.\n\n"
    "❓ للمساعدة في أي وقت أرسل /help"
)

HELP_TEXT = (
    "❓ <b>مساعدة</b>\n\n"
    "هذا البوت يتيح لك معرفة نتيجة الثانوية العامة 2026 "
    "(نظام حديث ونظام قديم):\n\n"
    "1️⃣ <b>البحث برقم الجلوس:</b>\n"
    "اكتب رقم الجلوس فقط — مثال: <code>2001970</code>\n"
    "وستظهر النتيجة بدرجات كل مادة بالتفصيل.\n\n"
    "2️⃣ <b>البحث بالاسم:</b>\n"
    "اكتب الاسم أو جزءًا منه — مثال: <code>احمد محمود السيد</code>\n"
    "وستظهر لك كل الأسماء المطابقة (حتى 20 نتيجة)، واضغط "
    "«📚 عرض درجات المواد» تحت أي نتيجة لعرض درجاتها.\n\n"
    "📌 لا يهم اختلاف الهمزات (أ/إ/آ) أو التاء المربوطة (ة/ه) "
    "أو الألف المقصورة (ى/ي) — البحث يتعامل معها تلقائيًا.\n\n"
    "🆘 <b>للدعم أو الاستفسار:</b> @hostrdp"
)

NO_RESULTS_TEXT = (
    "😕 <b>لم يتم العثور على نتائج.</b>\n\n"
    "💡 تأكد من:\n"
    "• كتابة رقم الجلوس بشكل صحيح، أو\n"
    "• كتابة جزء من الاسم بشكل أوضح.\n"
    "جرّب مرة أخرى أو أرسل /help للمساعدة."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /start — رسالة ترحيب."""
    await update.message.reply_html(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /help — شرح الاستخدام."""
    await update.message.reply_html(HELP_TEXT)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة أي نص يرسله المستخدم: بحث تلقائي برقم الجلوس أو بالاسم."""
    query = (update.message.text or "").strip()
    if not query:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        pairs, kind = search_auto(query)
    except Exception:
        logger.exception("خطأ أثناء البحث عن: %s", query)
        await update.message.reply_html(
            "⚠️ حدث خطأ أثناء البحث، حاول مرة أخرى بعد قليل."
        )
        return

    if not pairs:
        await update.message.reply_html(NO_RESULTS_TEXT)
        return

    shown = pairs[:MAX_NAME_RESULTS]

    if kind == "name":
        await update.message.reply_html(format_summary(len(pairs), len(shown)))

    # بحث برقم الجلوس بنتيجة واحدة → جلب درجات المواد التفصيلية
    if kind == "seating" and len(shown) == 1:
        row, ds = shown[0]
        system = DATASETS[ds]["system"]
        if system:
            detailed = await asyncio.to_thread(fetch_subjects, row["seating_no"], system)
            if detailed:
                await update.message.reply_html(format_subjects_result(detailed))
                return
        # فشل الجلب → نكمل بالنتيجة المحلية

    # عرض النتائج المحلية + زرار الدرجات تحت كل نتيجة
    for row, ds in shown:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "📚 عرض درجات المواد",
                callback_data=f"grades:{ds}:{row['seating_no']}",
            )
        ]])
        await update.message.reply_html(
            format_result(row, ds), reply_markup=keyboard
        )


async def handle_grades_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة ضغط زرار «عرض درجات المواد» — يجلب الدرجات جوه الشات."""
    query = update.callback_query
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.answer("⚠️ طلب غير صالح")
        return
    _, ds, seating_no = parts

    system = DATASETS.get(ds, {}).get("system")
    if not system:
        await query.answer("⚠️ طلب غير صالح")
        return

    await query.answer("⏳ جارٍ جلب الدرجات...")
    detailed = await asyncio.to_thread(fetch_subjects, seating_no, system)
    if detailed:
        await query.message.reply_html(format_subjects_result(detailed))
    else:
        await query.message.reply_html(
            "⚠️ تعذّر جلب درجات المواد حاليًا — حاول مرة أخرى بعد قليل."
        )


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit(
            "❌ متغير البيئة BOT_TOKEN غير مضبوط.\n"
            "احصل على توكن من @BotFather ثم نفّذ:\n"
            '   export BOT_TOKEN="123456:ABC..."\n'
            "   python bot.py"
        )

    logger.info("جارٍ تحميل بيانات النتائج (قد يستغرق دقيقة)...")
    load_all()
    logger.info("تم تحميل النتائج بنجاح.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_grades_callback, pattern=r"^grades:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت يعمل الآن (long polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
