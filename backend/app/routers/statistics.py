from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud
from ..auth import require_admin

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("")
def get_statistics(db: Session = Depends(get_db), _=Depends(require_admin)):
    return crud.get_statistics(db)


@router.get("/records")
def get_statistics_records(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
    exam_id: int = Query(None),
    user_id: int = Query(None),
    keyword: str = Query(None),
    limit: int = Query(500, ge=1, le=2000),
):
    """每条交卷记录的明细：姓名 / 工号 / 考试 / 成绩 / 用时 / 答题次数。"""
    return crud.get_statistics_records(
        db, exam_id=exam_id, user_id=user_id, keyword=keyword, limit=limit
    )


@router.get("/recent-activity")
def get_recent_activity(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
    limit: int = Query(10, ge=1, le=50),
):
    """首页"最近动态"：最近交卷 / 开始作答 / 新学员注册的真实记录。"""
    return crud.get_recent_activity(db, limit=limit)


@router.get("/trend")
def get_statistics_trend(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
    days: int = Query(7, ge=1, le=400),
):
    """交卷量趋势：days<=60 按天，超过按月。"""
    return crud.get_statistics_trend(db, days=days)
