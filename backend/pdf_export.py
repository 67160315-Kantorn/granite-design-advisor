"""
pdf_export.py — สร้างไฟล์ PDF สรุป "โปรเจกต์ของฉัน" ฝั่ง backend (รองรับภาษาไทย)

ทำไมทำฝั่ง backend แทน jsPDF ในเบราว์เซอร์: jsPDF ไม่มีฟอนต์ไทยในตัว ภาษาไทยจึงออกมาเป็น
ตัวอักษรเพี้ยน/ว่างในไฟล์ PDF — ที่นี่ใช้ fpdf2 + ฟอนต์ไทย (TLWG ที่ติดตั้งใน Docker image) และ
เปิด text shaping (uharfbuzz) เพื่อให้สระ/วรรณยุกต์ภาษาไทยวางตำแหน่งถูกต้อง

หาฟอนต์ตามลำดับ: ตัวแปร PDF_FONT_PATH / PDF_FONT_BOLD_PATH ใน .env -> ฟอนต์ TLWG บน Linux
-> ฟอนต์ไทยของ Windows (รันในเครื่องตัวเองโดยไม่ใช้ Docker) ถ้าไม่เจอเลยจะ fallback เป็น
Helvetica (ภาษาไทยจะแสดงเป็น "?") พร้อมเตือนใน log
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)

_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/tlwg/Garuda.ttf", "/usr/share/fonts/truetype/tlwg/Garuda-Bold.ttf"),
    ("/usr/share/fonts/truetype/tlwg/Loma.ttf", "/usr/share/fonts/truetype/tlwg/Loma-Bold.ttf"),
    ("/usr/share/fonts/truetype/tlwg/Waree.ttf", "/usr/share/fonts/truetype/tlwg/Waree-Bold.ttf"),
    ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
    ("C:/Windows/Fonts/LeelawUI.ttf", "C:/Windows/Fonts/LeelaUIb.ttf"),
]

KIND_LABEL = {"granite": "หิน", "price": "ราคา", "advisor": "AI แนะนำ", "inspiration": "Inspiration"}
AREA_LABEL = {
    "kitchen": "ห้องครัว", "bathroom": "ห้องน้ำ", "livingroom": "Living Room", "counter": "Counter",
    "table": "โต๊ะ", "wall": "ผนัง", "floor": "พื้น", "outdoor": "Outdoor",
}
COLOR_LABEL = {
    "black": "ดำ", "white": "ขาว", "brown": "น้ำตาล", "green": "เขียว",
    "blue": "น้ำเงิน", "red": "แดง", "grey": "เทา",
}
THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

GOLD = (176, 132, 48)
DARK = (30, 27, 22)
GRAY = (110, 110, 110)


def _find_font() -> Optional[tuple]:
    env_regular = os.environ.get("PDF_FONT_PATH")
    if env_regular and os.path.exists(env_regular):
        bold = os.environ.get("PDF_FONT_BOLD_PATH")
        return env_regular, bold if bold and os.path.exists(bold) else None
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            return regular, bold if os.path.exists(bold) else None
    return None


def _thai_date(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return f"{dt.day} {THAI_MONTHS[dt.month - 1]} {dt.year + 543}"


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _baht(v: Any) -> str:
    n = _num(v)
    return "-" if n is None else f"฿{n:,.0f}"


class _ProjectPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)
        self.has_thai = False
        self.has_bold = False
        found = _find_font()
        if found:
            regular, bold = found
            try:
                self.add_font("Thai", "", regular)
                if bold:
                    self.add_font("Thai", "B", bold)
                    self.has_bold = True
                self.has_thai = True
            except Exception as e:  # noqa: BLE001
                logger.warning("โหลดฟอนต์ไทยสำหรับ PDF ไม่สำเร็จ (%s): %s", regular, e)
        if self.has_thai:
            try:
                self.set_text_shaping(True)  # ต้องมี uharfbuzz — ทำให้สระ/วรรณยุกต์ไทยไม่ทับกัน
            except Exception as e:  # noqa: BLE001
                logger.warning("เปิด text shaping ไม่ได้ (ติดตั้ง uharfbuzz หรือยัง?): %s", e)
        else:
            logger.warning("ไม่พบฟอนต์ไทยสำหรับสร้าง PDF — ภาษาไทยจะแสดงเป็น ? (ตั้ง PDF_FONT_PATH ใน .env)")

    # ---- helpers ----
    def t(self, text: Any) -> str:
        s = "" if text is None else str(text)
        if self.has_thai:
            return s
        return s.encode("latin-1", "replace").decode("latin-1")

    def font(self, bold: bool = False, size: int = 11) -> None:
        if self.has_thai:
            self.set_font("Thai", "B" if (bold and self.has_bold) else "", size)
        else:
            self.set_font("helvetica", "B" if bold else "", size)

    def footer(self):
        self.set_y(-13)
        self.font(size=9)
        self.set_text_color(*GRAY)
        self.cell(0, 6, self.t("Granite Design Advisor"), align="L")
        self.set_x(self.l_margin)
        self.cell(0, 6, self.t(f"หน้า {self.page_no()}/{{nb}}"), align="R")


def _item_lines(item: Dict[str, Any], product: Optional[Dict[str, Any]]) -> List[tuple]:
    """คืนรายการบรรทัดรายละเอียด [(ป้าย, ค่า, ตัวหนาไหม)] ตามประเภทของรายการ"""
    kind = item.get("kind")
    d = item.get("detail") or {}
    if not isinstance(d, dict):
        return []
    lines: List[tuple] = []

    if kind == "granite":
        price = product["price"] if product else d.get("price")
        lines.append(("ราคา", f"{_baht(price)} / ตร.ม.", False))
        if product:
            meta = " · ".join(x for x in [
                COLOR_LABEL.get(product.get("color"), product.get("color")),
                "หินอ่อน" if product.get("material") == "marble" else "หินแกรนิต",
            ] if x)
            if meta:
                lines.append(("ลักษณะ", meta, False))

    elif kind == "advisor":
        if d.get("area"):
            lines.append(("พื้นที่", AREA_LABEL.get(d["area"], d["area"]), False))
        if d.get("style"):
            lines.append(("สไตล์", d["style"], False))
        if d.get("color"):
            lines.append(("สี", COLOR_LABEL.get(d["color"], d["color"]), False))
        if d.get("score") is not None:
            lines.append(("คะแนนความเหมาะสม", f"{d['score']}", False))

    elif kind == "price":
        w, l, a = _num(d.get("width")), _num(d.get("length")), _num(d.get("area"))
        if w is not None and l is not None and a is not None:
            lines.append(("ขนาดพื้นที่", f"{w:g} × {l:g} ม. = {a:.2f} ตร.ม.", False))
        lines.append(("ราคา/ตร.ม.", _baht(d.get("basePricePerSqm")), False))
        lines.append(("ค่าวัสดุ (รวมผิวสัมผัส)", _baht(d.get("materialCost")), False))
        lines.append(("ค่าติดตั้ง", _baht(d.get("installCost")), False))
        lines.append(("รวมก่อน VAT", _baht(d.get("subtotal")), False))
        lines.append(("VAT 7%", _baht(d.get("vat")), False))
        lines.append(("ราคารวมโดยประมาณ", _baht(d.get("total")), True))
    return lines


def build_project_pdf(
    project_name: str,
    items: List[Dict[str, Any]],
    products_by_id: Dict[int, Dict[str, Any]],
    owner_name: str = "",
) -> bytes:
    """
    items: [{kind, title, detail, created_at}] เรียงตามเวลาที่เพิ่ม
    products_by_id: {id: {price, color, material}} ใช้ดึงราคา "ปัจจุบัน" ของหินที่บันทึกไว้
    """
    pdf = _ProjectPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # ---- หัวเอกสาร ----
    pdf.font(True, 9)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 5, pdf.t("GRANITE DESIGN ADVISOR  ·  สรุปโปรเจกต์"), new_x="LMARGIN", new_y="NEXT")
    pdf.font(True, 22)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 11, pdf.t(project_name), new_x="LMARGIN", new_y="NEXT")
    pdf.font(size=10)
    pdf.set_text_color(*GRAY)
    sub = f"สร้างเมื่อ {_thai_date(datetime.now())}  ·  {len(items)} รายการ"
    if owner_name:
        sub += f"  ·  เจ้าของ: {owner_name}"
    pdf.cell(0, 6, pdf.t(sub), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    if not items:
        pdf.font(size=12)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 8, pdf.t("ยังไม่มีรายการในโปรเจกต์นี้"), new_x="LMARGIN", new_y="NEXT")

    price_total = 0.0
    price_count = 0

    for item in items:
        detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
        stone_id = detail.get("stoneId") or (detail.get("stone") or {}).get("id") if detail else None
        try:
            product = products_by_id.get(int(stone_id)) if stone_id is not None else None
        except (TypeError, ValueError):
            product = None

        if item.get("kind") == "price" and _num(detail.get("total")) is not None:
            price_total += _num(detail.get("total"))
            price_count += 1

        with pdf.unbreakable() as block:
            block.font(size=9)
            block.set_text_color(*GOLD)
            label = KIND_LABEL.get(item.get("kind"), item.get("kind") or "")
            when = _thai_date(item.get("created_at"))
            block.cell(0, 5, block.t(f"[{label}]  {when}".strip()), new_x="LMARGIN", new_y="NEXT")
            block.font(True, 12)
            block.set_text_color(*DARK)
            block.multi_cell(0, 6.5, block.t(item.get("title", "")), new_x="LMARGIN", new_y="NEXT")
            for lab, val, bold in _item_lines(item, product):
                block.font(bold, 10)
                block.set_text_color(*(DARK if bold else GRAY))
                block.set_x(block.l_margin + 4)
                block.cell(62, 5.5, block.t(lab))
                block.cell(0, 5.5, block.t(val), new_x="LMARGIN", new_y="NEXT")
            block.ln(3)

        # เส้นคั่นระหว่างรายการ — วาดนอก unbreakable() เพราะ fpdf2 ไม่ให้เรียก get_y() ข้างใน
        pdf.set_draw_color(225, 220, 210)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

    if price_count:
        with pdf.unbreakable() as block:
            block.ln(2)
            block.font(True, 12)
            block.set_text_color(*DARK)
            block.cell(120, 8, block.t(f"ราคารวมโดยประมาณ ({price_count} รายการคำนวณราคา)"))
            block.set_text_color(*GOLD)
            block.cell(0, 8, block.t(_baht(price_total)), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.font(size=9)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5, pdf.t("หมายเหตุ: ราคาทั้งหมดเป็นการประมาณการเบื้องต้นเท่านั้น ราคาจริงขึ้นกับผู้จำหน่ายและหน้างาน"),
                   new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


FINISH_LABEL = {1.0: "ขัดเงา (Polished)", 1.1: "ผิวด้าน (Honed) +10%", 1.2: "ผิวหยาบ (Leathered) +20%"}


def build_price_pdf(
    stone_name: str,
    width_m: float,
    length_m: float,
    base_price_per_sqm: float,
    finish_multiplier: float,
    install_rate_per_sqm: float,
) -> bytes:
    """ใบประมาณราคา 1 หน้า — คำนวณตัวเลขซ้ำฝั่ง backend ให้ตรงกับสูตรในหน้าเว็บ
    (ค่าวัสดุ = ราคา/ตร.ม. × ตัวคูณผิว × พื้นที่, ค่าติดตั้ง = อัตรา × พื้นที่, VAT 7%)"""
    area = width_m * length_m
    material = base_price_per_sqm * finish_multiplier * area
    install = install_rate_per_sqm * area
    subtotal = material + install
    vat = subtotal * 0.07
    total = subtotal + vat

    pdf = _ProjectPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.font(True, 9)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 5, pdf.t("GRANITE DESIGN ADVISOR  ·  ใบประมาณราคา"), new_x="LMARGIN", new_y="NEXT")
    pdf.font(True, 22)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 11, pdf.t(stone_name), new_x="LMARGIN", new_y="NEXT")
    pdf.font(size=10)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 6, pdf.t(f"ออกเมื่อ {_thai_date(datetime.now())}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    finish = FINISH_LABEL.get(round(finish_multiplier, 2), f"ตัวคูณผิวสัมผัส ×{finish_multiplier:g}")
    rows = [
        ("หิน", stone_name, False),
        ("ขนาดพื้นที่", f"{width_m:g} × {length_m:g} ม. = {area:.2f} ตร.ม.", False),
        ("ราคาหิน/ตร.ม.", _baht(base_price_per_sqm), False),
        ("ผิวสัมผัส", finish, False),
        ("ค่าวัสดุ", _baht(material), False),
        (f"ค่าติดตั้ง ({_baht(install_rate_per_sqm)}/ตร.ม.)", _baht(install), False),
        ("รวมก่อน VAT", _baht(subtotal), False),
        ("VAT 7%", _baht(vat), False),
    ]
    for lab, val, bold in rows:
        pdf.font(bold, 11)
        pdf.set_text_color(*GRAY)
        pdf.cell(80, 8, pdf.t(lab))
        pdf.set_text_color(*DARK)
        pdf.cell(0, 8, pdf.t(val), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(225, 220, 210)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())

    pdf.ln(4)
    pdf.font(True, 15)
    pdf.set_text_color(*DARK)
    pdf.cell(100, 11, pdf.t("ราคารวมโดยประมาณ"))
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 11, pdf.t(_baht(total)), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.font(size=9)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(0, 5, pdf.t("หมายเหตุ: ราคาทั้งหมดเป็นการประมาณการเบื้องต้นเท่านั้น ราคาจริงขึ้นกับผู้จำหน่ายและหน้างาน"),
                   new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
