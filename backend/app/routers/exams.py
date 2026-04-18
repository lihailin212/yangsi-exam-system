from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/exams", tags=["exams"])
record_router = APIRouter(prefix="/api/exam-records", tags=["records"])

@router.get("")
def list_exams(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), _=Depends(get_current_user)):
    exams, total = crud.get_exams(db, skip=skip, limit=limit)
    result = []
    for e in exams:
        result.append({
            "id": e.id,
            "title": e.title,
            "duration": e.duration,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "pass_score": e.pass_score,
            "total_score": e.total_score,
            "retake_limit": e.retake_limit,
            "created_at": e.created_at,
            "question_count": len(e.questions),
            "participant_count": len(e.records),
        })
    return {"items": result, "total": total}

@router.get("/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    score_map = {
        "single": exam.single_score,
        "multiple": exam.multiple_score,
        "judgment": exam.judgment_score,
    }
    questions = []
    for q in exam.questions:
        qd = schemas.QuestionOut.model_validate(q).model_dump()
        qd["score"] = score_map.get(q.type, 10)
        questions.append(qd)
    return {
        "id": exam.id,
        "title": exam.title,
        "duration": exam.duration,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "pass_score": exam.pass_score,
        "single_score": exam.single_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "retake_limit": exam.retake_limit,
        "total_score": exam.total_score,
        "created_at": exam.created_at,
        "questions": questions,
        "question_ids": [q.id for q in exam.questions],
    }

@router.post("", response_model=schemas.ExamOut)
def create_exam(exam_in: schemas.ExamCreate, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    exam = crud.create_exam(db, exam_in, current_user.id)
    return {
        "id": exam.id,
        "title": exam.title,
        "duration": exam.duration,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "pass_score": exam.pass_score,
        "single_score": exam.single_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "created_at": exam.created_at,
        "created_by": exam.created_by,
        "question_count": len(exam.questions),
        "participant_count": len(exam.records),
    }

@router.put("/{exam_id}")
def update_exam(exam_id: int, exam_in: schemas.ExamUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    exam = crud.update_exam(db, exam_id, exam_in)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    return {
        "id": exam.id,
        "title": exam.title,
        "duration": exam.duration,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "pass_score": exam.pass_score,
        "single_score": exam.single_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "created_at": exam.created_at,
        "created_by": exam.created_by,
        "question_count": len(exam.questions),
        "participant_count": len(exam.records),
    }

@router.delete("/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    crud.delete_exam(db, exam_id)
    return {"ok": True}

@router.post("/{exam_id}/submit", response_model=schemas.ExamRecordOut)
def submit_exam(exam_id: int, record_in: schemas.ExamRecordCreate,
                db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    record_in.exam_id = exam_id
    record = crud.submit_exam(db, record_in, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="考试不存在")
    return record

@router.get("/{exam_id}/records")
def get_exam_records(exam_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    records = crud.get_exam_records(db, exam_id)
    result = []
    for r in records:
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_name": r.user.name if r.user else "",
            "employee_id": r.user.employee_id if r.user else "",
            "exam_title": r.exam.title if r.exam else "",
            "score": r.score,
            "total_score": r.total_score,
            "percent": round(r.score / r.total_score * 100, 1) if r.total_score > 0 else 0,
            "submitted_at": r.submitted_at,
        })
    return result

@record_router.get("/recent")
def get_recent_records(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """获取最近的考试提交记录（用于通知）"""
    from ..models import ExamRecord
    records = db.query(ExamRecord).order_by(ExamRecord.submitted_at.desc()).limit(10).all()
    result = []
    for r in records:
        if r.user:
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "user_name": r.user.name,
                "employee_id": r.user.employee_id,
                "exam_id": r.exam_id,
                "exam_title": r.exam.title if r.exam else "",
                "score": r.score,
                "total_score": r.total_score,
                "percent": round(r.score / r.total_score * 100, 1) if r.total_score > 0 else 0,
                "submitted_at": r.submitted_at,
            })
    return result

@record_router.get("/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from ..models import ExamRecord
    r = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    return schemas.ExamRecordOut.model_validate(r)

@record_router.get("/user/{user_id}/exam/{exam_id}")
def get_user_exam_record(user_id: int, exam_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from ..models import ExamRecord
    r = db.query(ExamRecord).filter(
        ExamRecord.user_id == user_id,
        ExamRecord.exam_id == exam_id
    ).first()
    if not r:
        return None
    return {
        "id": r.id,
        "score": r.score,
        "total_score": r.total_score,
        "submitted_at": r.submitted_at,
    }
