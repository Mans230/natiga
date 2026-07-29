# -*- coding: utf-8 -*-
"""
منطق تحميل البيانات والبحث في نتيجة الثانوية العامة (نظام حديث).

هذا الملف مستقل تمامًا عن تليجرام ويمكن استيراده واختباره بسهولة:

    from search import load_data, search

    load_data()                      # تحميل مرّة واحدة
    results, kind = search("2001970")  # بحث برقم جلوس
    results, kind = search("احمد محمود")  # بحث بالاسم
"""

import os
import re
import unicodedata

import pandas as pd

# مسار ملف النتائج بجانب هذا الملف (pickle مضغوط — أصغر وأسرع من Excel)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.pkl.gz")

# أقصى مجموع كلي في النظام الحديث
MAX_DEGREE = 320.0

# أقصى عدد نتائج يُعرض للبحث بالاسم
MAX_NAME_RESULTS = 20

# DataFrame يُحمّل مرة واحدة في الذاكرة
_df: pd.DataFrame | None = None

# ---------------------------------------------------------------------------
# التطبيع (Normalization)
# ---------------------------------------------------------------------------

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIACRITICS_RE = re.compile(r"[ً-ْٰـ]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """
    تطبيع نص عربي للبحث:
    - أ إ آ → ا
    - ة → ه
    - ى → ي
    - إزالة التشكيل والتطويل
    - تحويل الأرقام العربية/الفارسية إلى أرقام إنجليزية
    - تقليص المسافات المتكررة وإزالة المسافات الطرفية
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.translate(_ARABIC_DIGITS)
    text = _DIACRITICS_RE.sub("", text)
    text = (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


# ---------------------------------------------------------------------------
# تحميل البيانات
# ---------------------------------------------------------------------------


def load_data(path: str | None = None) -> pd.DataFrame:
    """
    تحميل ملف البيانات مرة واحدة في الذاكرة وتجهيز عمود الاسم المُطبَّع
    (name_norm) لتسريع البحث الجزئي بالاسم.
    يدعم ملف pickle مضغوط (.pkl.gz) وملف Excel (.xlsx) كاحتياطي.
    """
    global _df
    if _df is None:
        path = path or DATA_FILE
        if path.endswith((".pkl", ".pkl.gz", ".pickle")):
            df = pd.read_pickle(path)
        else:
            df = pd.read_excel(path)
        df["seating_no"] = pd.to_numeric(df["seating_no"], errors="coerce").astype("Int64")
        df["arabic_name"] = df["arabic_name"].astype(str).str.strip()
        # عمود البحث المُطبَّع: يُحسب فقط إن لم يكن جاهزًا في الملف
        if "name_norm" not in df.columns:
            df["name_norm"] = df["arabic_name"].map(normalize_arabic)
        _df = df
    return _df


def is_loaded() -> bool:
    return _df is not None


# ---------------------------------------------------------------------------
# البحث
# ---------------------------------------------------------------------------


def is_seating_query(text: str) -> bool:
    """هل النص رقم جلوس؟ (أرقام فقط بعد تطبيع الأرقام العربية)"""
    t = normalize_arabic(text).replace(" ", "")
    return bool(t) and t.isdigit()


def find_by_seating_no(seating_no: int) -> pd.DataFrame:
    """بحث تام برقم الجلوس — يرجع DataFrame (صف واحد عادة)."""
    df = load_data()
    return df[df["seating_no"] == seating_no]


def find_by_name(name: str) -> pd.DataFrame:
    """
    بحث جزئي بالاسم بعد تطبيع الطرفين.
    يرجع DataFrame بكل المطابقات (بلا حد أقصى — التقليص يتم عند العرض).
    """
    df = load_data()
    q = normalize_arabic(name)
    if not q:
        return df.iloc[0:0]
    return df[df["name_norm"].str.contains(re.escape(q), na=False)]


def search(query: str):
    """
    نقطة دخول موحّدة للبحث.
    - أرقام فقط → تطابق تام برقم الجلوس.
    - غير ذلك → تطابق جزئي بالاسم.

    يرجع: (results: DataFrame, kind: "seating" | "name")
    """
    query = (query or "").strip()
    if is_seating_query(query):
        return find_by_seating_no(int(normalize_arabic(query).replace(" ", ""))), "seating"
    return find_by_name(query), "name"


# ---------------------------------------------------------------------------
# تنسيق النتيجة
# ---------------------------------------------------------------------------

_STATUS_EMOJI = {
    "ناجح دور أول": "✅",
    "دور ثان": "🔄",
    "راسب دور أول": "❌",
    "غياب كلى دور أول": "⚠️",
}


def format_degree(degree) -> str:
    """تنسيق المجموع بدون أصفار زائدة (290.0 → 290 ، 179.5 → 179.5)."""
    try:
        d = float(degree)
    except (TypeError, ValueError):
        return str(degree)
    return str(int(d)) if d == int(d) else f"{d:g}"


def format_percentage(degree) -> str:
    """النسبة المئوية من 320 — رقمان عشريان كحد أقصى."""
    try:
        pct = float(degree) / MAX_DEGREE * 100
    except (TypeError, ValueError):
        return "—"
    s = f"{pct:.2f}".rstrip("0").rstrip(".")
    return f"{s}%"


def format_result(row) -> str:
    """تنسيق نتيجة طالب واحد برسالة عربية أنيقة (HTML)."""
    name = str(row["arabic_name"]).strip()
    seating = row["seating_no"]
    degree = row["total_degree"]
    status = str(row["student_case_desc"]).strip()
    emoji = next((e for k, e in _STATUS_EMOJI.items() if k in status), "ℹ️")

    return (
        "🎓 <b>نتيجة الطالب</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 <b>الاسم:</b> {name}\n"
        f"🪪 <b>رقم الجلوس:</b> {seating}\n"
        f"📊 <b>المجموع:</b> {format_degree(degree)} من 320\n"
        f"📈 <b>النسبة المئوية:</b> {format_percentage(degree)}\n"
        f"{emoji} <b>الحالة:</b> {status}"
    )


def format_summary(total: int, shown: int) -> str:
    """رسالة ملخّص عدد نتائج البحث بالاسم."""
    if total > shown:
        return f"🔎 تم إيجاد <b>{total}</b> نتيجة — أول {shown} معروضة:"
    return f"🔎 تم إيجاد <b>{total}</b> نتيجة:"
