# -*- coding: utf-8 -*-
"""历年真题卷列表（考生端「历年真题」入口）。

真题卷本身还是普通考试（复用判分、交卷、记录那套逻辑），
只是用 kind='past_paper' 标出来，单独从这个接口列出去，
不混在「我的考试」里。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/past-papers", tags=["past-papers"])

# 分卷在页面上的先后顺序
PAPER_ORDER = ["基础知识", "相关专业知识", "专业知识", "专业实践能力"]


@router.get("")
def list_past_papers(db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """按年份分组返回历年真题卷，附考生自己的最好成绩。"""
    papers = db.query(models.QuestionPaper).filter(
        models.QuestionPaper.kind == "paper").order_by(
        models.QuestionPaper.year, models.QuestionPaper.id).all()

    exams = {}
    if papers:
        exam_ids = [p.exam_id for p in papers if p.exam_id]
        for e in db.query(models.Exam).filter(models.Exam.id.in_(exam_ids)).all():
            exams[e.id] = e

    # 考生在各卷的最好成绩
    best = {}
    attempts = {}
    if exams:
        rows = db.query(models.ExamRecord.exam_id, models.ExamRecord.score).filter(
            models.ExamRecord.user_id == current_user.id,
            models.ExamRecord.exam_id.in_(list(exams.keys()))).all()
        for exam_id, score in rows:
            attempts[exam_id] = attempts.get(exam_id, 0) + 1
            if score is None:
                continue
            if exam_id not in best or score > best[exam_id]:
                best[exam_id] = score

    items = []
    for p in papers:
        exam = exams.get(p.exam_id)
        if exam is None:
            continue
        items.append({
            "paper_id": p.id,
            "exam_id": exam.id,
            "year": p.year,
            "level": p.level,
            "paper_name": p.paper_name,
            "title": p.title,
            "question_count": p.question_count or len(exam.questions),
            "duration": exam.duration,
            "total_score": exam.total_score,
            "pass_score": exam.pass_score,
            "best_score": best.get(exam.id),
            "attempts": attempts.get(exam.id, 0),
            "done": exam.id in best,
        })

    # 按年份分组
    years = []
    index = {}
    for it in sorted(items, key=lambda x: (x["year"],
                                           PAPER_ORDER.index(x["paper_name"])
                                           if x["paper_name"] in PAPER_ORDER else 9)):
        y = it["year"]
        if y not in index:
            index[y] = {"year": y, "papers": []}
            years.append(index[y])
        index[y]["papers"].append(it)

    return {"years": years, "total": len(items)}
