# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import crud, schemas, models
from ..auth import get_current_user, require_admin, require_org_admin
from .. import billing as billing_lib

router = APIRouter(prefix="/api/students", tags=["students"])


def _student_row(db, u):
    """列表里附上机构与权益信息，前端直接显示。"""
    row = schemas.UserOut.model_validate(u).model_dump()
    org = None
    if u.organization_id:
        org = db.query(models.Organization).filter(
            models.Organization.id == u.organization_id).first()
    row["organization_name"] = org.name if org else ""
    ent = billing_lib.compute_entitlement(
        u, billing_lib.get_org_snapshot(db, u.organization_id),
        billing_lib.get_billing_settings(db))
    row["entitlement_active"] = bool(ent.get("active"))
    row["entitlement_reason"] = ent.get("reason", "")
    row["org_expires_at"] = ent.get("org_expires_at")
    row["days_left"] = ent.get("days_left")
    return row


@router.get("")
def list_students(skip: int = 0, limit: int = 20, search: str = "", dept: str = "",
                  organization_id: int = 0,
                  db: Session = Depends(get_db), current_user=Depends(require_org_admin)):
    """学员列表。

    机构管理员只能看到自己机构的学员；organization_id=-1 表示看「未分配池」。
    机构过滤和排序都在 SQL 里做，翻页不会漏人也不会乱序。
    """
    if current_user.is_admin:
        users, total = crud.get_users(db, skip=skip, limit=limit, search=search, dept=dept,
                                     organization_id=organization_id)
    else:
        # 机构管理员：只看自己机构。require_org_admin 已保证他挂了机构。
        users, total = crud.get_users(db, skip=skip, limit=limit, search=search, dept=dept,
                                     organization_id=current_user.organization_id or -1)
    return {"items": [_student_row(db, u) for u in users], "total": total}


def _check_phone_free(db, phone: str, exclude_user_id: int = 0):
    """手机号在系统里是登录标识之一（短信登录/按手机号找账号），
    不能两个人共用同一个号，否则登录会串号。"""
    if not phone:
        return
    owner = crud.get_user_by_phone(db, phone)
    if owner and owner.id != exclude_user_id:
        raise HTTPException(status_code=400, detail=f"手机号已被「{owner.name}」占用")


@router.post("", response_model=schemas.UserOut)
def create_student(user_in: schemas.UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if crud.get_user_by_employee_id(db, user_in.employee_id):
        raise HTTPException(status_code=400, detail="工号已存在")
    _check_phone_free(db, user_in.phone)
    if user_in.organization_id:
        org = db.query(models.Organization).filter(
            models.Organization.id == user_in.organization_id).first()
        if org is None:
            raise HTTPException(status_code=400, detail="机构不存在")
        used = billing_lib.count_seats(db, org.id)
        if used >= (org.seat_limit or 0):
            raise HTTPException(
                status_code=400,
                detail=f"机构名额已满（{used}/{org.seat_limit or 0}），请先扩容")
    return crud.create_user(db, user_in)


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_student(user_id: int, user_in: schemas.UserUpdate, db: Session = Depends(get_db),
                   current_user=Depends(require_org_admin)):
    """改学员。

    - 超管：可以改姓名/科室/密码/启停，也可以把学员拉进某个机构（待分配池 → 机构）
    - 机构管理员：只能改自己机构的学员，且**不能**改所属机构和机构角色
    """
    if not current_user.is_admin:
        # 机构管理员只能动自己机构的人
        target = db.query(models.User).filter(models.User.id == user_id).first()
        if target is None or target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user_in.organization_id is not None or user_in.org_role is not None:
            raise HTTPException(status_code=403, detail="不能修改学员的所属机构或机构角色")

    # 拉进机构：校验机构存在 + 席位没满（organization_id=0 表示移出机构）
    if user_in.organization_id:
        org = db.query(models.Organization).filter(
            models.Organization.id == user_in.organization_id).first()
        if org is None:
            raise HTTPException(status_code=400, detail="机构不存在")
        target = db.query(models.User).filter(models.User.id == user_id).first()
        if target is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        # 已经在别的机构里，换机构等于多占一个名额
        moving = target.organization_id != org.id
        if moving and target.is_active:
            used = billing_lib.count_seats(db, org.id)
            if used >= (org.seat_limit or 0):
                raise HTTPException(
                    status_code=400,
                    detail=f"机构名额已满（{used}/{org.seat_limit or 0}），请先扩容")

    if user_in.org_role is not None and user_in.org_role not in ("", "member", "admin"):
        raise HTTPException(status_code=400, detail="机构角色只能是 member 或 admin")

    if user_in.phone is not None:
        _check_phone_free(db, user_in.phone, exclude_user_id=user_id)

    user = crud.update_user(db, user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_in.organization_id:
        billing_lib.invalidate_org_cache(user_in.organization_id)
    return user


@router.delete("/{user_id}")
def delete_student(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    crud.delete_user(db, user_id)
    return {"ok": True}


@router.get("/{user_id}/records")
def get_student_records(user_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    records = crud.get_user_records(db, user_id)
    return [schemas.ExamRecordOut.model_validate(r) for r in records]
