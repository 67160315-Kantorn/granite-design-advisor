"""
database.py — ตั้งค่าการเชื่อมต่อ MySQL ผ่าน SQLAlchemy

อ่านค่าเชื่อมต่อจาก environment variables ที่ docker-compose.yml กำหนดให้:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "granite_db")
DB_USER = os.environ.get("DB_USER", "granite_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# pool_pre_ping=True: เช็ค connection ก่อนใช้ทุกครั้ง กัน error "MySQL server has gone away"
# ที่มักเกิดถ้า connection ถูกปิดทิ้งไปเฉยๆ (เช่น container MySQL restart)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: เปิด session ต่อ request แล้วปิดให้อัตโนมัติเมื่อ request จบ"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
