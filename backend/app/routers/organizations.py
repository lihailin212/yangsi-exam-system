# -*- coding: utf-8 -*-
"""机构（付费单位）管理接口。

数据隔离规则：
- 超管（is_admin）：能看全部机构。
- 机构管理员（org_role='admin'）：只能看自己那一机构，所有操作都锁在自己的 organization_id 上。
"""
import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import billing as billing_lib, crud, models, schemas
from ..auth import (get_current_user, hash_password, require_admin,
                    require_org_admin, invalidate_user_cache)
from ..database import get_db
from ..timeutil import utc_now

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _get_org_or_404(db: Session, org_id: int):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="机构不存在")
    return org


def _ensure_access(current_user, org_id: int):
    """超管随便看；机构管理员只能看自己的机构。看别人的机构一律 404，不泄露存在性。"""
    if current_user.is_admin:
        return
    if current_user.org_role != "admin" or current_user.organization_id != org_id:
        raise HTTPException(status_code=404, detail="机构不存在")
    return


def _parse_expiry(raw: str):
    """解析到期日。支持 YYYY-MM-DD 或 ISO 日期时间。"""
    from datetime import datetime as _dt
    text = raw.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return _dt.strptime(text, fmt)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="到期日格式不正确，应为 YYYY-MM-DD")


def _seat_guard(db: Session, org, adding: int = 1):
    used = billing_lib.count_seats(db, org.id)
    if used + adding > (org.seat_limit or 0):
        raise HTTPException(
            status_code=400,
            detail=f"机构名额已满（{used}/{org.seat_limit or 0}），请先联系管理员扩容")


def _org_out(db: Session, org):
    data = schemas.OrganizationOut.model_validate(org).model_dump()
    data["seat_used"] = billing_lib.count_seats(db, org.id)
    return data


@router.get("")
def list_organizations(db: Session = Depends(get_db), current_user=Depends(require_org_admin)):
    q = db.query(models.Organization)
    if not current_user.is_admin:
        q = q.filter(models.Organization.id == current_user.organization_id)
    rows = q.order_by(models.Organization.id).all()
    return {"items": [_org_out(db, o) for o in rows]}


