import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from urllib.parse import quote
from ..database import get_db
from .. import crud, schemas
from .. import paper as paper_lib
from ..auth import get_current_user, require_admin
from ..timeutil import SUBMIT_GRACE_SECONDS, app_now, to_epoch_ms, utc_now

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
            "random_mode": bool(getattr(e, "random_mode", False)),
            "created_at": e.created_at,
            "question_count": len(e.questions),
            "participant_count": len(e.records),
        })
    return {"items": result, "total": total}

@router.get("/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    score_map = {
        "single": exam.single_score,
        "multiple": exam.multiple_score,
        "judgment": exam.judgment_score,
        "fill": exam.fill_score,
    }
    # 只有管理员，或已交卷且无法再重考的考生，才能看到正确答案与解析，
    # 避免考生通过浏览器开发者工具直接读取答案。
    used_rounds, answered_count = crud.get_exam_progress(db, exam_id, current_user.id)
    retake_exhausted = exam.retake_limit > 0 and used_rounds >= exam.retake_limit
    exam_finished = exam.end_time is not None and exam.end_time < app_now()
    reveal_answers = current_user.is_admin or (
        answered_count > 0 and (retake_exhausted or exam_finished)
    )
    random_mode = bool(getattr(exam, "random_mode", False))
    if random_mode and not current_user.is_admin:
        # 随机卷：考生只看得到自己抽到的那份卷子，
        # 没抽过（还没开始考试）时先不给题，避免整池题目漏出去。
        attempt_no = crud.current_attempt_no(db, exam_id, current_user.id)
        try:
            exam_questions = crud.get_paper_questions(
                db, exam, current_user.id, attempt_no)
        except paper_lib.RuleError:
            # 规则和题库对不上时别把整个页面搞崩，提示管理员去调规则
            exam_questions = []
    else:
        exam_questions = crud.get_exam_questions(exam)
    questions = []
    for q in exam_questions:
        qd = schemas.QuestionOut.model_validate(q).model_dump()
        if not reveal_answers:
            qd["answer"] = ""
            qd["analysis"] = ""
        qd["score"] = score_map.get(q.type, 10)
        questions.append(qd)
    result = {
        "id": exam.id,
        "title": exam.title,
        "duration": exam.duration,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "pass_score": exam.pass_score,
        "single_score": exam.single_score,
        "fill_score": exam.fill_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "retake_limit": exam.retake_limit,
        "total_score": exam.total_score,
        "random_mode": random_mode,
        "random_rules": exam.random_rules or "[]",
        "created_at": exam.created_at,
        "questions": questions,
        "question_ids": [q.id for q in exam_questions],
    }
    return result


