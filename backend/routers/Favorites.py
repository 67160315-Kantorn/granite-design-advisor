"""
API รายการโปรด (ต้อง login)

- GET    /favorites               — รายการ id หินที่ผู้ใช้กดหัวใจไว้
- PUT    /favorites/{product_id}  — เพิ่มเข้ารายการโปรด (เรียกซ้ำได้ ไม่เกิด error)
- DELETE /favorites/{product_id}  — เอาออกจากรายการโปรด
"""
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import get_db
from models import Favorite, GraniteProduct, User
from routers.Auth import get_current_user

router = APIRouter(tags=["Favorites"])


class FavoritesResponse(BaseModel):
    product_ids: List[int]


@router.get("/favorites", response_model=FavoritesResponse)
def list_favorites(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Favorite.product_id)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .all()
    )
    return {"product_ids": [r[0] for r in rows]}


@router.put("/favorites/{product_id}", response_model=FavoritesResponse)
def add_favorite(product_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.query(GraniteProduct.id).filter(GraniteProduct.id == product_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบหินชนิดนี้")
    exists = (
        db.query(Favorite.id)
        .filter(Favorite.user_id == current_user.id, Favorite.product_id == product_id)
        .first()
    )
    if not exists:
        db.add(Favorite(user_id=current_user.id, product_id=product_id))
        db.commit()
    return list_favorites(current_user, db)


@router.delete("/favorites/{product_id}", response_model=FavoritesResponse)
def remove_favorite(product_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Favorite).filter(
        Favorite.user_id == current_user.id, Favorite.product_id == product_id
    ).delete(synchronize_session=False)
    db.commit()
    return list_favorites(current_user, db)
