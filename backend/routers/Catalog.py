"""
API Catalog: ให้บริการข้อมูลหินแกรนิต/หินอ่อนจาก MySQL (แทนที่การอ่านจาก CSV ตรงๆ)

- GET /granite-products             — รายการหินทั้งหมด กรองได้ตาม color / style / area / material
- GET /granite-products/{id}        — ข้อมูลหินชิ้นเดียว
- POST   /granite-products          — เพิ่มหินใหม่ (เฉพาะแอดมิน)
- PUT    /granite-products/{id}     — แก้ไขหิน (เฉพาะแอดมิน)
- DELETE /granite-products/{id}     — ลบหิน (เฉพาะแอดมิน)

endpoint พวกนี้ "ไม่ต้อง login" เพราะเป็นข้อมูลสินค้าสาธารณะที่ทุกคนดูได้
(ต่างจาก /projects ที่ต้อง login เพราะเป็นข้อมูลส่วนตัวของแต่ละคน)
"""
import sys
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from sqlalchemy import or_, text

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import SessionLocal, get_db
from models import GraniteProduct, User
from routers.Auth import require_admin
from routers.Chat import invalidate_products_cache

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
    q: Optional[str] = Query(None, description="คำค้นหาอิสระ เช่น ชื่อหินหรือคำบรรยาย (รองรับทั้งอังกฤษและไทย)"),
    color: Optional[str] = Query(None, description="เช่น black, white, brown, green, blue, red, grey"),
    style: Optional[str] = Query(None, description="เช่น Modern, Minimal, Luxury, Classic"),
    area: Optional[str] = Query(None, description="เช่น kitchen, bathroom, counter"),
    material: Optional[str] = Query(None, description="granite หรือ marble"),
    min_price: Optional[float] = Query(None, description="ราคาต่ำสุด (บาท/ตร.ม.)"),
    max_price: Optional[float] = Query(None, description="ราคาสูงสุด (บาท/ตร.ม.) — ใช้คู่กับงบประมาณที่ลูกค้าระบุ"),
):
    """รายการหินทั้งหมด กรองได้หลายเงื่อนไขพร้อมกัน (ใส่ query param ไหนก็กรองตามนั้น)"""
    db = _get_db_session()
    try:
        query = db.query(GraniteProduct)

        search_term = q.strip() if q else None
        fulltext_clause = None
        if search_term:
            # Hybrid search — ตั้งใจออกแบบแบบนี้ ไม่ใช่ FULLTEXT ล้วนๆ:
            # MySQL FULLTEXT (NATURAL LANGUAGE MODE) ใช้ idx_fulltext_search ได้ผลดีมากกับ
            # ชื่อหินภาษาอังกฤษ (คั่นด้วยช่องว่างปกติ ให้คะแนน relevance ที่มีความหมาย) แต่
            # "ใช้ไม่ได้เลย" กับคำค้นภาษาไทย เพราะ parser มาตรฐานของ MySQL ตัดคำโดยอาศัย
            # ช่องว่างระหว่างคำ ซึ่งภาษาไทยไม่มี (ทดสอบจริงแล้ว: ค้นคำไทยด้วย FULLTEXT ล้วนๆ
            # คืนผลเป็น 0 แถวเสมอ) จึง OR เพิ่ม LIKE '%...%' เป็น fallback ให้คำค้นภาษาไทย
            # หาเจอได้ด้วย (เคยลอง FULLTEXT ... WITH PARSER ngram แล้วด้วย แต่ default
            # ngram_token_size=2 ทำให้แทบทุกแถวแมตช์หมดแบบไม่เลือกเลย ไม่ใช้งานจริงได้)
            like_pattern = f"%{search_term}%"
            fulltext_clause = text(
                "MATCH(product_title, product_description) AGAINST (:search_term IN NATURAL LANGUAGE MODE)"
            ).bindparams(search_term=search_term)
            query = query.filter(
                or_(
                    fulltext_clause,
                    GraniteProduct.product_title.like(like_pattern),
                    GraniteProduct.product_description.like(like_pattern),
                )
            )

        if color:
            query = query.filter(GraniteProduct.color == color)
        if material:
            query = query.filter(GraniteProduct.material == material)
        # min_price/max_price กรองที่ระดับ SQL (ใช้ idx_price) ต่างจาก style/area ที่กรอง
        # ใน Python ทีหลัง เพราะราคาเป็นคอลัมน์ตัวเลขธรรมดา ไม่ใช่ JSON array
        if min_price is not None:
            query = query.filter(GraniteProduct.product_price >= min_price)
        if max_price is not None:
            query = query.filter(GraniteProduct.product_price <= max_price)

        if search_term:
            # เรียงตาม relevance ก่อน (คำค้นภาษาอังกฤษที่ตรงที่สุดจะขึ้นบนสุด) คำค้นภาษาไทย
            # ที่หาเจอผ่าน LIKE อย่างเดียวจะมี relevance=0 เรียงตามชื่อ A-Z แทน
            # หมายเหตุ: TextClause (จาก text()) ไม่มีเมธอด .desc() ให้ใช้เหมือน Column ปกติ
            # ต้องใส่ DESC เข้าไปใน SQL ดิบตรงๆ แทน (ใช้ชื่อ bind param แยกจาก fulltext_clause
            # ข้างบน กันตัวแปรชนกันตอน SQLAlchemy ประกอบ query สุดท้าย)
            relevance_order = text(
                "MATCH(product_title, product_description) "
                "AGAINST (:search_term_order IN NATURAL LANGUAGE MODE) DESC"
            ).bindparams(search_term_order=search_term)
            query = query.order_by(relevance_order, GraniteProduct.product_title.asc())
        else:
            query = query.order_by(GraniteProduct.id)
        products = query.all()

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


