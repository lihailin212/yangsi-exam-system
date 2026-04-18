import json
import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models, schemas
from .auth import hash_password, verify_password

# ---- User ----
def get_user_by_employee_id(db: Session, employee_id: str):
    return db.query(models.User).filter(models.User.employee_id == employee_id).first()

def get_users(db: Session, skip=0, limit=100, search="", dept=""):
    q = db.query(models.User)
    if search:
        q = q.filter(
            (models.User.name.contains(search)) | (models.User.employee_id.contains(search))
        )
    if dept:
        q = q.filter(models.User.dept == dept)
    return q.offset(skip).limit(limit).all(), q.count()

def create_user(db: Session, user_in: schemas.UserCreate):
    user = models.User(
        employee_id=user_in.employee_id,
        name=user_in.name,
        password_hash=hash_password(user_in.password),
        dept=user_in.dept,
        role=user_in.role,
        is_admin=user_in.is_admin,
        is_active=user_in.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user_id: int, user_in: schemas.UserUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    if user_in.name is not None:
        user.name = user_in.name
    if user_in.dept is not None:
        user.dept = user_in.dept
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.password is not None:
        user.password_hash = hash_password(user_in.password)
    if user_in.is_admin is not None:
        user.is_admin = user_in.is_admin
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return user

# ---- Question ----
def get_questions(db: Session, skip=0, limit=100, q_type="", search="", category=""):
    q = db.query(models.Question)
    # 过滤掉系统分类占位题目（内容以[SYSTEM_CATEGORY]开头）
    q = q.filter(~models.Question.content.startswith("<p>[SYSTEM_CATEGORY]"))
    if q_type:
        q = q.filter(models.Question.type == q_type)
    if search:
        q = q.filter(models.Question.content.contains(search))
    if category:
        # 检查是否为父级分类（查询所有以此开头的子分类）
        if category.endswith('/'):
            # 精确匹配分类，如 "形态学/"
            q = q.filter(models.Question.category.like(f"{category}%"))
        else:
            # 精确匹配或以 "父分类/" 开头的子分类
            q = q.filter(
                (models.Question.category == category) |
                (models.Question.category.like(f"{category}/%"))
            )
    total = q.count()
    return q.order_by(models.Question.id.desc()).offset(skip).limit(limit).all(), total

def get_question(db: Session, question_id: int):
    return db.query(models.Question).filter(models.Question.id == question_id).first()

def create_question(db: Session, q_in: schemas.QuestionCreate):
    q = models.Question(**q_in.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return q

def update_question(db: Session, question_id: int, q_in: schemas.QuestionUpdate):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        return None
    for k, v in q_in.model_dump().items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q

def delete_question(db: Session, question_id: int):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if q:
        # 防止删除系统分类占位题目
        if q.content.startswith("<p>[SYSTEM_CATEGORY]"):
            return None
        db.delete(q)
        db.commit()
    return q

def bulk_create_questions(db: Session, questions: list):
    objs = [models.Question(**q) for q in questions]
    db.add_all(objs)
    db.commit()
    return len(objs)


def get_all_categories(db: Session):
    """获取所有分类及其题目数量"""
    result = db.query(
        models.Question.category,
        func.count(models.Question.id).label('count')
    ).group_by(models.Question.category).all()
    return [{"name": r.category, "count": r.count} for r in result if r.category]


def rename_category(db: Session, old_name: str, new_name: str):
    """重命名分类"""
    # 更新所有使用该分类的题目（包括系统题目）
    db.query(models.Question).filter(
        models.Question.category == old_name
    ).update({"category": new_name})
    db.commit()
    # 如果新名称为空（删除分类），删除该分类的系统占位题目
    if not new_name:
        db.query(models.Question).filter(
            models.Question.category == "",
            models.Question.content.startswith("<p>[SYSTEM_CATEGORY]")
        ).delete(synchronize_session=False)
        db.commit()


def create_category(db: Session, category_name: str):
    """创建新分类（通过创建一个系统占位题目）"""
    # 检查分类是否已存在
    existing = db.query(models.Question).filter(
        models.Question.category == category_name
    ).first()
    if existing:
        return False
    # 创建一个系统占位题目来代表这个分类（不会被普通界面显示）
    q = models.Question(
        type="single",
        content=f"<p>[SYSTEM_CATEGORY]{category_name}</p>",
        options='{"A": "系统分类"}',
        answer="A",
        analysis="系统分类占位题目，不在题目列表中显示",
        category=category_name
    )
    db.add(q)
    db.commit()
    return True


# ---- Exam ----
def get_exams(db: Session, skip=0, limit=100):
    exams = db.query(models.Exam).order_by(models.Exam.id.desc()).offset(skip).limit(limit).all()
    total = db.query(models.Exam).count()
    return exams, total

def get_exam(db: Session, exam_id: int):
    return db.query(models.Exam).filter(models.Exam.id == exam_id).first()

def _calc_total_score(exam: models.Exam) -> float:
    """计算考试总分"""
    score_map = {
        "single": exam.single_score or 10,
        "multiple": exam.multiple_score or 20,
        "judgment": exam.judgment_score or 5,
    }
    return sum(score_map.get(q.type, 10) for q in exam.questions)

def create_exam(db: Session, exam_in: schemas.ExamCreate, creator_id: int):
    data = exam_in.model_dump(exclude={"question_ids"})
    exam = models.Exam(**data, created_by=creator_id)
    if exam_in.question_ids:
        qs = db.query(models.Question).filter(models.Question.id.in_(exam_in.question_ids)).all()
        exam.questions = qs
    # 计算并存储总分
    exam.total_score = _calc_total_score(exam)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam

def update_exam(db: Session, exam_id: int, exam_in: schemas.ExamUpdate):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        return None
    data = exam_in.model_dump(exclude_none=True, exclude={"question_ids"})
    for k, v in data.items():
        setattr(exam, k, v)
    if exam_in.question_ids is not None:
        qs = db.query(models.Question).filter(models.Question.id.in_(exam_in.question_ids)).all()
        exam.questions = qs
    # 重新计算总分
    exam.total_score = _calc_total_score(exam)
    db.commit()
    db.refresh(exam)
    return exam

def delete_exam(db: Session, exam_id: int):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if exam:
        db.delete(exam)
        db.commit()
    return exam

# ---- ExamRecord ----
def submit_exam(db: Session, record_in: schemas.ExamRecordCreate, user_id: int):
    exam = db.query(models.Exam).filter(models.Exam.id == record_in.exam_id).first()
    if not exam:
        return None
    answers = json.loads(record_in.answers)
    earned_score = 0.0

    # 根据题型映射分值
    score_map = {
        "single": exam.single_score,
        "multiple": exam.multiple_score,
        "judgment": exam.judgment_score
    }

    for q in exam.questions:
        question_score = score_map.get(q.type, 10)  # 默认10分
        user_ans = answers.get(str(q.id), "")
        if q.type == "multiple":
            correct = set(q.answer.split(","))
            given = set(user_ans.split(",")) if user_ans else set()
            if correct == given:
                earned_score += question_score
        else:
            if str(user_ans).strip() == str(q.answer).strip():
                earned_score += question_score
    record = models.ExamRecord(
        exam_id=record_in.exam_id,
        user_id=user_id,
        answers=record_in.answers,
        score=earned_score,
        total_score=exam.total_score,  # 使用存储的总分
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def get_user_records(db: Session, user_id: int):
    return db.query(models.ExamRecord).filter(models.ExamRecord.user_id == user_id).all()

def get_exam_records(db: Session, exam_id: int):
    return db.query(models.ExamRecord).filter(models.ExamRecord.exam_id == exam_id).all()

# ---- Statistics ----
def get_statistics(db: Session):
    total_users = db.query(models.User).filter(models.User.is_admin == False).count()
    total_exams = db.query(models.Exam).count()
    records = db.query(models.ExamRecord).all()
    total_records = len(records)
    avg_score = 0.0
    pass_rate = 0.0
    if total_records > 0:
        scores = [r.score / r.total_score * 100 if r.total_score > 0 else 0 for r in records]
        avg_score = sum(scores) / len(scores)
        # 获取每个考试的及格线
        pass_count = 0
        for r in records:
            exam = db.query(models.Exam).filter(models.Exam.id == r.exam_id).first()
            if exam:
                pct = r.score / r.total_score * 100 if r.total_score > 0 else 0
                if pct >= exam.pass_score:
                    pass_count += 1
        pass_rate = pass_count / total_records * 100

    # 近7天趋势
    trend = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        count = db.query(models.ExamRecord).filter(
            func.date(models.ExamRecord.submitted_at) == day
        ).count()
        trend.append({"date": str(day), "count": count})

    # 分数分布
    score_dist = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "below60": 0}
    for r in records:
        pct = r.score / r.total_score * 100 if r.total_score > 0 else 0
        if pct >= 90:
            score_dist["90-100"] += 1
        elif pct >= 80:
            score_dist["80-89"] += 1
        elif pct >= 70:
            score_dist["70-79"] += 1
        elif pct >= 60:
            score_dist["60-69"] += 1
        else:
            score_dist["below60"] += 1

    return {
        "total_users": total_users,
        "total_exams": total_exams,
        "total_records": total_records,
        "avg_score": round(avg_score, 1),
        "pass_rate": round(pass_rate, 1),
        "trend": trend,
        "score_dist": score_dist,
    }

# ---- ExamDistribution ----
def _generate_invite_code(db: Session) -> str:
    """生成唯一的6位邀请码"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        exists = db.query(models.ExamDistribution).filter(
            models.ExamDistribution.invite_code == code
        ).first()
        if not exists:
            return code

def create_distributions(db: Session, exam_id: int, user_ids: list):
    """批量创建分发记录，同一考生参加同一考试共用一个邀请码"""
    records = []
    for user_id in user_ids:
        # 检查是否已存在该分发
        existing = db.query(models.ExamDistribution).filter(
            models.ExamDistribution.exam_id == exam_id,
            models.ExamDistribution.user_id == user_id
        ).first()
        if existing:
            records.append(existing)
            continue
        invite_code = _generate_invite_code(db)
        dist = models.ExamDistribution(
            exam_id=exam_id,
            user_id=user_id,
            invite_code=invite_code,
        )
        db.add(dist)
        records.append(dist)
    db.commit()
    for r in records:
        db.refresh(r)
    return records

def get_distributions(db: Session, exam_id: int):
    """获取某考试的所有分发记录"""
    return db.query(models.ExamDistribution).filter(
        models.ExamDistribution.exam_id == exam_id
    ).all()

def delete_distribution(db: Session, distribution_id: int):
    """删除分发记录"""
    dist = db.query(models.ExamDistribution).filter(
        models.ExamDistribution.id == distribution_id
    ).first()
    if dist:
        db.delete(dist)
        db.commit()
    return dist

def get_distribution_by_code(db: Session, code: str):
    """通过邀请码查询分发记录"""
    return db.query(models.ExamDistribution).filter(
        models.ExamDistribution.invite_code == code
    ).first()

def verify_distribution_user(db: Session, code: str, employee_id: str, password: str):
    """验证邀请码+用户凭证，返回 (user, distribution) 或 (None, None)"""
    dist = get_distribution_by_code(db, code)
    if not dist:
        return None, None
    user = get_user_by_employee_id(db, employee_id)
    if not user:
        return None, None
    if not verify_password(password, user.password_hash):
        return None, None
    # 检查该用户是否在此分发记录中
    if dist.user_id != user.id:
        return None, None
    return user, dist
