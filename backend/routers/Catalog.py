"""
API Catalog: ให้บริการข้อมูลหินแกรนิต/หินอ่อนจาก MySQL (แทนที่การอ่านจาก CSV ตรงๆ)

- GET /granite-products             — รายการหินทั้งหมด กรองได้ตาม color / style / area / material
- GET /granite-products/{id}        — ข้อมูลหินชิ้นเดียว

endpoint พวกนี้ "ไม่ต้อง login" เพราะเป็นข้อมูลสินค้าสาธารณะที่ทุกคนดูได้
(ต่างจาก /projects ที่ต้อง login เพราะเป็นข้อมูลส่วนตัวของแต่ละคน)
"""
import sys
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import SessionLocal
from models import GraniteProduct

router = APIRouter(tags=["Catalog"])


class GraniteProductResponse(BaseModel):
    id: int
    product_title: str
    product_description: Optional[str] = None
    product_price: float
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    styles: Optional[List[str]] = None
    areas: Optional[List[str]] = None
    indoor: Optional[str] = None
    rating: Optional[Any] = None

    model_config = {"from_attributes": True}


def _get_db_session() -> Session:
    """
    endpoint นี้ไม่ต้อง login เลยไม่ได้ใช้ Depends(get_db) เหมือน router อื่น (ที่ผูกกับ
    request lifecycle ของ FastAPI) — เปิด/ปิด session ตรงๆ ในฟังก์ชันแทนเพื่อความง่าย
    """
    return SessionLocal()


@router.get("/granite-products", response_model=List[GraniteProductResponse])
def list_products(
    color: Optional[str] = Query(None, description="เช่น black, white, brown, green, blue, red, grey"),
    style: Optional[str] = Query(None, description="เช่น Modern, Minimal, Luxury, Classic"),
    area: Optional[str] = Query(None, description="เช่น kitchen, bathroom, counter"),
    material: Optional[str] = Query(None, description="granite หรือ marble"),
):
    """รายการหินทั้งหมด กรองได้หลายเงื่อนไขพร้อมกัน (ใส่ query param ไหนก็กรองตามนั้น)"""
    db = _get_db_session()
    try:
        query = db.query(GraniteProduct)
        if color:
            query = query.filter(GraniteProduct.color == color)
        if material:
            query = query.filter(GraniteProduct.material == material)
        products = query.order_by(GraniteProduct.id).all()

        # style / area เก็บเป็น JSON array ใน MySQL — กรองแบบ "อยู่ใน list ไหม" ทำง่ายสุด
        # ด้วย Python หลัง query กลับมาแล้ว (ข้อมูลแค่ ~24 ชิ้น ไม่กระทบ performance)
        if style:
            products = [p for p in products if p.styles and style in p.styles]
        if area:
            products = [p for p in products if p.areas and area in p.areas]

        return products
    finally:
        db.close()


@router.get("/granite-products/{product_id}", response_model=GraniteProductResponse)
def get_product(product_id: int):
    """ข้อมูลหินชิ้นเดียวตาม id"""
    db = _get_db_session()
    try:
        product = db.query(GraniteProduct).filter(GraniteProduct.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="ไม่พบหินชนิดนี้")
        return product
    finally:
        db.close()
