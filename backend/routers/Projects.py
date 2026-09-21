"""
API Projects: "โปรเจกต์ของฉัน" ผูกกับบัญชีผู้ใช้จริง (แทนที่ localStorage)

ทุก endpoint ต้อง login ก่อน (แนบ Authorization: Bearer <token>) และเข้าถึงได้แค่
โปรเจกต์ของตัวเองเท่านั้น — คนอื่นมองไม่เห็น แก้ไม่ได้ ลบไม่ได้

- POST   /projects                        — สร้างโปรเจกต์ใหม่
- GET    /projects                        — รายชื่อโปรเจกต์ของตัวเอง
- GET    /projects/{id}                   — ดูโปรเจกต์เดียว พร้อมรายการข้างใน
- DELETE /projects/{id}                   — ลบโปรเจกต์ (รายการข้างในลบตามอัตโนมัติ)
- POST   /projects/{id}/items             — เพิ่มรายการเข้าโปรเจกต์ (หิน/ราคา/คำแนะนำ AI)
- DELETE /projects/{id}/items/{item_id}   — ลบรายการออกจากโปรเจกต์
"""
import sys
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import get_db
from models import User, Project, ProjectItem
from routers.Auth import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

VALID_KINDS = ("granite", "price", "advisor", "inspiration")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    name: str


class ProjectItemCreateRequest(BaseModel):
    kind: str
    title: str
    detail: Optional[Any] = None


class ProjectItemResponse(BaseModel):
    id: int
    kind: str
    title: str
    detail: Optional[Any] = None

    model_config = {"from_attributes": True}


class ProjectSummaryResponse(BaseModel):
    id: int
    name: str
    item_count: int


class ProjectDetailResponse(BaseModel):
    id: int
    name: str
    items: List[ProjectItemResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helper: ดึงโปรเจกต์พร้อมเช็คว่าเป็นเจ้าของจริง (ใช้ซ้ำหลาย endpoint)
# ---------------------------------------------------------------------------

def _get_owned_project(project_id: int, current_user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="ไม่พบโปรเจกต์นี้")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="เข้าถึงโปรเจกต์นี้ได้แค่เจ้าของเท่านั้น")
    return project


# ---------------------------------------------------------------------------
# POST /projects
# ---------------------------------------------------------------------------

@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="กรุณาตั้งชื่อโปรเจกต์")
    project = Project(user_id=current_user.id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


# ---------------------------------------------------------------------------
# GET /projects
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ProjectSummaryResponse])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = (
        db.query(Project)
        .options(joinedload(Project.items))
        .filter(Project.user_id == current_user.id)
        .order_by(Project.id.desc())
        .all()
    )
    return [
        ProjectSummaryResponse(id=p.id, name=p.name, item_count=len(p.items))
        for p in projects
    ]


# ---------------------------------------------------------------------------
# GET /projects/{id}
# ---------------------------------------------------------------------------

@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_project(project_id, current_user, db)


# ---------------------------------------------------------------------------
# DELETE /projects/{id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user, db)
    db.delete(project)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# POST /projects/{id}/items
# ---------------------------------------------------------------------------

@router.post("/{project_id}/items", response_model=ProjectItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    project_id: int,
    request: ProjectItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user, db)
    if request.kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind ต้องเป็นหนึ่งใน {', '.join(VALID_KINDS)} เท่านั้น",
        )
    item = ProjectItem(
        project_id=project.id,
        kind=request.kind,
        title=request.title,
        detail=request.detail,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# DELETE /projects/{id}/items/{item_id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    project_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user, db)
    item = (
        db.query(ProjectItem)
        .filter(ProjectItem.id == item_id, ProjectItem.project_id == project.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="ไม่พบรายการนี้ในโปรเจกต์")
    db.delete(item)
    db.commit()
    return None
