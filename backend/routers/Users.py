"""
API User Management: จัดการข้อมูลผู้ใช้

- GET  /me                     — ดึงข้อมูลตัวเอง (ต้อง login)
- GET  /users/{id}             — ดึงข้อมูล user คนใดคนหนึ่ง (ต้อง login)
- GET  /users                  — ดึงรายชื่อ user ทั้งหมด แบบแบ่งหน้า (ต้อง login)
- PUT  /users/{id}             — แก้ไขข้อมูล user (แก้ได้แค่ของตัวเองเท่านั้น)
- DELETE /users/{id}           — ลบ user (ลบได้แค่ของตัวเองเท่านั้น)
- GET  /check-username/{name}  — เช็คว่า username ว่างไหม (ไม่ต้อง login — ใช้ตอนกรอกฟอร์มสมัคร)
"""
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import get_db
from models import User
from routers.Auth import get_current_user, UserResponse

router = APIRouter(tags=["User Management"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UsernameAvailableResponse(BaseModel):
    username: str
    available: bool


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """ดึงข้อมูลของตัวเอง (ใช้ token ที่ส่งมาหาว่าเป็นใคร)"""
    return current_user


# ---------------------------------------------------------------------------
# GET /users/{id}
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ดึงข้อมูล user คนใดคนหนึ่งตาม id (ต้อง login ก่อนถึงจะดูได้)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")
    return user


# ---------------------------------------------------------------------------
# GET /users (pagination)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1, description="เลขหน้า เริ่มที่ 1"),
    page_size: int = Query(20, ge=1, le=100, description="จำนวนต่อหน้า สูงสุด 100"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ดึงรายชื่อ user ทั้งหมด แบบแบ่งหน้า"""
    total = db.query(User).count()
    items = (
        db.query(User)
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# PUT /users/{id}
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    แก้ไขข้อมูล user — จำกัดไว้ว่าแก้ได้แค่ข้อมูลของตัวเองเท่านั้น
    (ยังไม่มีระบบ admin/role ในโปรเจกต์นี้ จึงยังไม่เปิดให้คนอื่นแก้ไขแทนกันได้)
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="แก้ไขได้แค่ข้อมูลของตัวเองเท่านั้น")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")

    if request.email is not None and request.email != user.email:
        existing = db.query(User).filter(User.email == request.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="email นี้มีผู้ใช้แล้ว")
        user.email = request.email

    if request.full_name is not None:
        user.full_name = request.full_name

    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# DELETE /users/{id}
# ---------------------------------------------------------------------------

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ลบบัญชี user — ลบได้แค่ของตัวเองเท่านั้น (โปรเจกต์/รายการของ user จะถูกลบตามไปด้วย
    อัตโนมัติเพราะตั้ง FOREIGN KEY ... ON DELETE CASCADE ไว้ใน schema.sql)"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="ลบได้แค่บัญชีของตัวเองเท่านั้น")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้นี้")

    db.delete(user)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# GET /check-username/{name}
# ---------------------------------------------------------------------------

@router.get("/check-username/{username}", response_model=UsernameAvailableResponse)
def check_username(username: str, db: Session = Depends(get_db)):
    """
    เช็คว่า username นี้ว่างไหม — endpoint นี้ตั้งใจไม่บังคับ login เพราะต้องเรียกใช้ได้
    ตอนกำลังกรอกฟอร์มสมัครสมาชิก (ซึ่งตอนนั้นยังไม่มี token เพราะยังไม่ได้เป็นสมาชิก)
    """
    exists = db.query(User).filter(User.username == username).first() is not None
    return UsernameAvailableResponse(username=username, available=not exists)
