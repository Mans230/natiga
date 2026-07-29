# -*- coding: utf-8 -*-
"""
منطق تحميل البيانات والبحث في نتائج الثانوية العامة بكل الأنظمة:
- نظام حديث 2026 (من 320)
- نظام قديم 2026 (من 410)
- ثانوية عامة 2025 (من 410)

هذا الملف مستقل تمامًا عن تليجرام ويمكن استيراده واختباره بسهولة:

    from search import load_all, search
    load_all()
    results, kind = search("2001970", "hadith")
"""

import os
import re
import unicodedata

import pandas as pd

# ---------------------------------------------------------------------------
# سجل النتائج المتاحة
# ---------------------------------------------------------------------------

_BASE = os.path.dirname(os.path.abspath(__file__))

DATASETS = {
    "hadith": {
        "title": "نظام حديث 2026",
        "file": os.path.join(_BASE, "results.pkl.gz"),
        "max_degree": 320.0,
        "system": "1",  # معرّف النظام في مواقع الدرجات التفصيلية
    },
    "qadeem": {
        "title": "نظام قديم 2026",
        "file": os.path.join(_BASE, "results_old2026.pkl.gz"),
        "max_degree": 410.0,
        "system": "2",
    },
    # ملاحظة: نتيجة 2025 معطّلة حاليًا بطلب المستخدم (بحث تلقائي في 2026 فقط).
    # لإعادة تفعيلها: أزل التعليق عن القاموس التالي وارفع ملف results_2025.pkl.gz.
    # "y2025": {
    #     "title": "ثانوية عامة 2025",
    #     "file": os.path.join(_BASE, "results_2025.pkl.gz"),
    #     "max_degree": 410.0,
    #     "system": None,  # لا تتوفر درجات مواد خارجية لهذه السنة
    # },
}

DEFAULT_DATASET = "hadith"

# النتائج المشمولة في البحث التلقائي (2025 اختيار يدوي فقط)
AUTO_DATASETS = ["hadith", "qadeem"]

# أقصى عدد نتائج يُعرض للبحث بالاسم
MAX_NAME_RESULTS = 20

# DataFrames مُحمّلة في الذاكرة (مفتاحها مفتاح النتيجة)
_frames: dict[str, pd.DataFrame] = {}

