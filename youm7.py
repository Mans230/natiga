# -*- coding: utf-8 -*-
"""
جلب درجات المواد التفصيلية برقم الجلوس من منصات النتيجة المفتوحة
(الجمهورية أونلاين + اليوم السابع — نفس المنصة ونفس البنية).

المنصة تحظر الطلبات البرمجية العادية عبر فحص بصمة TLS، لذلك نستخدم
curl_cffi بمحاكاة بصمة كروم الحقيقية — تعمل بثبات من السيرفرات.
عند فشل كل المصادر تُرجع None والبوت يكمل بالنتيجة المحلية.
"""

import html as html_lib
import logging
import re
import time

# curl_cffi يحاكي بصمة متصفح كروم الحقيقية (TLS) — ضروري لأن المنصة
# تحظر الطلبات البرمجية العادية (requests) بعد أول استخدام.
from curl_cffi import requests

logger = logging.getLogger(__name__)

# مصادر النتيجة — يتم تجربتها بالترتيب وأول نجاح يُستخدم.
SOURCES = [
    "https://natega.gomhuriaonline.com",
    "https://natega.youm7.com",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TIMEOUT = 15


def _clean(s: str) -> str:
    """إزالة وسوم HTML وفك ترميز الكيانات وتقليص المسافات."""
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_result_page(page_html: str) -> dict | None:
    """تحليل صفحة النتيجة — يرجع dict بالبيانات أو None إن لم توجد نتيجة."""
    if "student-result" not in page_html:
        return None

    result: dict = {"name": "", "status": "", "division": "", "seat": "",
                    "subjects": [], "total_percent": "", "total_degree": ""}

    m = re.search(r'student-result__name">(.*?)</h2>', page_html, re.S)
    if m:
        result["name"] = _clean(m.group(1)).replace("الأسم:", "").strip()

    m = re.search(r'student-result__school">(.*?)</p>', page_html, re.S)
    if m:
        result["status"] = _clean(m.group(1)).replace("حالة الطالب:", "").strip()

    for p in re.findall(r'student-result__seat">(.*?)</p>', page_html, re.S):
        c = _clean(p)
        if "الشعبة" in c:
            result["division"] = c.replace("الشعبة:", "").strip()
        elif "رقم الجلوس" in c:
            result["seat"] = re.sub(r"\D", "", c)

    tbody = re.search(r'student-result__table">.*?<tbody>(.*?)</tbody>', page_html, re.S)
    if tbody:
        for row in re.findall(r"<tr>(.*?)</tr>", tbody.group(1), re.S):
            cells = re.findall(r"<td>(.*?)</td>", row, re.S)
            if len(cells) == 3:
                result["subjects"].append({
                    "subject": _clean(cells[0]),
                    "degree": _clean(cells[1]),
                    "percent": _clean(cells[2]),
                })

    for label, key in [("النسبة المئوية الكلية", "total_percent"),
                       ("مجموع الدرجات", "total_degree")]:
        m = re.search(re.escape(label) + r"</span>\s*<span[^>]*>(.*?)</span>", page_html, re.S)
        if m:
            result[key] = _clean(m.group(1))

    return result if result["subjects"] else None


def _fetch_from_source(base_url: str, seating_no, system: str) -> dict | None:
    """محاولة جلب واحدة من مصدر معين (ببصمة متصفح حقيقية)."""
    try:
        session = requests.Session(impersonate="chrome")
        session.headers.update({"User-Agent": USER_AGENT})
        # زيارة الصفحة الرئيسية أولًا (تهيئة الجلسة والكوكيز)
        session.get(base_url + "/", timeout=TIMEOUT)
        time.sleep(0.5)
        resp = session.post(
            f"{base_url}/Result/1",
            data={"seating_no": str(seating_no), "system": system},
            headers={"Referer": base_url + "/", "Origin": base_url},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return parse_result_page(resp.text)
        logger.warning("natega: %s رد بـ %s", base_url, resp.status_code)
    except Exception:
        logger.exception("natega: خطأ أثناء الجلب من %s", base_url)
    return None


def fetch_subjects(seating_no, system: str = "1") -> dict | None:
    """
    جلب درجات المواد برقم الجلوس — يجرب المصادر بالترتيب:
    الجمهورية ← اليوم السابع، وأول نجاح يُرجع.
    يرجع None فقط إذا فشلت كل المصادر (والبوت يكمل بالنتيجة المحلية).
    """
    for source in SOURCES:
        result = _fetch_from_source(source, seating_no, system)
        if result:
            logger.info("natega: نجح الجلب من %s", source)
            return result
        time.sleep(1)
    logger.warning("natega: فشلت كل المصادر لرقم %s", seating_no)
    return None


_STATUS_EMOJI = {
    "ناجح": "✅",
    "دور ثان": "🔄",
    "راسب": "❌",
    "غياب": "⚠️",
}


def format_subjects_result(data: dict) -> str:
    """تنسيق نتيجة المواد برسالة HTML أنيقة لتليجرام."""
    status = data.get("status", "")
    emoji = next((e for k, e in _STATUS_EMOJI.items() if k in status), "ℹ️")

    lines = [
        "🎓 <b>النتيجة التفصيلية</b>",
        "━━━━━━━━━━━━━━",
        f"👤 <b>الاسم:</b> {data.get('name', '')}",
        f"🪪 <b>رقم الجلوس:</b> {data.get('seat', '')}",
    ]
    if data.get("division"):
        lines.append(f"🏫 <b>الشعبة:</b> {data['division']}")
    lines.append(f"{emoji} <b>الحالة:</b> {status}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📚 <b>درجات المواد:</b>")

    for sub in data["subjects"]:
        if "غير مقرر" in sub["degree"]:
            lines.append(f"▫️ {sub['subject']}: <i>غير مقرر</i>")
        else:
            pct = f" ({sub['percent']})" if sub["percent"] and sub["percent"] != "—" else ""
            lines.append(f"▪️ {sub['subject']}: <b>{sub['degree']}</b>{pct}")

    lines.append("━━━━━━━━━━━━━━")
    if data.get("total_degree"):
        lines.append(f"📊 <b>المجموع:</b> {data['total_degree']}")
    if data.get("total_percent"):
        lines.append(f"📈 <b>النسبة الكلية:</b> {data['total_percent']}")
    return "\n".join(lines)