@router.post("", response_model=schemas.OrganizationOut)
def create_organization(payload: schemas.OrganizationCreate, db: Session = Depends(get_db),
                         current_user=Depends(require_admin)):
    if db.query(models.Organization).filter(models.Organization.name == payload.name).first():
        raise HTTPException(status_code=400, detail="机构名称已存在")
    org = models.Organization(
        name=payload.name,
        invite_code=billing_lib.generate_invite_code(),
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        seat_limit=int(payload.seat_limit or 0),
        is_active=True,
        created_by=current_user.id,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    billing_lib.invalidate_org_cache(org.id)

    # 建机构时可以直接带上套餐，一并完成首次开通
    if payload.plan_id or payload.duration_days:
        try:
            billing_lib.activate_organization_subscription(
                db, org,
                plan_id=payload.plan_id,
                duration_days=payload.duration_days,
                seat_limit=payload.seat_limit,
                amount_cents=payload.amount_cents,
                channel="manual",
                operator_id=current_user.id,
                user_id=current_user.id,
                note=payload.note or "创建机构时开通",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        db.refresh(org)
    return _org_out(db, org)


@router.put("/{org_id}", response_model=schemas.OrganizationOut)
def update_organization(org_id: int, payload: schemas.OrganizationUpdate,
                        db: Session = Depends(get_db), current_user=Depends(require_org_admin)):
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)
    if not current_user.is_admin:
        # 机构管理员只能改自己的联系方式，改不了名字、席位、启停
        if payload.contact_name is not None:
            org.contact_name = payload.contact_name
        if payload.contact_phone is not None:
            org.contact_phone = payload.contact_phone
        db.commit()
        db.refresh(org)
        billing_lib.invalidate_org_cache(org.id)
        return _org_out(db, org)

    if payload.name is not None:
        dup = db.query(models.Organization).filter(
            models.Organization.name == payload.name,
            models.Organization.id != org_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="机构名称已存在")
        org.name = payload.name
    if payload.contact_name is not None:
        org.contact_name = payload.contact_name
    if payload.contact_phone is not None:
        org.contact_phone = payload.contact_phone
    if payload.seat_limit is not None:
        org.seat_limit = int(payload.seat_limit)
    if payload.is_active is not None:
        org.is_active = bool(payload.is_active)
    if payload.subscription_expires_at is not None:
        raw = str(payload.subscription_expires_at).strip()
        org.subscription_expires_at = None if raw in ("", "null", "none") else _parse_expiry(raw)
    db.commit()
    db.refresh(org)
    billing_lib.invalidate_org_cache(org.id)
    return _org_out(db, org)


@router.post("/{org_id}/grant")
def grant_subscription(org_id: int, payload: schemas.GrantRequest,
                       db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """超管给机构开通/续期订阅。"""
    org = _get_org_or_404(db, org_id)
    try:
        order = billing_lib.activate_organization_subscription(
            db, org,
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
            seat_limit=payload.seat_limit,
            amount_cents=payload.amount_cents,
            channel="manual",
            operator_id=current_user.id,
            user_id=current_user.id,
            note=payload.note or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(org)
    return {
        "ok": True,
        "order_no": order.order_no,
        "subscription_expires_at": org.subscription_expires_at,
        "seat_limit": org.seat_limit,
    }


@router.post("/{org_id}/invite-code/rotate")
def rotate_invite_code(org_id: int, db: Session = Depends(get_db),
                       current_user=Depends(require_org_admin)):
    """重置机构邀请码（旧码立即失效）。"""
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)
    org.invite_code = billing_lib.generate_invite_code()
    db.commit()
    db.refresh(org)
    billing_lib.invalidate_org_cache(org.id)
    return {"ok": True, "invite_code": org.invite_code}


@router.get("/{org_id}/members")
def list_members(org_id: int, db: Session = Depends(get_db),
                 current_user=Depends(require_org_admin)):
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)
    rows = db.query(models.User).filter(
        models.User.organization_id == org_id
    ).order_by(models.User.id).all()
    return {
        "items": [schemas.OrgMemberOut.model_validate(u).model_dump() for u in rows],
        "seat_used": billing_lib.count_seats(db, org_id),
        "seat_limit": org.seat_limit or 0,
        "organization": _org_out(db, org),
    }


@router.post("/{org_id}/members", response_model=schemas.OrgMemberOut)
def add_member(org_id: int, payload: schemas.OrgMemberCreate, db: Session = Depends(get_db),
               current_user=Depends(require_org_admin)):
    """给机构加学员（机构管理员可用）。"""
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)
    phone = (payload.phone or "").strip()
    if not phone.isdigit() or len(phone) != 11:
        raise HTTPException(status_code=400, detail="请填写正确的 11 位手机号")
    if db.query(models.User).filter(
            (models.User.phone == phone) | (models.User.employee_id == phone)).first():
        raise HTTPException(status_code=400, detail="该手机号已注册")
    _seat_guard(db, org, adding=1)

    password = payload.password or ("".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(10)))
    user = models.User(
        employee_id=phone,
        name=payload.name or ("学员" + phone[-4:]),
        phone=phone,
        password_hash=hash_password(password),
        dept=payload.dept or "",
        is_active=True,
        must_change_password=False,
        registered_via="admin",
        organization_id=org.id,
        org_role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    result = schemas.OrgMemberOut.model_validate(user).model_dump()
    result["initial_password"] = password
    return result


@router.put("/{org_id}/members/{user_id}", response_model=schemas.OrgMemberOut)
def update_member(org_id: int, user_id: int, payload: schemas.OrgMemberUpdate,
                  db: Session = Depends(get_db), current_user=Depends(require_org_admin)):
    """改学员信息。**不能**改所属机构、不能改超管权限。"""
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or user.organization_id != org_id:
        raise HTTPException(status_code=404, detail="学员不存在")

    if payload.name is not None:
        user.name = payload.name
    if payload.dept is not None:
        user.dept = payload.dept
    if payload.password:
        user.password_hash = hash_password(payload.password)
        user.must_change_password = False
    if payload.is_active is not None:
        if not current_user.is_admin and user.org_role == "admin":
            raise HTTPException(status_code=403, detail="不能停用机构管理员")
        user.is_active = bool(payload.is_active)
    if payload.org_role is not None:
        # 只有超管能指定机构管理员
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="只有超级管理员能设置机构管理员")
        if payload.org_role not in ("", "member", "admin"):
            raise HTTPException(status_code=400, detail="机构角色只能是 member 或 admin")
        user.org_role = payload.org_role
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


@router.get("/{org_id}/stats")
def org_stats(org_id: int, db: Session = Depends(get_db),
              current_user=Depends(require_org_admin)):
    """本机构概况：成员数、可用席位、成绩统计。"""
    org = _get_org_or_404(db, org_id)
    _ensure_access(current_user, org_id)

    member_ids = [u.id for u in db.query(models.User).filter(
        models.User.organization_id == org_id).all()]
    if member_ids:
        records = db.query(models.ExamRecord).filter(
            models.ExamRecord.user_id.in_(member_ids)).all()
    else:
        records = []
    total = len(records)
    avg = round(sum(r.score or 0 for r in records) / total, 1) if total else 0
    return {
        "organization": _org_out(db, org),
        "member_count": len(member_ids),
        "seat_used": billing_lib.count_seats(db, org_id),
        "seat_limit": org.seat_limit or 0,
        "record_count": total,
        "average_score": avg,
        "subscription_expires_at": org.subscription_expires_at,
    }