# ---------------------------------------------------------------------------
# التطبيع (Normalization)
# ---------------------------------------------------------------------------

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIACRITICS_RE = re.compile(r"[ً-ْٰـ]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """
    تطبيع نص عربي للبحث:
    - أ إ آ → ا ، ة → ه ، ى → ي
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


def dataset_title(key: str) -> str:
    return DATASETS.get(key, DATASETS[DEFAULT_DATASET])["title"]


def load_dataset(key: str = DEFAULT_DATASET) -> pd.DataFrame:
    """تحميل نتيجة معينة مرة واحدة في الذاكرة."""
    if key not in DATASETS:
        key = DEFAULT_DATASET
    if key not in _frames:
        path = DATASETS[key]["file"]
        if path.endswith((".pkl", ".pkl.gz", ".pickle")):
            df = pd.read_pickle(path)
        else:
            df = pd.read_excel(path)
        df["seating_no"] = pd.to_numeric(df["seating_no"], errors="coerce").astype("Int64")
        df["arabic_name"] = df["arabic_name"].astype(str).str.strip()
        # عمود البحث المُطبَّع: يُحسب فقط إن لم يكن جاهزًا في الملف
        if "name_norm" not in df.columns:
            df["name_norm"] = df["arabic_name"].map(normalize_arabic)
        _frames[key] = df
    return _frames[key]


def load_all() -> None:
    """تحميل كل النتائج عند بدء التشغيل."""
    for key in DATASETS:
        load_dataset(key)


# ---------------------------------------------------------------------------
# البحث
# ---------------------------------------------------------------------------


def is_seating_query(text: str) -> bool:
    """هل النص رقم جلوس؟ (أرقام فقط بعد تطبيع الأرقام العربية)"""
    t = normalize_arabic(text).replace(" ", "")
    return bool(t) and t.isdigit()


def find_by_seating_no(seating_no: int, dataset: str = DEFAULT_DATASET) -> pd.DataFrame:
    """بحث تام برقم الجلوس — يرجع DataFrame (صف واحد عادة)."""
    df = load_dataset(dataset)
    return df[df["seating_no"] == seating_no]


def find_by_name(name: str, dataset: str = DEFAULT_DATASET) -> pd.DataFrame:
    """بحث جزئي بالاسم بعد تطبيع الطرفين."""
    df = load_dataset(dataset)
    q = normalize_arabic(name)
    if not q:
        return df.iloc[0:0]
    return df[df["name_norm"].str.contains(re.escape(q), na=False)]


def search(query: str, dataset: str = DEFAULT_DATASET):
    """
    نقطة دخول موحّدة للبحث داخل نتيجة معينة.
    - أرقام فقط → تطابق تام برقم الجلوس.
    - غير ذلك → تطابق جزئي بالاسم.

    يرجع: (results: DataFrame, kind: "seating" | "name")
    """
    query = (query or "").strip()
    if is_seating_query(query):
        return find_by_seating_no(int(normalize_arabic(query).replace(" ", "")), dataset), "seating"
    return find_by_name(query, dataset), "name"


def search_auto(query: str):
    """
    بحث تلقائي في نتائج 2026 (حديث + قديم) معًا — برقم الجلوس أو بالاسم.
    يرجع: (rows: قائمة من (صف، مفتاح_النتيجة), kind: "seating" | "name")
    كل صف موسوم بالنتيجة اللي اتلاقى فيها.
    """
    query = (query or "").strip()
    rows: list = []
    if is_seating_query(query):
        seat = int(normalize_arabic(query).replace(" ", ""))
        for ds in AUTO_DATASETS:
            for _, r in find_by_seating_no(seat, ds).iterrows():
                rows.append((r, ds))
        return rows, "seating"
    for ds in AUTO_DATASETS:
        for _, r in find_by_name(query, ds).iterrows():
            rows.append((r, ds))
    return rows, "name"


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


def format_percentage(degree, dataset: str = DEFAULT_DATASET) -> str:
    """النسبة المئوية حسب أقصى مجموع للنتيجة المختارة."""
    max_degree = DATASETS.get(dataset, DATASETS[DEFAULT_DATASET])["max_degree"]
    try:
        pct = float(degree) / max_degree * 100
    except (TypeError, ValueError):
        return "—"
    s = f"{pct:.2f}".rstrip("0").rstrip(".")
    return f"{s}%"


def format_result(row, dataset: str = DEFAULT_DATASET) -> str:
    """تنسيق نتيجة طالب واحد برسالة عربية أنيقة (HTML)."""
    cfg = DATASETS.get(dataset, DATASETS[DEFAULT_DATASET])
    max_d = format_degree(cfg["max_degree"])
    name = str(row["arabic_name"]).strip()
    seating = row["seating_no"]
    degree = row["total_degree"]

    lines = [
        f"🎓 <b>نتيجة الطالب — {cfg['title']}</b>",
        "━━━━━━━━━━━━━━",
        f"👤 <b>الاسم:</b> {name}",
        f"🪪 <b>رقم الجلوس:</b> {seating}",
        f"📊 <b>المجموع:</b> {format_degree(degree)} من {max_d}",
        f"📈 <b>النسبة المئوية:</b> {format_percentage(degree, dataset)}",
    ]
    # الحالة تُعرض فقط إن وُجدت في بيانات النتيجة
    if "student_case_desc" in row.index and pd.notna(row["student_case_desc"]):
        status = str(row["student_case_desc"]).strip()
        emoji = next((e for k, e in _STATUS_EMOJI.items() if k in status), "ℹ️")
        lines.append(f"{emoji} <b>الحالة:</b> {status}")
    return "\n".join(lines)


def format_summary(total: int, shown: int) -> str:
    """رسالة ملخّص عدد نتائج البحث بالاسم."""
    if total > shown:
        return f"🔎 تم إيجاد <b>{total}</b> نتيجة — أول {shown} معروضة:"
    return f"🔎 تم إيجاد <b>{total}</b> نتيجة:"
