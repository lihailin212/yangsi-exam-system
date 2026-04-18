from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from ..database import get_db
from .. import crud, schemas
from ..auth import get_current_user, require_admin, create_access_token
from ..config import FRONTEND_BASE_URL

router = APIRouter(prefix="/api/distributions", tags=["distributions"])
invite_router = APIRouter(prefix="/api/invite", tags=["invite"])
exam_login_router = APIRouter(prefix="/api/exam-login", tags=["exam-login"])
exam_student_router = APIRouter(prefix="/api/distributions/exam-students", tags=["exam-students"])


@router.get("/frontend-url")
def get_frontend_url(exam_id: int, request: Request):
    """获取考试登录页的完整 URL（用于生成分发链接/二维码）"""
    base = _get_frontend_base_url(request)
    return {"url": f"{base}/#/exam-login/{exam_id}"}


def _get_frontend_base_url(request: Request) -> str:
    """获取前端访问地址，优先使用配置，其次使用请求头推断"""
    # 配置值优先级最高
    configured = FRONTEND_BASE_URL
    if configured and configured != "http://localhost:5173":
        return configured
    # 开发环境回退：从请求头推断
    forwarded = request.headers.get("x-forwarded-host", "")
    if forwarded:
        origin = request.headers.get("origin", "")
        if origin:
            return origin
        return f"http://{forwarded}" if not forwarded.startswith("http") else forwarded
    origin = request.headers.get("origin", "")
    if origin:
        return origin
    host = request.headers.get("host", "localhost:5173")
    return f"http://{host}" if not host.startswith("http") else host


