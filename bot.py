# -*- coding: utf-8 -*-
"""
بوت تليجرام لنتيجة الثانوية العامة (نظام حديث).

التشغيل:
    export BOT_TOKEN="التوكن_من_BotFather"
    python bot.py

يعتمد على python-telegram-bot v21+ (واجهة async) و long polling.
"""

import logging
import os

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from search import (
    MAX_NAME_RESULTS,
    format_result,
    format_summary,
    load_data,
    search,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 أهلًا بك في <b>بوت نتيجة الثانوية العامة (نظام حديث)</b>\n\n"
    "🔍 <b>طريقة الاستخدام:</b>\n"
    "• أرسل <b>رقم الجلوس</b> (مثال: 2001970) للبحث المباشر.\n"
    "• أو أرسل <b>اسم الطالب</b> (كاملًا أو جزءًا منه) للبحث بالاسم.\n\n"
    "💡 يمكنك كتابة الأرقام بالعربية (٢٠٠١٩٧٠) أو الإنجليزية.\n"
    "❓ للمساعدة في أي وقت أرسل /help"
)

HELP_TEXT = (
    "❓ <b>مساعدة</b>\n\n"
    "هذا البوت يتيح لك معرفة نتيجة الثانوية العامة (نظام حديث):\n\n"
    "1️⃣ <b>البحث برقم الجلوس:</b>\n"
    "اكتب رقم الجلوس فقط — مثال: <code>2001970</code>\n\n"
    "2️⃣ <b>البحث بالاسم:</b>\n"
    "اكتب الاسم أو جزءًا منه — مثال: <code>احمد محمود السيد</code>\n"
    "وستظهر لك كل الأسماء المطابقة (حتى 20 نتيجة).\n\n"
    "📌 لا يهم اختلاف الهمزات (أ/إ/آ) أو التاء المربوطة/المروية (ة/ه) "
    "أو الألف المقصورة (ى/ي) — البحث يتعامل معها تلقائيًا."
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
    """معالجة أي نص يرسله المستخدم: بحث برقم الجلوس أو بالاسم."""
    query = (update.message.text or "").strip()
    if not query:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        results, kind = search(query)
    except Exception:
        logger.exception("خطأ أثناء البحث عن: %s", query)
        await update.message.reply_html(
            "⚠️ حدث خطأ أثناء البحث، حاول مرة أخرى بعد قليل."
        )
        return

    if results.empty:
        await update.message.reply_html(NO_RESULTS_TEXT)
        return

    shown = results.head(MAX_NAME_RESULTS)

    if kind == "name":
        await update.message.reply_html(format_summary(len(results), len(shown)))

    for _, row in shown.iterrows():
        await update.message.reply_html(
            format_result(row), parse_mode=ParseMode.HTML
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
    df = load_data()
    logger.info("تم تحميل %d صفًا بنجاح.", len(df))

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت يعمل الآن (long polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
