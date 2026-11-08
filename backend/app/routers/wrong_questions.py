# -*- coding: utf-8 -*-
"""错题本接口。

每个账号一份错题记录：交卷判分时自动落库，考生可以随时查看、
按错题生成练习卷，或把错题记录导成 Excel。

错题本按 user_id 隔离，普通考生只能看自己的错题；
管理员可以看指定学员的（用于教学分析）。
"""
import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/wrong-questions", tags=["wrong-questions"])

@router.get("")
def list_wrong_questions(status: str = "wrong", q_type: str = "", category: str = "",
                         skip: int = 0, limit: int = 20,
                         db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    """列出错题记录。status 传空字符串表示连已掌握的一起返回。"""
    items, total = crud.get_wrong_questions(
        db, current_user.id, status=status, skip=skip, limit=limit,
        q_type=q_type, category=category)
    return {"items": items, "total": total}


@router.get("/stats")
def wrong_question_stats(db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    """错题本汇总：待练数、已掌握数、按题型分布。"""
    return crud.get_wrong_question_stats(db, current_user.id)


@router.delete("/{wrong_id}")
def delete_wrong_question(wrong_id: int, db: Session = Depends(get_db),
                           current_user=Depends(get_current_user)):
    """删掉一条错题记录（只允许删自己的）。"""
    if not crud.delete_wrong_question(db, current_user.id, wrong_id):
        raise HTTPException(status_code=404, detail="错题记录不存在")
    return {"ok": True}


@router.get("/practice-exams")
def list_practice_exams(db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    """我生成过的错题练习卷。"""
    rows = db.query(models.Exam).filter(
        models.Exam.kind == "wrong_practice",
        models.Exam.created_by == current_user.id
    ).order_by(models.Exam.id.desc()).all()
    items = []
    for e in rows:
        q_count = db.query(models.exam_question.c.question_id).filter(
            models.exam_question.c.exam_id == e.id).count()
        items.append({
            "exam_id": e.id,
            "title": e.title,
            "question_count": q_count,
            "total_score": e.total_score,
            "duration": e.duration,
            "created_at": e.created_at,
        })
    return {"items": items}


class GenerateExamIn(BaseModel):
    """生成错题练习卷的入参。

    要用 body 收，不能用查询参数：前端是 POST 一个 JSON 对象过来，
    参数写成普通函数参数的话 FastAPI 会去查询串里找，body 里的值全收不到，
    筛选项会静默变成默认值。
    """
    status: str = "wrong"     # wrong / mastered / ""（全部）
    q_type: str = ""          # 题型，空表示不限
    limit: int = 50           # 最多取几道题


@router.post("/generate-exam")
def generate_exam_from_wrong(payload: GenerateExamIn,
                             db: Session = Depends(get_db),
                             current_user=Depends(get_current_user)):
    """拿错题生成一场练习卷，返回可直接开考的考试 id。

    生成的是一张单独标记的卷子（kind=wrong_practice）：判分、交卷、
    错题本更新全都复用现成的一套逻辑，不另开一条路。
    """
    status = (payload.status or "").strip()
    items, _ = crud.get_wrong_questions(
        db, current_user.id, status=status, skip=0, limit=payload.limit)
    if payload.q_type:
        items = [i for i in items if i["type"] == payload.q_type]
    if not items:
        raise HTTPException(status_code=400, detail="没有符合条件的错题")

    question_ids = [i["question_id"] for i in items]
    if len(question_ids) > 200:
        question_ids = question_ids[:200]
    exam = crud.create_exam(db, schemas.ExamCreate(
        title="错题练习（%d题）" % len(question_ids),
        duration=max(10, len(question_ids)),
        question_ids=question_ids,
    ), creator_id=current_user.id)
    # 单独标一种 kind：这类卷子只有本人能做，也不混在正式考试列表里
    exam.kind = "wrong_practice"
    db.commit()
    db.refresh(exam)
    return {
        "exam_id": exam.id,
        "question_count": len(question_ids),
        "title": exam.title,
    }


@router.get("/export")
def export_wrong_questions(status: str = "wrong", q_type: str = "",
                            db: Session = Depends(get_db),
                            current_user=Depends(get_current_user)):
    """把错题记录导成 Excel：题干、正确答案、解析、我的错答、错误次数。"""
    items, _ = crud.get_wrong_questions(
        db, current_user.id, status=status, skip=0, limit=10000)
    if q_type:
        items = [i for i in items if i["type"] == q_type]
    if not items:
        raise HTTPException(status_code=404, detail="没有可导出的错题记录")
    buf = crud.export_wrong_questions_excel(db, current_user.id, items)
    filename = "错题记录.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
