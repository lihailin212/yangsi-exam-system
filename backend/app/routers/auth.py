# -*- coding: utf-8 -*-
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import billing as billing_lib, crud, models, schemas
from ..auth import (create_access_token, get_current_db_user, hash_password,
                    invalidate_user_cache, verify_password)
from ..sms import SmsNotConfigured, generate_code, send_sms_code, sms_configured
from ..timeutil import utc_now

router = APIRouter(prefix="/api/auth", tags=["auth"])

PHONE_PATTERN = r"^1[3-9]\d{9}$"


def _valid_phone(phone: str) -> bool:
    import re
    return bool(re.match(PHONE_PATTERN, (phone or "").strip()))


def _token_response(user, db: Session):
    """签发 token 并带上机构/权益信息。"""
    token = create_access_token({"sub": str(user.id)})
    ent = billing_lib.get_entitlement(db, user)
    org = ent.get("organization") or {}
    return schemas.TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        is_admin=bool(user.is_admin),
        employee_id=user.employee_id,
        must_change_password=bool(getattr(user, "must_change_password", False)),
        organization_id=user.organization_id,
        organization_name=org.get("name", ""),
        org_role=getattr(user, "org_role", "") or "",
        trial_expires_at=getattr(user, "trial_expires_at", None),
        entitlement_active=bool(ent.get("active", True)),
    )


@router.post("/login", response_model=schemas.TokenResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    """登录。employee_id 可以是工号，也可以是手机号。"""
    user = crud.get_user_by_identifier(db, req.employee_id)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    return _token_response(user, db)


@router.post("/register", response_model=schemas.TokenResponse)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """手机号自助注册。

    - 手机号即账号（工号位也存手机号），密码至少 8 位
    - 注册即赠免费试用（free_trial_days 天）
    - 填了机构邀请码就自动归属该机构；没填的进待分配池，等机构管理员/超管拉入
    """
    phone = (req.phone or "").strip()
    if not _valid_phone(phone):
        raise HTTPException(status_code=400, detail="请输入正确的 11 位手机号")
    if not req.password or len(req.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")
    if crud.get_user_by_employee_id(db, phone) or crud.get_user_by_phone(db, phone):
        raise HTTPException(status_code=400, detail="该手机号已注册，请直接登录")

    settings = billing_lib.get_billing_settings(db)
    trial_days = int(settings.get("free_trial_days", 0) or 0)
    trial_expires_at = utc_now() + timedelta(days=trial_days) if trial_days > 0 else None

    org = None
    invite_code = (req.invite_code or "").strip().upper()
    if invite_code:
        org = db.query(models.Organization).filter(
            models.Organization.invite_code == invite_code).first()
        if org is None:
            raise HTTPException(status_code=400, detail="机构邀请码无效")
        if not org.is_active:
            raise HTTPException(status_code=400, detail="该机构已停用，请联系机构管理员")
        used = billing_lib.count_seats(db, org.id)
        if used >= (org.seat_limit or 0):
            raise HTTPException(status_code=400, detail=f"机构名额已满（{used}/{org.seat_limit or 0}），请联系机构管理员扩容")

    user = models.User(
        employee_id=phone,
        name=(req.name or "").strip() or ("学员" + phone[-4:]),
        phone=phone,
        password_hash=hash_password(req.password),
        is_active=True,
        is_admin=False,
        must_change_password=False,
        registered_via="self",
        organization_id=org.id if org is not None else None,
        org_role="member" if org is not None else "",
        trial_expires_at=trial_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user, db)


@router.get("/capabilities")
def capabilities(db: Session = Depends(get_db)):
    """前端启动时拉一次：短信登录是否可用、支付通道、收费开关、试用天数。"""
    settings = billing_lib.get_billing_settings(db)
    return {
        "sms_login": bool(settings.get("sms_enabled")) and sms_configured(),
        "payment_channel": settings.get("payment_channel", "manual"),
        "billing_enabled": bool(settings.get("enabled")),
        "free_trial_days": int(settings.get("free_trial_days", 7) or 0),
    }


@router.post("/sms/send")
def sms_send(req: schemas.SmsSendRequest, db: Session = Depends(get_db)):
    """发短信验证码。没配置短信服务商时返回 501，前端会隐藏这个入口。"""
    if not sms_configured():
        raise HTTPException(status_code=501, detail="短信登录即将开放")
    phone = (req.phone or "").strip()
    if not _valid_phone(phone):
        raise HTTPException(status_code=400, detail="请输入正确的 11 位手机号")

    now = utc_now()
    last = db.query(models.SmsCode).filter(
        models.SmsCode.phone == phone,
        models.SmsCode.purpose == "login",
    ).order_by(models.SmsCode.id.desc()).first()
    if last is not None and last.created_at and (now - last.created_at).total_seconds() < 60:
        raise HTTPException(status_code=429, detail="请 60 秒后再试")
    today_count = db.query(models.SmsCode).filter(
        models.SmsCode.phone == phone,
        models.SmsCode.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
    ).count()
    if today_count >= 10:
        raise HTTPException(status_code=429, detail="今日发送次数已达上限")

    code = generate_code()
    try:
        send_sms_code(phone, code)
    except SmsNotConfigured:
        raise HTTPException(status_code=501, detail="短信登录即将开放")
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="短信通道尚未接通")

    db.add(models.SmsCode(
        phone=phone, code=code, purpose="login",
        expires_at=now + timedelta(minutes=5), used=False, sent_count=today_count + 1,
    ))
    db.commit()
    return {"ok": True, "message": "验证码已发送"}


@router.post("/sms/login", response_model=schemas.TokenResponse)
def sms_login(req: schemas.SmsLoginRequest, db: Session = Depends(get_db)):
    """短信验证码登录（需先配置短信服务商）。"""
    if not sms_configured():
        raise HTTPException(status_code=501, detail="短信登录即将开放")
    phone = (req.phone or "").strip()
    code = (req.code or "").strip()
    if not _valid_phone(phone):
        raise HTTPException(status_code=400, detail="请输入正确的 11 位手机号")

    row = db.query(models.SmsCode).filter(
        models.SmsCode.phone == phone,
        models.SmsCode.purpose == "login",
        models.SmsCode.used.is_(False),
    ).order_by(models.SmsCode.id.desc()).first()
    if row is None or row.code != code:
        raise HTTPException(status_code=400, detail="验证码不正确")
    if row.expires_at and row.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="验证码已过期")

    user = crud.get_user_by_phone(db, phone)
    if user is None:
        raise HTTPException(status_code=400, detail="该手机号尚未注册")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    row.used = True
    db.commit()
    return _token_response(user, db)


@router.post("/change-password")
def change_password(req: schemas.ChangePasswordRequest,
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_db_user)):
    """修改自己的密码。

    初始密码（环境变量里定的或随机生成的）登录后必须走这里改一次，
    改完 must_change_password 置 False，其余接口才放行。
    """
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if req.new_password == req.old_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    current_user.password_hash = hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    db.refresh(current_user)
    # 缓存里的快照还带着旧密码和 must_change_password，必须立刻作废
    invalidate_user_cache(current_user.id)
    return {"ok": True, "message": "密码修改成功"}