@router.get("")
def list_distributions(exam_id: int, request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    dists = crud.get_distributions(db, exam_id)
    base = _get_frontend_base_url(request)
    result = []
    for d in dists:
        result.append({
            "id": d.id,
            "exam_id": d.exam_id,
            "exam_title": d.exam.title if d.exam else "",
            "user_id": d.user_id,
            "user_name": d.user.name if d.user else "",
            "employee_id": d.user.employee_id if d.user else "",
            "invite_code": d.invite_code,
            "created_at": d.created_at,
            "invite_url": f"{base}#/invite/{d.invite_code}",
        })
    return result


@router.post("")
def create_distributions(d_in: schemas.DistributionCreate, request: Request, db: Session = Depends(get_db), _=Depends(require_admin)):
    exam = crud.get_exam(db, d_in.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    dists = crud.create_distributions(db, d_in.exam_id, d_in.user_ids)
    base = _get_frontend_base_url(request)
    result = []
    for d in dists:
        result.append({
            "id": d.id,
            "exam_id": d.exam_id,
            "exam_title": d.exam.title if d.exam else "",
            "user_id": d.user_id,
            "user_name": d.user.name if d.user else "",
            "employee_id": d.user.employee_id if d.user else "",
            "invite_code": d.invite_code,
            "created_at": d.created_at,
            "invite_url": f"{base}#/invite/{d.invite_code}",
        })
    return result


@router.delete("/{distribution_id}")
def delete_distribution(distribution_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    crud.delete_distribution(db, distribution_id)
    return {"ok": True}


@invite_router.get("/{code}")
def get_invite_info(code: str, db: Session = Depends(get_db)):
    """获取邀请考试信息，无需认证"""
    dist = crud.get_distribution_by_code(db, code)
    if not dist:
        raise HTTPException(status_code=404, detail="邀请码无效或已失效")
    exam = dist.exam
    now = datetime.utcnow()
    if exam.start_time and exam.start_time > now:
        status = "未开始"
    elif exam.end_time and exam.end_time < now:
        status = "已结束"
    elif exam.start_time:
        status = "进行中"
    else:
        status = "可参加"
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "duration": exam.duration,
        "pass_score": exam.pass_score,
        "exam_status": status,
    }


@invite_router.post("/login", response_model=schemas.InviteLoginResponse)
def invite_login(req: schemas.InviteLoginRequest, db: Session = Depends(get_db)):
    """邀请页登录，验证邀请码和用户凭证"""
    user, dist = crud.verify_distribution_user(db, req.invite_code, req.employee_id, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="邀请码无效或您没有此考试的访问权限")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    # 生成专用的 access_token，payload中包含exam_id
    token = create_access_token({"sub": str(user.id), "exam_id": dist.exam_id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "is_admin": user.is_admin,
        "exam_id": dist.exam_id,
    }


@exam_login_router.get("/{exam_id}")
def get_exam_login_info(exam_id: int, db: Session = Depends(get_db)):
    """获取考试信息（无需认证），用于考生登录页"""
    exam = crud.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    now = datetime.utcnow()
    if exam.start_time and exam.start_time > now:
        status = "未开始"
    elif exam.end_time and exam.end_time < now:
        status = "已结束"
    elif exam.start_time:
        status = "进行中"
    else:
        status = "可参加"
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "duration": exam.duration,
        "pass_score": exam.pass_score,
        "retake_limit": exam.retake_limit,
        "exam_status": status,
    }


@exam_login_router.post("")
def exam_login(req: schemas.ExamLoginRequest, db: Session = Depends(get_db)):
    """考生登录（无需认证）：验证工号+密码，有效则进入考试"""
    user = crud.get_user_by_employee_id(db, req.employee_id)
    if not user:
        raise HTTPException(status_code=401, detail="工号不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    # 验证密码
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    if not pwd_ctx.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")
    # 检查补考次数限制
    exam = crud.get_exam(db, req.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    from .. import models
    taken_count = db.query(models.ExamRecord).filter(
        models.ExamRecord.user_id == user.id,
        models.ExamRecord.exam_id == req.exam_id
    ).count()
    if exam.retake_limit > 0 and taken_count >= exam.retake_limit:
        raise HTTPException(status_code=403, detail=f"该考试每人最多参加 {exam.retake_limit} 次，您已达上限")
    # 检查是否在允许参加考试的名单中（如果名单非空）
    allowed = db.query(models.ExamDistribution).filter(
        models.ExamDistribution.exam_id == req.exam_id
    ).all()
    if len(allowed) > 0:
        allowed_user_ids = {d.user_id for d in allowed}
        if user.id not in allowed_user_ids:
            raise HTTPException(status_code=403, detail="您不用参加此次考试，谢谢！")
    # 生成 token，payload中包含exam_id
    token = create_access_token({"sub": str(user.id), "exam_id": req.exam_id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "is_admin": user.is_admin,
        "exam_id": req.exam_id,
    }


# 获取某考试的允许考生列表
@exam_student_router.get("")
def get_exam_students(exam_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    from .. import models
    dists = db.query(models.ExamDistribution).filter(
        models.ExamDistribution.exam_id == exam_id
    ).all()
    result = []
    for d in dists:
        result.append({
            "user_id": d.user_id,
            "user_name": d.user.name if d.user else "",
            "employee_id": d.user.employee_id if d.user else "",
        })
    return result


# 设置某考试的允许考生列表（覆盖式更新）
class ExamStudentSet(BaseModel):
    exam_id: int
    user_ids: List[int]


@exam_student_router.post("")
def set_exam_students(data: ExamStudentSet, db: Session = Depends(get_db), _=Depends(require_admin)):
    from .. import models
    import random, string

    def gen_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # 删除旧的
    db.query(models.ExamDistribution).filter(
        models.ExamDistribution.exam_id == data.exam_id
    ).delete(synchronize_session=False)

    # 添加新的
    for uid in data.user_ids:
        code = gen_code()
        dist = models.ExamDistribution(
            exam_id=data.exam_id,
            user_id=uid,
            invite_code=code,
        )
        db.add(dist)
    db.commit()
    return {"ok": True, "count": len(data.user_ids)}
