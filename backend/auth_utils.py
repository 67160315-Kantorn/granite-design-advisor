"""
auth_utils.py — เข้ารหัสรหัสผ่าน (bcrypt) และออก/ตรวจ JWT token

การตั้งค่า (.env):
    JWT_SECRET_KEY=xxxxxxxx     (จำเป็น — สุ่มสตริงยาวๆ เก็บเป็นความลับ ห้ามหลุดขึ้น git)
    JWT_EXPIRE_MINUTES=1440     (ไม่ใส่ก็ได้ ค่า default = 1440 นาที = 24 ชั่วโมง)
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    if not SECRET_KEY:
        raise RuntimeError(
            "ยังไม่ได้ตั้งค่า JWT_SECRET_KEY — เพิ่มใน .env แล้ว restart server"
        )
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    if not SECRET_KEY:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
