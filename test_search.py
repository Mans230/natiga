# -*- coding: utf-8 -*-
"""
اختبار حقيقي لمنطق البحث على الملف الفعلي results.xlsx — بدون توكن تليجرام.

التشغيل:
    python test_search.py
"""

import sys

from search import (
    find_by_name,
    find_by_seating_no,
    format_result,
    format_summary,
    load_data,
    normalize_arabic,
    search,
)

PASS, FAIL = "✅ PASS", "❌ FAIL"
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{PASS if ok else FAIL} — {name}" + (f" | {detail}" if detail else ""))
    if not ok:
        failures += 1


print("جارٍ تحميل البيانات...")
df = load_data()
print(f"تم تحميل {len(df):,} صف.\n")

# --- 1) بحث برقم جلوس موجود (2001970) -----------------------------------
res, kind = search("2001970")
check(
    "بحث برقم جلوس موجود (2001970)",
    kind == "seating" and len(res) == 1 and res.iloc[0]["seating_no"] == 2001970,
    f"النتائج: {len(res)} | النوع: {kind}",
)
print("--- نموذج الرسالة المنسقة ---")
print(format_result(res.iloc[0]))
print("-----------------------------\n")

# --- 2) بحث باسم موجود ---------------------------------------------------
real_name = str(res.iloc[0]["arabic_name"]).strip()
res2, kind2 = search(real_name)
check(
    f"بحث باسم موجود («{real_name}»)",
    kind2 == "name" and len(res2) >= 1 and (res2["seating_no"] == 2001970).any(),
    f"النتائج: {len(res2)} | النوع: {kind2}",
)

# بحث جزئي: أول كلمتين من الاسم
partial = " ".join(real_name.split()[:2])
res3, _ = search(partial)
check(
    f"بحث جزئي بالاسم («{partial}»)",
    len(res3) >= 1 and (res3["seating_no"] == 2001970).any(),
    f"النتائج: {len(res3)}",
)

# --- 3) بحث باسم متكرر (يرجع أكثر من نتيجة) ------------------------------
# نبحث عن اسم شائع (اسم أول + اسم أب شائعين)
common = "محمد احمد"
res4, _ = search(common)
check(
    f"بحث باسم متكرر («{common}»)",
    len(res4) > 1,
    f"النتائج: {len(res4)}",
)
if len(res4) > 1:
    shown = res4.head(20)
    print(format_summary(len(res4), len(shown)))
    for _, row in shown.head(3).iterrows():
        print(format_result(row))
    if len(shown) > 3:
        print(f"... و{len(shown) - 3} نتيجة أخرى معروضة ضمن الحد الأقصى 20\n")

# --- 4) بحث برقم جلوس غير موجود ------------------------------------------
res5, kind5 = search("999999999")
check(
    "بحث برقم جلوس غير موجود (999999999)",
    res5.empty,
    f"النتائج: {len(res5)}",
)

# --- 5) بحث باسم غير موجود -----------------------------------------------
res6, _ = search("ززززقققق غيرموجودابدا")
check(
    "بحث باسم غير موجود",
    res6.empty,
    f"النتائج: {len(res6)}",
)

# --- 6) تطبيع الأرقام العربية (٢٠٠١٩٧٠ → 2001970) ------------------------
res7, kind7 = search("٢٠٠١٩٧٠")
check(
    "تطبيع الأرقام العربية («٢٠٠١٩٧٠» → يجد 2001970)",
    kind7 == "seating" and len(res7) == 1 and res7.iloc[0]["seating_no"] == 2001970,
    f"النتائج: {len(res7)} | النوع: {kind7}",
)

# --- 7) اختبارات وحدة للتطبيع ---------------------------------------------
check(
    "تطبيع الهمزات والتاء والياء",
    normalize_arabic("أحمد إبراهيم آمنة فاطمة علي") == "احمد ابراهيم امنه فاطمه علي",
    repr(normalize_arabic("أحمد إبراهيم آمنة فاطمة علي")),
)
check(
    "إزالة التشكيل",
    normalize_arabic("مُحَمَّدٌ") == "محمد",
    repr(normalize_arabic("مُحَمَّدٌ")),
)
check(
    "تقليص المسافات",
    normalize_arabic("  احمد    محمود  ") == "احمد محمود",
    repr(normalize_arabic("  احمد    محمود  ")),
)

# بحث بالاسم مع اختلافات إملائية (ة↔ه، ى↔ي، همزات) يجب أن يجد الطالب نفسه
twisted = real_name.replace("ال", "أل").replace("ة", "ه").replace("ى", "ي")
res8, _ = search(twisted)
check(
    f"بحث متسامح مع الهمزات/ة/ى («{twisted}»)",
    (res8["seating_no"] == 2001970).any(),
    f"النتائج: {len(res8)}",
)

print()
if failures:
    print(f"❌ فشل {failures} اختبارًا.")
    sys.exit(1)
print("🎉 كل الاختبارات نجحت.")
