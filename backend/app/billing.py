# -*- coding: utf-8 -*-
"""收费（订阅）核心逻辑。

付费单位是「机构」：机构买席位名额 + 有效期，机构订阅到期则院内学员失效。
个人只有试用期（trial_expires_at），不单独购买。

对外暴露三个东西：
- get_entitlement()   算某个用户当前能不能用
- activate_organization_subscription()  唯一的开通入口（后台/兑换码/未来微信回调共用）
- redeem_code()       兑换码兑换
"""
from datetime import datetime, timedelta
import secrets
import string
import time

from sqlalchemy.orm import Session

from . import models
from .timeutil import utc_now

# 系统设置里 billing 这一项的默认值。enabled 默认关：改造上线后老用户照常用，
# 等超管把机构套餐配好再一键打开拦截。
DEFAULT_BILLING_SETTINGS = {
    "enabled": False,
    "free_trial_days": 7,
    "payment_channel": "manual",
    "sms_enabled": False,
    "contact_wechat": "",
}

# 数据库在远端（Neon），一次 SELECT 200ms 起步，而权益校验几乎每个请求都要做。
# 设置和机构信息都用短 TTL 缓存一份快照，改动时主动作废。
CACHE_TTL_SECONDS = 30.0
_settings_cache = {"expires_at": 0.0, "data": None}
_org_cache = {}  # org_id -> (expires_at, snapshot dict)

# 邀请码用的字符集：去掉容易看错的 0/O/1/I
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_invite_code(length: int = 8) -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(length))


def generate_redemption_code(prefix: str = "") -> str:
    body = "".join(secrets.choice(string.ascii_uppercase + string.digits)
                   for _ in range(12))
    return f"{prefix}{body}" if prefix else body


def invalidate_settings_cache():
    _settings_cache["expires_at"] = 0.0
    _settings_cache["data"] = None


def invalidate_org_cache(org_id=None):
    if org_id is None:
        _org_cache.clear()
    else:
        _org_cache.pop(org_id, None)


def get_billing_settings(db: Session = None, force: bool = False) -> dict:
    """读系统设置 billing（JSON）。没配就用默认值。"""
    now = time.time()
    if not force and _settings_cache["data"] is not None and _settings_cache["expires_at"] > now:
        return _settings_cache["data"]

    data = dict(DEFAULT_BILLING_SETTINGS)
    if db is not None:
        try:
            row = db.query(models.SystemSetting).filter_by(key="billing").first()
            if row is not None and row.value:
                import json
                loaded = json.loads(row.value)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            # 设置读失败时退回默认值，绝不因为收费开关读不出来就把全站锁死
            pass

    _settings_cache["data"] = data
    _settings_cache["expires_at"] = now + CACHE_TTL_SECONDS
    return data


def save_billing_settings(db: Session, data: dict):
    """保存 billing 设置（超管在系统设置里改）。"""
    import json
    merged = get_billing_settings(db, force=True)
    merged.update({k: v for k, v in (data or {}).items() if k in DEFAULT_BILLING_SETTINGS})
    row = db.query(models.SystemSetting).filter_by(key="billing").first()
    if row is None:
        db.add(models.SystemSetting(key="billing", value=json.dumps(merged, ensure_ascii=False)))
    else:
        row.value = json.dumps(merged, ensure_ascii=False)
    db.commit()
    invalidate_settings_cache()
    return merged


def get_org_snapshot(db: Session, org_id: int):
    """取机构快照（带缓存）。返回 None 表示机构不存在。"""
    if not org_id:
        return None
    now = time.time()
    item = _org_cache.get(org_id)
    if item is not None and item[0] > now:
        return item[1]

    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if org is None:
        return None
    snapshot = {
        "id": org.id,
        "name": org.name,
        "invite_code": org.invite_code,
        "seat_limit": org.seat_limit or 0,
        "subscription_expires_at": org.subscription_expires_at,
        "subscription_plan_code": org.subscription_plan_code or "",
        "is_active": bool(org.is_active),
    }
    _org_cache[org_id] = (now + CACHE_TTL_SECONDS, snapshot)
    return snapshot


