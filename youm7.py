# -*- coding: utf-8 -*-
"""
جلب درجات المواد التفصيلية من موقع نتيجة اليوم السابع (natega.youm7.com).

الموقع يقبل POST مباشر بدون حماية Cloudflare، لكنه قد يحظر مؤقتًا (404)
عند كثرة الطلبات من نفس العنوان — لذلك كل فشل يُعالَج بهدوء ويرجع None
(والبوت يكمل بالنتيجة المحلية + زرار الموقع البديل).
"""

import html as html_lib
import logging
import re

import requests

logger = logging.getLogger(__name__)

SITE_URL = "https://natega.youm7.com/"
RESULT_URL = "https://natega.youm7.com/Result/1"
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


def fetch_subjects(seating_no, system: str = "1") -> dict | None:
    """
    جلب درجات المواد برقم الجلوس من موقع اليوم السابع.
    system: "1" = نظام حديث، "2" = نظام قديم.
    يرجع dict بالنتيجة، أو None عند أي فشل (حظر مؤقت/موقع خارج الخدمة/لا نتيجة).
    """
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        resp = session.post(
            RESULT_URL,
            data={"seating_no": str(seating_no), "system": system},
            headers={"Referer": SITE_URL},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("youm7: status %s لرقم %s", resp.status_code, seating_no)
            return None
        return parse_result_page(resp.text)
    except Exception:
        logger.exception("youm7: فشل الجلب لرقم %s", seating_no)
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