# ---------------------------------------------------------------------------
# แอดมิน: เพิ่ม / แก้ไข / ลบหิน  (ต้อง login ด้วยบัญชี role = admin)
# ---------------------------------------------------------------------------

RATING_KEYS = ("price", "durability", "maintenance", "modern", "luxury")


class ProductWriteRequest(BaseModel):
    product_title: str = Field(..., min_length=1, max_length=255)
    product_description: Optional[str] = None
    product_price: float = Field(..., ge=0)
    image_url: Optional[str] = Field(None, max_length=500)
    product_url: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, max_length=30)
    material: Optional[str] = Field(None, max_length=20)
    styles: List[str] = []
    areas: List[str] = []
    indoor: Optional[str] = Field(None, max_length=10)
    rating: Optional[dict] = None


def _clean_rating(rating: Optional[dict]) -> Optional[dict]:
    """เก็บเฉพาะคีย์คะแนนที่รู้จัก และบังคับเป็นจำนวนเต็ม 1-5"""
    if not rating:
        return None
    cleaned = {}
    for key in RATING_KEYS:
        if key in rating:
            try:
                value = int(rating[key])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"คะแนน {key} ต้องเป็นตัวเลข 1-5")
            if not 1 <= value <= 5:
                raise HTTPException(status_code=422, detail=f"คะแนน {key} ต้องอยู่ระหว่าง 1-5")
            cleaned[key] = value
    return cleaned or None


def _apply_fields(product: GraniteProduct, req: ProductWriteRequest) -> None:
    product.product_title = req.product_title.strip()
    product.product_description = req.product_description
    product.product_price = req.product_price
    product.image_url = req.image_url or None
    product.product_url = req.product_url or None
    product.color = req.color or None
    product.material = req.material or None
    product.styles = req.styles
    product.areas = req.areas
    product.indoor = req.indoor or None
    product.rating = _clean_rating(req.rating)


@router.post("/granite-products", response_model=GraniteProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductWriteRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """แอดมินเพิ่มหินใหม่"""
    product = GraniteProduct()
    _apply_fields(product, request)
    db.add(product)
    db.commit()
    db.refresh(product)
    invalidate_products_cache()
    return product


@router.put("/granite-products/{product_id}", response_model=GraniteProductResponse)
def update_product(
    product_id: int,
    request: ProductWriteRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """แอดมินแก้ไขข้อมูลหิน (ส่งค่าทุกช่องมาทับของเดิม)"""
    product = db.query(GraniteProduct).filter(GraniteProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="ไม่พบหินชนิดนี้")
    _apply_fields(product, request)
    db.commit()
    db.refresh(product)
    invalidate_products_cache()
    return product


@router.delete("/granite-products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """แอดมินลบหิน"""
    product = db.query(GraniteProduct).filter(GraniteProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="ไม่พบหินชนิดนี้")
    db.delete(product)
    db.commit()
    invalidate_products_cache()
    return None
