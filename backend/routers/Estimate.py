"""
API Estimate: scrape ข้อมูลหินแกรนิตจาก siamtak.com แล้วเก็บเป็น CSV
- รัน scrape อัตโนมัติทุก 1 วัน
- Endpoints: อ่านข้อมูล, ดาวน์โหลด CSV, รัน scrape ทันที (refresh)
- Calculate: คำนวณตาม Flow (input → ราคาหินจาก MySQL → คำนวณพื้นที่/ราคารวม → แสดงผล)

หมายเหตุ: /calculate และ /products เปลี่ยนมาอ่านราคาจากตาราง granite_products ใน MySQL
แล้ว (แทนที่จะอ่าน CSV ตรงๆ เหมือนเดิม) เพราะตอนนี้มี Catalog DB จริงตามสถาปัตยกรรมที่วางแผนไว้
ส่วน scraper (/refresh) ยังคงเขียนผลลัพธ์ดิบลง CSV เหมือนเดิม (เป็นขั้น "staging" ก่อนคัดกรอง
ข้อมูลเข้า DB) — /csv ยังดาวน์โหลดไฟล์ CSV ดิบนั้นได้ตามปกติ
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scrape_granite import CSV_PATH, run_granite_scrape
from database import SessionLocal
from models import GraniteProduct

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/estimate", tags=["Estimate"])

_scheduler = None


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(run_granite_scrape, "interval", days=1, id="granite_scrape")
        logger.info("Estimate: scheduled granite scrape every 1 day")
    return _scheduler


def start_estimate_scheduler():
    """เรียกจาก main.py ตอน startup เพื่อให้รัน scrape ทุก 1 วัน"""
    _get_scheduler().start()


# ---------------------------------------------------------------------------
# Calculate ตาม Flow: Input → ราคาหินจาก MySQL → คำนวณพื้นที่/ราคารวม → แสดงผล
# ---------------------------------------------------------------------------

def _load_products_db() -> list:
    """โหลดรายการหินจากตาราง granite_products ใน MySQL"""
    db = SessionLocal()
    try:
        return db.query(GraniteProduct).all()
    finally:
        db.close()


def _get_stone_price_by_type(products: list, stone_type: str) -> Optional[float]:
    """
    ตรวจสอบราคาหินตามประเภท (product_title) จากข้อมูลใน MySQL
    คืนราคาต่อ ตร.ม (บาท) หรือ None ถ้าไม่เจอ
    """
    stone_upper = (stone_type or "").strip().upper()
    if not stone_upper:
        return None
    for p in products:
        title = (p.product_title or "").strip().upper()
        if stone_upper in title or title in stone_upper:
            return float(p.product_price)
    # fuzzy: ถ้าไม่ match เต็ม ใช้ตัวแรกที่ขึ้นต้นตรง
    for p in products:
        title = (p.product_title or "").strip().upper()
        if title.startswith(stone_upper) or stone_upper.startswith(title):
            return float(p.product_price)
    return None


class CalculateRequest(BaseModel):
    """Input ตาม Flow: พื้นที่ (ตร.ม), ประเภทหิน, งบประมาณ (ถ้ามี). หรือส่งกว้าง×ยาวแทนพื้นที่"""
    area_sqm: Optional[float] = None
    width_m: Optional[float] = None
    length_m: Optional[float] = None
    stone_type: str
    budget: Optional[float] = None


class CalculateResponse(BaseModel):
    area_sqm: float
    price_per_sqm: float
    total_price: float
    stone_type: str
    within_budget: Optional[bool] = None
    message: str


@router.post("/calculate", response_model=CalculateResponse)
def calculate(request: CalculateRequest):
    """
    คำนวณตาม Flow:
    1. Input: พื้นที่ (หรือ กว้าง×ยาว), ประเภทหิน, งบประมาณ(ถ้ามี)
    2. ตรวจสอบราคาหินจากตาราง granite_products ใน MySQL
    3. คำนวณพื้นที่ = กว้าง × ยาว (ถ้าไม่ได้ส่ง area_sqm)
    4. คำนวณราคารวม = พื้นที่ × ราคาต่อหน่วย
    5. แสดงคำตอบ (และเปรียบกับงบถ้ามี)
    """
    products = _load_products_db()
    if not products:
        raise HTTPException(
            status_code=404,
            detail="ยังไม่มีข้อมูลราคาหินในฐานข้อมูล ให้ import seed_catalog.sql ก่อน",
        )

    if request.area_sqm is not None and request.area_sqm > 0:
        area_sqm = request.area_sqm
    elif request.width_m is not None and request.length_m is not None and request.width_m > 0 and request.length_m > 0:
        area_sqm = request.width_m * request.length_m
    else:
        raise HTTPException(
            status_code=400,
            detail="กรุณาส่ง area_sqm หรือ (width_m และ length_m) ที่ถูกต้อง",
        )

    price_per_sqm = _get_stone_price_by_type(products, request.stone_type)
    if price_per_sqm is None:
        raise HTTPException(
            status_code=404,
            detail=f"ไม่พบประเภทหิน '{request.stone_type}' ในรายการ กรุณาใช้ชื่อจาก GET /estimate/products",
        )

    total_price = area_sqm * price_per_sqm

    within_budget = None
    if request.budget is not None:
        within_budget = total_price <= request.budget

    message = (
        f"พื้นที่ {area_sqm:.2f} ตร.ม × ราคา {price_per_sqm:,.0f} บาท/ตร.ม = ราคารวม {total_price:,.2f} บาท"
    )
    if request.budget is not None:
        message += " อยู่ในงบประมาณ" if within_budget else " เกินงบประมาณ"

    return CalculateResponse(
        area_sqm=round(area_sqm, 2),
        price_per_sqm=price_per_sqm,
        total_price=round(total_price, 2),
        stone_type=request.stone_type,
        within_budget=within_budget,
        message=message,
    )


@router.get("/products")
def get_products():
    """อ่านข้อมูลหินแกรนิตจากตาราง granite_products ใน MySQL (JSON)"""
    products = _load_products_db()
    if not products:
        raise HTTPException(status_code=404, detail="ยังไม่มีข้อมูลในฐานข้อมูล ให้ import seed_catalog.sql ก่อน")
    rows = [
        {
            "product_title": p.product_title,
            "product_description": p.product_description,
            "product_price": str(p.product_price),
            "image_url": p.image_url,
            "product_url": p.product_url,
        }
        for p in products
    ]
    return {"count": len(rows), "products": rows}


@router.get("/csv")
def download_csv():
    """ดาวน์โหลดไฟล์ CSV ดิบจากการ scrape ล่าสุด (ก่อนคัดกรองเข้า DB)"""
    if not CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="ยังไม่มีไฟล์ CSV ให้รัน POST /estimate/refresh ก่อน")
    return FileResponse(
        path=CSV_PATH,
        filename=CSV_PATH.name,
        media_type="text/csv",
    )


@router.post("/refresh")
def refresh_scrape():
    """รัน scrape หินแกรนิตจาก siamtak ทันที แล้วอัปเดตไฟล์ CSV ดิบ (ไม่ต้องรอ 1 วัน)
    หมายเหตุ: การ scrape ครั้งนี้เขียนแค่ CSV ยังไม่ได้อัปเดตตาราง granite_products อัตโนมัติ
    ต้องคัดกรอง/รัน seed script ใหม่เองถ้าต้องการเอาข้อมูลชุดใหม่เข้า DB จริง"""
    result = run_granite_scrape()
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("message", "Scrape failed"))
    return result
