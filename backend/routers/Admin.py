"""
API แดชบอร์ดแอดมิน (เฉพาะ role = admin)

- GET /admin/stats — สถิติรวมของระบบ: สมาชิก, โปรเจกต์, แชต, แคตตาล็อก, หินยอดนิยม
"""
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import get_db
from models import ChatMessage, Favorite, GraniteProduct, Project, ProjectItem, User
from routers.Auth import require_admin

router = APIRouter(tags=["Admin"])


def _top(counter: Counter, limit: int = 5):
    return [{"name": k, "count": v} for k, v in counter.most_common(limit)]


@router.get("/admin/stats")
def admin_stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = date.today()
    week_ago_dt = datetime.now() - timedelta(days=7)

    # ---- สมาชิก ----
    users_total = db.query(func.count(User.id)).scalar() or 0
    admins = db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
    new_7d = db.query(func.count(User.id)).filter(User.created_at >= week_ago_dt).scalar() or 0
    per_day = {
        str(d): c
        for d, c in db.query(func.date(User.created_at), func.count(User.id))
        .filter(User.created_at >= datetime.combine(today - timedelta(days=6), datetime.min.time()))
        .group_by(func.date(User.created_at))
        .all()
    }
    signups = []
    for i in range(6, -1, -1):
        d = str(today - timedelta(days=i))
        signups.append({"date": d, "count": per_day.get(d, 0)})

    # ---- โปรเจกต์ ----
    projects_total = db.query(func.count(Project.id)).scalar() or 0
    items_by_kind = {k: c for k, c in db.query(ProjectItem.kind, func.count(ProjectItem.id)).group_by(ProjectItem.kind).all()}

    # ---- แชต ----
    chat_total = db.query(func.count(ChatMessage.id)).scalar() or 0
    chat_questions = db.query(func.count(ChatMessage.id)).filter(ChatMessage.role == "user").scalar() or 0
    chat_users = db.query(func.count(func.distinct(ChatMessage.user_id))).scalar() or 0
    chat_7d = db.query(func.count(ChatMessage.id)).filter(ChatMessage.role == "user", ChatMessage.created_at >= week_ago_dt).scalar() or 0

    # ---- แคตตาล็อก ----
    products_total = db.query(func.count(GraniteProduct.id)).scalar() or 0
    avg_price = db.query(func.avg(GraniteProduct.product_price)).scalar() or 0
    by_material = {(m or "ไม่ระบุ"): c for m, c in db.query(GraniteProduct.material, func.count(GraniteProduct.id)).group_by(GraniteProduct.material).all()}
    by_color = {(m or "ไม่ระบุ"): c for m, c in db.query(GraniteProduct.color, func.count(GraniteProduct.id)).group_by(GraniteProduct.color).all()}

    # ---- หินยอดนิยม ----
    top_fav = [
        {"name": name, "count": c}
        for name, c in db.query(GraniteProduct.product_title, func.count(Favorite.id))
        .join(Favorite, Favorite.product_id == GraniteProduct.id)
        .group_by(GraniteProduct.id, GraniteProduct.product_title)
        .order_by(func.count(Favorite.id).desc())
        .limit(5)
        .all()
    ]
    top_project = [
        {"name": t, "count": c}
        for t, c in db.query(ProjectItem.title, func.count(ProjectItem.id))
        .filter(ProjectItem.kind == "granite")
        .group_by(ProjectItem.title)
        .order_by(func.count(ProjectItem.id).desc())
        .limit(5)
        .all()
    ]
    ai_counter: Counter = Counter()
    rows = (
        db.query(ChatMessage.products)
        .filter(ChatMessage.role == "assistant", ChatMessage.products.isnot(None))
        .order_by(ChatMessage.id.desc())
        .limit(5000)
        .all()
    )
    for (prods,) in rows:
        for p in prods or []:
            if isinstance(p, dict) and p.get("name"):
                ai_counter[p["name"]] += 1

    return {
        "users": {"total": users_total, "admins": admins, "new_7d": new_7d, "signups_7d": signups},
        "projects": {"total": projects_total, "items_by_kind": items_by_kind},
        "chat": {"messages": chat_total, "questions": chat_questions, "users": chat_users, "questions_7d": chat_7d},
        "catalog": {
            "total": products_total,
            "avg_price": round(float(avg_price), 0),
            "by_material": by_material,
            "by_color": by_color,
        },
        "favorites_total": db.query(func.count(Favorite.id)).scalar() or 0,
        "top": {"favorited": top_fav, "ai_recommended": _top(ai_counter), "in_projects": top_project},
    }