def count_seats(db: Session, org_id: int) -> int:
    """已占用席位数：该机构下启用状态的学员数。"""
    if not org_id:
        return 0
    return db.query(models.User).filter(
        models.User.organization_id == org_id,
        models.User.is_active.is_(True),
    ).count()


def _days_left(expires_at) -> int:
    if not expires_at:
        return 0
    delta = expires_at - utc_now()
    return max(0, int(delta.total_seconds() // 86400))


def compute_entitlement(user, org_snapshot, settings) -> dict:
    """判定权益。纯计算，不查库。

    顺序：全局开关关 → 超管 → 试用期 → 机构订阅。
    """
    trial_expires_at = getattr(user, "trial_expires_at", None)
    org_expires_at = None
    if org_snapshot:
        org_expires_at = org_snapshot.get("subscription_expires_at")

    base = {
        "trial_expires_at": trial_expires_at,
        "organization": org_snapshot,
        "org_expires_at": org_expires_at,
        "seat_limit": (org_snapshot or {}).get("seat_limit", 0),
        "seat_used": None,
    }

    if not settings.get("enabled", False):
        base.update(active=True, reason="billing_disabled", days_left=None)
        return base

    if getattr(user, "is_admin", False):
        base.update(active=True, reason="admin", days_left=None)
        return base

    if trial_expires_at and trial_expires_at > utc_now():
        base.update(active=True, reason="trial", days_left=_days_left(trial_expires_at))
        return base

    if org_snapshot and org_snapshot.get("is_active") and org_expires_at and org_expires_at > utc_now():
        base.update(active=True, reason="organization", days_left=_days_left(org_expires_at))
        return base

    reason = "no_subscription"
    if org_snapshot and org_expires_at and org_expires_at <= utc_now():
        reason = "organization_expired"
    base.update(active=False, reason=reason, days_left=_days_left(org_expires_at) if org_expires_at else 0)
    return base


def get_entitlement(db: Session, user) -> dict:
    """当前登录用户的完整权益信息（含席位用量）。"""
    settings = get_billing_settings(db)
    org_snapshot = get_org_snapshot(db, getattr(user, "organization_id", None))
    result = compute_entitlement(user, org_snapshot, settings)
    if org_snapshot:
        result["seat_used"] = count_seats(db, org_snapshot["id"])
    else:
        result["seat_used"] = 0
    return result


def activate_organization_subscription(
    db: Session,
    org,
    plan_id=None,
    duration_days=None,
    seat_limit=None,
    amount_cents=0,
    channel="manual",
    operator_id=None,
    user_id=None,
    note="",
):
    """给机构开通/续期订阅。**所有开通渠道的唯一入口**。

    续期在当前到期日上叠加（不浪费已购时长）；席位数取 max，续期不会把席位缩回去。
    """
    plan = None
    if plan_id:
        plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
        if plan is None:
            raise ValueError("套餐不存在")

    days = duration_days
    if days is None:
        days = plan.duration_days if plan else 0
    days = int(days or 0)
    if days <= 0:
        raise ValueError("有效期天数必须大于 0")

    seats = seat_limit
    if seats is None:
        seats = plan.seat_limit if plan else 0
    seats = int(seats or 0)

    now = utc_now()
    base = org.subscription_expires_at or now
    if base < now:
        base = now
    new_expiry = base + timedelta(days=days)

    org.subscription_expires_at = new_expiry
    org.seat_limit = max(org.seat_limit or 0, seats)
    if plan is not None:
        org.subscription_plan_code = plan.code

    order = models.PaymentOrder(
        order_no=f"MAN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(9000) + 1000}",
        organization_id=org.id,
        user_id=user_id,
        plan_id=plan.id if plan is not None else None,
        plan_name=plan.name if plan is not None else "自定义套餐",
        seat_limit=seats,
        duration_days=days,
        amount_cents=int(amount_cents or 0),
        channel=channel,
        status="paid",
        operator_id=operator_id,
        paid_at=now,
        note=note or "",
    )
    db.add(order)
    db.commit()
    db.refresh(org)
    invalidate_org_cache(org.id)
    return order


# 兑换接口限流：同一用户 5 次/分钟。
# 服务端多实例部署时每个实例各算各的，挡不住恶意刷，但能挡住手滑连点。
REDEEM_RATE_LIMIT = 5
REDEEM_RATE_WINDOW = 60.0
_redeem_hits = {}


class RateLimited(Exception):
    """操作太频繁。"""


def check_redeem_rate(user_id) -> None:
    """兑换码兑换限流。同一个用户 60 秒内最多 5 次。"""
    now = time.time()
    hits = [t for t in _redeem_hits.get(user_id, []) if now - t < REDEEM_RATE_WINDOW]
    if len(hits) >= REDEEM_RATE_LIMIT:
        _redeem_hits[user_id] = hits
        raise RateLimited(f"操作太频繁，{REDEEM_RATE_WINDOW:.0f} 秒内最多兑换 {REDEEM_RATE_LIMIT} 次")
    hits.append(now)
    _redeem_hits[user_id] = hits


def redeem_code(db: Session, user, code: str):
    """学员用兑换码给自己所在机构续期。

    规则：一次性、限机构（码上绑了机构就只能该机构学员用）、可设过期。
    """
    code = (code or "").strip().upper()
    if not code:
        raise ValueError("请输入兑换码")

    row = db.query(models.RedemptionCode).filter(models.RedemptionCode.code == code).first()
    if row is None:
        raise LookupError("兑换码不存在")
    if row.status == "used":
        raise ValueError("兑换码已被使用")
    if row.status == "void":
        raise ValueError("兑换码已作废")
    if row.expires_at and row.expires_at <= utc_now():
        raise ValueError("兑换码已过期")

    user_org_id = getattr(user, "organization_id", None)
    if row.organization_id and row.organization_id != user_org_id:
        raise PermissionError("该兑换码仅限指定机构使用")
    if not user_org_id:
        raise ValueError("您还没有加入任何机构，请先用机构邀请码注册或联系管理员")

    org = db.query(models.Organization).filter(models.Organization.id == user_org_id).first()
    if org is None:
        raise ValueError("所属机构不存在，请联系管理员")

    plan = None
    if row.plan_id:
        plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == row.plan_id).first()

    duration_days = row.duration_days or (plan.duration_days if plan else 0)
    seat_limit = row.seat_limit or (plan.seat_limit if plan else None)
    if not duration_days:
        raise ValueError("兑换码未配置有效期，请联系管理员")

    order = activate_organization_subscription(
        db, org,
        plan_id=row.plan_id,
        duration_days=duration_days,
        seat_limit=seat_limit,
        amount_cents=row.amount_cents,
        channel="redemption_code",
        operator_id=user.id,
        user_id=user.id,
        note=f"兑换码 {row.code}",
    )

    row.status = "used"
    row.used_by_org_id = org.id
    row.used_at = utc_now()
    db.commit()
    invalidate_org_cache(org.id)
    return order, org


def ensure_default_plans(db: Session):
    """首次启动时写入两条默认机构套餐（管理员可随时改价改名）。"""
    if db.query(models.SubscriptionPlan).count() > 0:
        return
    db.add_all([
        models.SubscriptionPlan(
            code="org_basic", name="机构基础版", seat_limit=20,
            duration_days=30, price_cents=39900,
            description="20 个席位，有效期 1 个月", sort_order=1),
        models.SubscriptionPlan(
            code="org_standard", name="机构标准版", seat_limit=50,
            duration_days=365, price_cents=299900,
            description="50 个席位，有效期 1 年", sort_order=2),
    ])
    db.commit()
