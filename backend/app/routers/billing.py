# -*- coding: utf-8 -*-
"""收费相关接口。

用户侧 /api/billing/*   套餐、我的权益、兑换码、下单
管理侧 /api/billing/admin/*   套餐管理、订单、兑换码
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import billing as billing_lib, models, schemas
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..payments import PaymentNotConfigured, get_provider
from ..timeutil import utc_now

router = APIRouter(prefix="/api/billing", tags=["billing"])
admin_router = APIRouter(prefix="/api/billing/admin", tags=["billing-admin"])


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    """前端启动时拉一次：收费开关、支付通道、短信是否可用、试用天数。"""
    settings = billing_lib.get_billing_settings(db)
    return {
        "billing_enabled": bool(settings.get("enabled")),
        "payment_channel": settings.get("payment_channel", "manual"),
        "sms_enabled": bool(settings.get("sms_enabled")) and _sms_enabled(),
        "free_trial_days": int(settings.get("free_trial_days", 7) or 0),
        "contact_wechat": settings.get("contact_wechat", ""),
    }


def _sms_enabled() -> bool:
    from .. import sms
    return sms.sms_configured()


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """启用的机构套餐，供订阅页展示。"""
    plans = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.is_active.is_(True)
    ).order_by(models.SubscriptionPlan.sort_order, models.SubscriptionPlan.id).all()
    return {"items": [schemas.PlanOut.model_validate(p).model_dump() for p in plans]}


@router.get("/me")
def my_entitlement(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """我的权益：试用期、所属机构、机构到期日、席位用量、当前能不能用。"""
    ent = billing_lib.get_entitlement(db, current_user)
    org = ent.get("organization") or {}
    return {
        "active": ent.get("active", False),
        "reason": ent.get("reason", ""),
        "days_left": ent.get("days_left"),
        "trial_expires_at": ent.get("trial_expires_at"),
        # 工号账号的手机号和登录账号是两回事：
        # 考生用工号登录，但「我的订阅」要显示本人真实手机号
        "phone": getattr(current_user, "phone", "") or "",
        "employee_id": getattr(current_user, "employee_id", "") or "",
        "name": getattr(current_user, "name", "") or "",
        "organization": {
            "id": org.get("id"),
            "name": org.get("name", ""),
            "invite_code": org.get("invite_code", ""),
            "seat_limit": ent.get("seat_limit", 0),
            "seat_used": ent.get("seat_used", 0),
            "subscription_expires_at": ent.get("org_expires_at"),
        } if org else None,
    }


@router.post("/redeem")
def redeem(req: schemas.RedeemRequest, db: Session = Depends(get_db),
           current_user=Depends(get_current_user)):
    """用兑换码给自己所在机构续期。"""
    try:
        billing_lib.check_redeem_rate(current_user.id)
    except billing_lib.RateLimited as e:
        raise HTTPException(status_code=429, detail=str(e))
    try:
        order, org = billing_lib.redeem_code(db, current_user, req.code)
    except LookupError:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    except PermissionError:
        raise HTTPException(status_code=403, detail="该兑换码仅限指定机构使用")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "ok": True,
        "message": f"兑换成功，{org.name}的订阅已延长",
        "order_no": order.order_no,
        "organization_id": org.id,
        "subscription_expires_at": org.subscription_expires_at,
    }


@router.post("/orders")
def create_order(req: schemas.CreateOrderRequest, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """创建待支付订单。

    当前 payment_channel=manual（人工开通），在线支付没开时直接 501，
    前端提示用户联系管理员。以后接了微信支付，这里会返回扫码链接。
    """
    settings = billing_lib.get_billing_settings(db)
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == req.plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")

    org_id = req.organization_id or current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=400, detail="您还没有加入任何机构，请先用机构邀请码注册")

    provider = get_provider(settings.get("payment_channel", "manual"))
    order = models.PaymentOrder(
        order_no=f"ORD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                 f"{__import__('secrets').randbelow(9000) + 1000}",
        organization_id=org_id,
        user_id=current_user.id,
        plan_id=plan.id,
        plan_name=plan.name,
        seat_limit=plan.seat_limit,
        duration_days=plan.duration_days,
        amount_cents=plan.price_cents,
        channel=provider.name,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    try:
        pay_info = provider.create_order(order)
    except PaymentNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    return {"order_no": order.order_no, "amount_cents": order.amount_cents, **pay_info}


# ---------------- 管理侧 ----------------

@admin_router.get("/plans")
def admin_list_plans(db: Session = Depends(get_db), _=Depends(require_admin)):
    plans = db.query(models.SubscriptionPlan).order_by(
        models.SubscriptionPlan.sort_order, models.SubscriptionPlan.id).all()
    return {"items": [schemas.PlanOut.model_validate(p).model_dump() for p in plans]}


@admin_router.post("/plans", response_model=schemas.PlanOut)
def admin_create_plan(payload: schemas.PlanIn, db: Session = Depends(get_db),
                      _=Depends(require_admin)):
    if db.query(models.SubscriptionPlan).filter(
            models.SubscriptionPlan.code == payload.code).first():
        raise HTTPException(status_code=400, detail="套餐编码已存在")
    plan = models.SubscriptionPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@admin_router.put("/plans/{plan_id}", response_model=schemas.PlanOut)
def admin_update_plan(plan_id: int, payload: schemas.PlanIn,
                      db: Session = Depends(get_db), _=Depends(require_admin)):
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    dup = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.code == payload.code,
        models.SubscriptionPlan.id != plan_id).first()
    if dup:
        raise HTTPException(status_code=400, detail="套餐编码已存在")
    for k, v in payload.model_dump().items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


@admin_router.delete("/plans/{plan_id}")
def admin_delete_plan(plan_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")
    db.query(models.RedemptionCode).filter(models.RedemptionCode.plan_id == plan_id).update(
        {"plan_id": None})
    db.delete(plan)
    db.commit()
    return {"ok": True}


@admin_router.get("/orders")
def admin_list_orders(skip: int = 0, limit: int = 50, organization_id: int = 0,
                      channel: str = "", status: str = "",
                      db: Session = Depends(get_db), _=Depends(require_admin)):
    q = db.query(models.PaymentOrder)
    if organization_id:
        q = q.filter(models.PaymentOrder.organization_id == organization_id)
    if channel:
        q = q.filter(models.PaymentOrder.channel == channel)
    if status:
        q = q.filter(models.PaymentOrder.status == status)
    total = q.count()
    rows = q.order_by(models.PaymentOrder.id.desc()).offset(skip).limit(limit).all()

    items = []
    for r in rows:
        item = schemas.OrderOut.model_validate(r).model_dump()
        org = db.query(models.Organization).filter(
            models.Organization.id == r.organization_id).first() if r.organization_id else None
        item["organization_name"] = org.name if org else ""
        items.append(item)
    return {"items": items, "total": total}


@admin_router.get("/codes")
def admin_list_codes(skip: int = 0, limit: int = 50, status: str = "",
                     organization_id: int = 0, batch_no: str = "",
                     db: Session = Depends(get_db), _=Depends(require_admin)):
    q = db.query(models.RedemptionCode)
    if status:
        q = q.filter(models.RedemptionCode.status == status)
    if organization_id:
        q = q.filter(models.RedemptionCode.organization_id == organization_id)
    if batch_no:
        q = q.filter(models.RedemptionCode.batch_no == batch_no)
    total = q.count()
    rows = q.order_by(models.RedemptionCode.id.desc()).offset(skip).limit(limit).all()
    return {"items": [schemas.CodeOut.model_validate(r).model_dump() for r in rows],
            "total": total}


@admin_router.post("/codes/generate")
def admin_generate_codes(req: schemas.CodeGenerateRequest, db: Session = Depends(get_db),
                          current_user=Depends(require_admin)):
    """批量生成兑换码。"""
    count = max(1, min(int(req.count or 1), 500))
    plan = None
    if req.plan_id:
        plan = db.query(models.SubscriptionPlan).filter(
            models.SubscriptionPlan.id == req.plan_id).first()
        if plan is None:
            raise HTTPException(status_code=404, detail="套餐不存在")

    duration_days = req.duration_days if req.duration_days is not None else (plan.duration_days if plan else 0)
    seat_limit = req.seat_limit if req.seat_limit is not None else (plan.seat_limit if plan else 0)
    if not duration_days:
        raise HTTPException(status_code=400, detail="请选择套餐或填写有效期天数")

    batch_no = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    expires_at = utc_now() + timedelta(days=int(req.valid_days)) if req.valid_days else None

    codes = []
    for _ in range(count):
        code = billing_lib.generate_redemption_code()
        row = models.RedemptionCode(
            code=code,
            organization_id=req.organization_id,
            plan_id=req.plan_id,
            plan_name=plan.name if plan else "自定义套餐",
            duration_days=int(duration_days),
            seat_limit=int(seat_limit or 0),
            amount_cents=int(req.amount_cents or 0),
            batch_no=batch_no,
            created_by=current_user.id,
            expires_at=expires_at,
            status="unused",
        )
        db.add(row)
        codes.append(code)
    db.commit()
    return {"ok": True, "batch_no": batch_no, "codes": codes,
            "expires_at": expires_at, "total": len(codes)}


@admin_router.post("/codes/{code_id}/void")
def admin_void_code(code_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(models.RedemptionCode).filter(models.RedemptionCode.id == code_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if row.status == "used":
        raise HTTPException(status_code=400, detail="兑换码已被使用，无法作废")
    row.status = "void"
    db.commit()
    return {"ok": True}


@admin_router.post("/codes/redeem-for")
def admin_redeem_for(req: schemas.AdminRedeemRequest, db: Session = Depends(get_db),
                     current_user=Depends(require_admin)):
    """管理员代某个机构兑换（学员不在机构里也能开通）。"""
    code = (req.code or "").strip().upper()
    row = db.query(models.RedemptionCode).filter(models.RedemptionCode.code == code).first()
    if row is None:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if row.status == "used":
        raise HTTPException(status_code=400, detail="兑换码已被使用")
    if row.status == "void":
        raise HTTPException(status_code=400, detail="兑换码已作废")
    if row.expires_at and row.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="兑换码已过期")

    org = db.query(models.Organization).filter(
        models.Organization.id == req.organization_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="机构不存在")
    if row.organization_id and row.organization_id != org.id:
        raise HTTPException(status_code=400, detail="该兑换码仅限指定机构使用")

    plan = None
    if row.plan_id:
        plan = db.query(models.SubscriptionPlan).filter(
            models.SubscriptionPlan.id == row.plan_id).first()
    duration_days = row.duration_days or (plan.duration_days if plan else 0)
    if not duration_days:
        raise HTTPException(status_code=400, detail="兑换码未配置有效期")
    seat_limit = row.seat_limit or (plan.seat_limit if plan else None)

    order = billing_lib.activate_organization_subscription(
        db, org,
        plan_id=row.plan_id,
        duration_days=duration_days,
        seat_limit=seat_limit,
        amount_cents=row.amount_cents,
        channel="redemption_code",
        operator_id=current_user.id,
        user_id=current_user.id,
        note=f"管理员代兑换 {row.code}",
    )
    row.status = "used"
    row.used_by_org_id = org.id
    row.used_at = utc_now()
    db.commit()
    return {"ok": True, "order_no": order.order_no,
            "subscription_expires_at": org.subscription_expires_at}