@router.post("/{exam_id}/start")
def start_exam(exam_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """考生进入考试：开启（或复用）本次作答会话，并下发权威截止时间。

    截止时间以服务端记录为准，前端只是据此显示倒计时。
    这样刷新页面、换设备、清浏览器缓存都无法把考试时间延长。
    """
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    now = app_now()
    if exam.start_time and exam.start_time > now:
        raise HTTPException(status_code=403, detail="考试尚未开始")
    if exam.end_time and exam.end_time < now:
        raise HTTPException(status_code=403, detail="考试已结束")
    # 允许名单校验：名单非空时，只有名单内考生可以作答
    if not crud.is_exam_allowed(db, exam_id, current_user.id):
        raise HTTPException(status_code=403, detail="您不用参加此次考试，谢谢！")
    # 先结算上一轮超时（按草稿自动交卷），再按"已用轮次"判次数上限。
    # 超时也占一轮，否则考生反复超时重进就能变相延长总作答时长。
    used, latest = crud.settle_and_count_rounds(db, exam, current_user.id)
    if exam.retake_limit > 0 and used >= exam.retake_limit:
        raise HTTPException(status_code=403, detail=f"该考试每人最多参加 {exam.retake_limit} 次，您已达上限")
    attempt = crud.start_attempt(db, exam, current_user.id, latest=latest)
    if not attempt:
        raise HTTPException(status_code=500, detail="无法开启作答会话")
    # 随机卷：抽题落库，并把这一轮抽到的题目一起下发，
    # 考生刷新页面拿到的还是同一份卷子。
    paper_ids = []
    if getattr(exam, "random_mode", False):
        try:
            paper_ids = crud.get_or_create_paper(
                db, exam, current_user.id, attempt.attempt_no)
        except paper_lib.RuleError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {
        "attempt_id": attempt.id,
        "attempt_no": attempt.attempt_no,
        "paper_question_ids": paper_ids,
        "deadline_ms": to_epoch_ms(attempt.deadline_at),
        "server_now_ms": to_epoch_ms(utc_now()),
        "duration": exam.duration,
    }


@router.get("/{exam_id}/preview-paper")
def preview_paper(exam_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """随机卷预览：按规则现抽一份样卷（不落库），方便管理员核对规则。"""
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    if not getattr(exam, "random_mode", False):
        return {"random_mode": False, "question_ids": [q.id for q in exam.questions]}
    rules = paper_lib.parse_rules(exam.random_rules)
    try:
        ids = paper_lib.build_paper(db, rules)
    except paper_lib.RuleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"random_mode": True, "question_ids": ids}


@router.post("/{exam_id}/draft")
def save_exam_draft(exam_id: int, payload: dict, db: Session = Depends(get_db),
                     current_user=Depends(get_current_user)):
    """保存作答草稿到服务端。

    手机端切后台、断网、浏览器被回收都可能丢答案，草稿落到服务端后，
    即便超时也能按已保存的内容自动交卷，不至于整场报废。
    """
    attempt = crud.get_open_attempt(db, exam_id, current_user.id)
    if attempt is None:
        # 没有进行中的会话时才需要新开一轮，开之前先确认还有次数，
        # 否则草稿接口会绕过 start 的次数检查，白白吃掉补考机会。
        exam = crud.get_exam(db, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="考试不存在")
        used, _ = crud.get_exam_progress(db, exam_id, current_user.id)
        if exam.retake_limit > 0 and used >= exam.retake_limit:
            raise HTTPException(status_code=403, detail=f"该考试每人最多参加 {exam.retake_limit} 次，您已达上限")
        attempt = crud.start_attempt(db, exam, current_user.id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="考试不存在")
    # 截止时间之后不再更新草稿：服务端保存的这份快照就是"截止时刻的作答"，
    # 超时后自动交卷按它判分，避免超时作答被算进成绩。
    if attempt.deadline_at and (utc_now() - attempt.deadline_at).total_seconds() > SUBMIT_GRACE_SECONDS:
        return {"ok": True, "expired": True, "deadline_ms": to_epoch_ms(attempt.deadline_at)}
    answers = payload.get("answers")
    if isinstance(answers, (dict, list)):
        answers = json.dumps(answers, ensure_ascii=False)
    attempt.draft = answers or ""
    db.commit()
    return {"ok": True, "deadline_ms": to_epoch_ms(attempt.deadline_at)}

@router.post("", response_model=schemas.ExamOut)
def create_exam(exam_in: schemas.ExamCreate, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    try:
        exam = crud.create_exam(db, exam_in, current_user.id)
    except (ValueError, paper_lib.RuleError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": exam.id,
        "title": exam.title,
        "duration": exam.duration,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "pass_score": exam.pass_score,
        "single_score": exam.single_score,
        "fill_score": exam.fill_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "random_mode": bool(exam.random_mode),
        "random_rules": exam.random_rules or "[]",
        "total_score": exam.total_score,
        "created_at": exam.created_at,
        "created_by": exam.created_by,
        "question_count": len(exam.questions),
        "participant_count": len(exam.records),
    }

@router.put("/{exam_id}")
def update_exam(exam_id: int, exam_in: schemas.ExamUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    try:
        exam = crud.update_exam(db, exam_id, exam_in)
    except (ValueError, paper_lib.RuleError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
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
        "fill_score": exam.fill_score,
        "multiple_score": exam.multiple_score,
        "judgment_score": exam.judgment_score,
        "random_mode": bool(exam.random_mode),
        "random_rules": exam.random_rules or "[]",
        "total_score": exam.total_score,
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
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    # 服务端为准核算考试用时：次数上限 + 本次作答的截止时间
    used, _ = crud.get_exam_progress(db, exam_id, current_user.id)
    if exam.retake_limit > 0 and used >= exam.retake_limit:
        raise HTTPException(status_code=403, detail=f"该考试每人最多参加 {exam.retake_limit} 次，您已达上限")
    attempt = crud.get_open_attempt(db, exam_id, current_user.id)
    if attempt is None:
        attempt = crud.start_attempt(db, exam, current_user.id)
    # 超时后不再接受新的作答内容：按服务端已保存的草稿自动交卷，
    # 这样既保证考生已答的内容不丢，也不会让超时的人继续作答。
    # 一道题都没答也照样记一条 0 分成绩，这一轮就算用掉了。
    if crud.is_attempt_expired(attempt):
        record = crud.finalize_expired_attempt(db, exam, current_user.id, attempt=attempt)
        if record is None:
            # 已被并发请求结算过，返回已有的那条成绩
            record = crud.get_latest_record(db, exam_id, current_user.id)
        if record is None:
            raise HTTPException(status_code=403, detail="考试时间已到，本次提交无效")
        return record
    record, claimed = crud.submit_attempt(db, exam, current_user.id, record_in.answers, attempt)
    if claimed:
        return record
    # 会话已被其它请求结算（并发提交或超时自动交卷），返回已有的成绩而不是报错
    latest = crud.get_latest_record(db, exam_id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=409, detail="本次提交未能生效，请重试")
    return latest

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
    """获取最近的考试提交记录（用于通知）

    原来逐条 r.user / r.exam 是懒加载，一次请求要打 11 条 SQL。
    管理端每 5 秒轮询一次这个接口，11 条就等于每 5 秒 11 个数据库往返，
    远端库上很容易堆成雪崩。这里改成一次 JOIN 取完。
    """
    from ..models import Exam, ExamRecord, User

    rows = (
        db.query(ExamRecord, User, Exam)
        .outerjoin(User, ExamRecord.user_id == User.id)
        .outerjoin(Exam, ExamRecord.exam_id == Exam.id)
        .order_by(ExamRecord.submitted_at.desc())
        .limit(10)
        .all()
    )
    result = []
    for r, user, exam in rows:
        if user:
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "user_name": user.name,
                "employee_id": user.employee_id,
                "exam_id": r.exam_id,
                "exam_title": exam.title if exam else "",
                "score": r.score,
                "total_score": r.total_score,
                "percent": round(r.score / r.total_score * 100, 1) if r.total_score > 0 else 0,
                "submitted_at": r.submitted_at,
            })
    return result


@router.get("/{exam_id}/export")
def export_exam_records(exam_id: int, db: Session = Depends(get_db),
                        _=Depends(require_admin)):
    """导出普通考试成绩 Excel（总成绩表 / 答题明细 / 统计表）"""
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    buf = crud.export_exam_excel(db, exam_id)
    if not buf:
        raise HTTPException(status_code=404, detail="导出失败")
    filename = f"{exam.title}_成绩表.xlsx"
    quoted = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )

@record_router.get("/{record_id}/review")
def get_record_review(record_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """返回某条已交卷记录的逐题解析。

    只允许记录本人或管理员访问。正确答案不放进考试接口，
    避免未交卷考生通过开发者工具提前拿到答案。
    """
    from .. import models

    record = db.query(models.ExamRecord).filter(models.ExamRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权查看该考试记录")

    exam = crud.get_exam(db, record.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    try:
        submitted_answers = json.loads(record.answers or "{}")
    except (TypeError, ValueError):
        submitted_answers = {}
    if not isinstance(submitted_answers, dict):
        submitted_answers = {}

    score_map = {
        "single": exam.single_score or 10,
        "multiple": exam.multiple_score or 20,
        "judgment": exam.judgment_score or 5,
        "fill": exam.fill_score or 10,
    }
    questions = []
    for q in crud.get_record_questions(db, record):
        user_answer = str(submitted_answers.get(str(q.id), submitted_answers.get(q.id, "")) or "")
        is_correct = crud._exam_answer_correct(q, user_answer)
        qd = schemas.QuestionOut.model_validate(q).model_dump()
        question_score = score_map.get(q.type, 10)
        qd.update({
            "score": question_score,
            "earned_score": question_score if is_correct else 0,
            "user_answer": user_answer,
            "correct_answer": q.answer or "",
            "is_correct": is_correct,
        })
        questions.append(qd)

    return {
        "record": {
            "id": record.id,
            "exam_id": record.exam_id,
            "user_id": record.user_id,
            "score": record.score,
            "total_score": record.total_score,
            "submitted_at": record.submitted_at,
        },
        "exam": {
            "id": exam.id,
            "title": exam.title,
            "pass_score": exam.pass_score,
        },
        "submitted_answers": submitted_answers,
        "questions": questions,
    }


@record_router.get("/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from ..models import ExamRecord
    r = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if r.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权查看该考试记录")
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
