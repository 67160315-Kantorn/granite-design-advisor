"""
models.py — SQLAlchemy ORM models ตรงกับตารางใน schema.sql
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, TIMESTAMP, ForeignKey,
    DECIMAL, Text, JSON, Enum, func,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="projects")
    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")


class ProjectItem(Base):
    __tablename__ = "project_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind = Column(Enum("granite", "price", "advisor", "inspiration", name="item_kind"), nullable=False)
    title = Column(String(255), nullable=False)
    detail = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    project = relationship("Project", back_populates="items")


class GraniteProduct(Base):
    __tablename__ = "granite_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_title = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=True)
    product_price = Column(DECIMAL(10, 2), nullable=False, default=0)
    image_url = Column(String(500), nullable=True)
    product_url = Column(String(500), nullable=True)
    color = Column(String(30), nullable=True)
    material = Column(String(20), nullable=True)
    styles = Column(JSON, nullable=True)   # เช่น ["Luxury", "Modern"]
    areas = Column(JSON, nullable=True)    # เช่น ["kitchen", "counter"]
    indoor = Column(String(10), nullable=True)  # "indoor" หรือ "both"
    rating = Column(JSON, nullable=True)   # เช่น {"price":4,"durability":5,...}
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
