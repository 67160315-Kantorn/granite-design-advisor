"""
API Auth: สมัครสมาชิก / เข้าสู่ระบบ / ออกจากระบบ / เปลี่ยนรหัสผ่าน

ใช้ JWT (JSON Web Token) แบบ stateless:
- POST /auth/register — สมัครสมาชิก คืน user object (ไม่คืน token ให้ต้อง login เอง)
- POST /auth/login — เข้าสู่ระบบ คืน access_token (JWT) ให้เก็บไว้ฝั่ง client แล้วแนบไปกับ
  request อื่นๆ ที่ต้อง login ก่อน ผ่าน header: Authorization: Bearer <token>
- POST /auth/logout — เพราะ JWT เป็น stateless server ไม่ได้เก็บ session ไว้ที่ไหน
  "logout" จริงๆ คือฝั่ง frontend ลบ token ที่เก็บไว้ทิ้งเอง endpoint นี้มีไว้ยืนยันตัวตน
  ก่อนบอกให้ client ลบ token (และเป็นจุดเผื่อไว้ถ้าจะทำ token blacklist ในอนาคต)
- POST /auth/change-password — ต้อง login ก่อน (ส่ง token มาด้วย) ต้องใส่รหัสผ่านเดิมถูกต้อง
"""
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import get_db
from models import User
from auth_utils import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

# tokenUrl แค่บอก Swagger UI (/docs) ว่า endpoint ไหนใช้ขอ token — ไม่ได้ผูก logic จริง
# auto_error=False: ถ้าไม่ส่ง token มา ให้ผ่านมาก่อนแล้วเราเช็คเองใน get_current_user
# (เพื่อคุมข้อความ error ให้เป็นภาษาไทยเองแทนที่จะให้ FastAPI ขึ้น error default)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,50}$")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="a-z, A-Z, 0-9, _ เท่านั้น")
    email: EmailStr
    password: str = Field(..., min_length=8, description="อย่างน้อย 8 ตัวอักษร")
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dependency: ดึง user ปัจจุบันจาก JWT token (ใช้ใน endpoint ที่ต้อง login ก่อน)
# ---------------------------------------------------------------------------

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ยังไม่ได้ login")
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token ไม่ถูกต้องหรือหมดอายุ")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ไม่พบผู้ใช้ หรือบัญชีถูกปิดใช้งาน")
    return user


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """สมัครสมาชิกใหม่ — username และ email ต้องไม่ซ้ำกับที่มีอยู่แล้ว"""
    if not USERNAME_RE.match(request.username):
        raise HTTPException(
            status_code=400,
            detail="username ต้องเป็นตัวอักษร a-z, A-Z, ตัวเลข, หรือ _ เท่านั้น (3-50 ตัวอักษร)",
        )

    existing = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing:
        field = "username" if existing.username == request.username else "email"
        raise HTTPException(status_code=409, detail=f"{field} นี้มีผู้ใช้แล้ว")

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """เข้าสู่ระบบด้วย username + password คืน JWT access token"""
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="username หรือ password ไม่ถูกต้อง")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="บัญชีนี้ถูกปิดใช้งาน")

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    ออกจากระบบ — เพราะ JWT เป็น stateless (server ไม่เก็บ session)
    การ "logout" จริงๆ ต้องทำที่ฝั่ง frontend: ลบ token ที่เก็บไว้ใน localStorage ทิ้ง
    endpoint นี้แค่ยืนยันว่า token ที่ส่งมายังใช้งานได้อยู่ตอนที่กด logout
    """
    return {"message": f"ออกจากระบบสำเร็จ (username: {current_user.username}) — กรุณาลบ token ฝั่ง client ด้วย"}


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------

@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """เปลี่ยนรหัสผ่าน — ต้อง login ก่อน (แนบ token) และใส่รหัสผ่านเดิมให้ถูกต้อง"""
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="รหัสผ่านเดิมไม่ถูกต้อง")
    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}
