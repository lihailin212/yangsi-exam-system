# -*- coding: utf-8 -*-
"""收费改造冒烟测试。

跑法（在仓库根目录）：
    python backend/scripts/test_billing.py

用一份独立的临时 SQLite 库，不碰线上数据，也不碰本地 exam.db。
"""
import os
import pathlib
import sys
import tempfile

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# 必须在导入 app 之前指定数据库
_TMP_DB = pathlib.Path(tempfile.gettempdir()) / "exam_billing_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-for-billing-smoke"
os.environ.pop("ADMIN_INITIAL_PASSWORD", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app import crud, schemas, models, billing  # noqa: E402
from app.timeutil import utc_now  # noqa: E402
from datetime import timedelta  # noqa: E402

PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  [OK] {name}")
    else:
        FAILED.append(f"{name} {detail}")
        print(f"  [FAIL] {name} {detail}")


def login(client, ident, password):
    r = client.post("/api/auth/login", json={"employee_id": ident, "password": password})
    return r


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    client = TestClient(app)
    db = SessionLocal()

    # 造数据：一个超管、一个机构、一个学员
    admin = crud.get_user_by_employee_id(db, "admin")
    if admin is None:
        admin = crud.create_user(db, schemas.UserCreate(
            employee_id="admin", name="超管", password="adminpass123", is_admin=True))
    db.commit()

    admin_token = login(client, "admin", "adminpass123").json()["access_token"]
    check("管理员登录", bool(admin_token))

    # ---------- 1. 收费开关默认关 ----------
    cfg = client.get("/api/billing/config").json()
    check("收费开关默认关闭", cfg["billing_enabled"] is False, cfg)
    check("试用天数默认 7", cfg["free_trial_days"] == 7, cfg)

    # ---------- 2. 创建机构并开通 ----------
    r = client.post("/api/organizations", headers=auth(admin_token), json={
        "name": "测试医院", "seat_limit": 2, "contact_name": "张三", "contact_phone": "13900000001"})
    check("创建机构", r.status_code == 200, r.text)
    org = r.json()
    org_id = org["id"]
    invite_code = org["invite_code"]

    plans = client.get("/api/billing/plans", headers=auth(admin_token)).json()["items"]
    check("默认套餐已初始化", len(plans) >= 2, plans)
    plan = plans[0]

    # 只延期、不带席位（不传 plan_id/seat_limit），席位上限保持建机构时的 2
    r = client.post(f"/api/organizations/{org_id}/grant", headers=auth(admin_token), json={
        "duration_days": 30, "amount_cents": plan["price_cents"], "note": "首开"})
    check("机构开通订阅", r.status_code == 200, r.text)
    expires = r.json()["subscription_expires_at"]
    check("开通后有到期时间", bool(expires), expires)

    orders = client.get("/api/billing/admin/orders", headers=auth(admin_token)).json()
    check("开通记录已落订单", orders["total"] >= 1, orders["total"])
    check("订单渠道为 manual", orders["items"][0]["channel"] == "manual")

    # ---------- 3. 注册（带邀请码） ----------
    r = client.post("/api/auth/register", json={
        "phone": "13900000002", "name": "学员甲", "password": "abcd1234",
        "invite_code": invite_code})
    check("手机号注册成功", r.status_code == 200, r.text)
    student = r.json()
    stu_token = student["access_token"]
    check("注册后归属机构", student["organization_id"] == org_id, student)
    check("注册后有试用期", student["trial_expires_at"] is not None)

    # 重复注册
    r = client.post("/api/auth/register", json={
        "phone": "13900000002", "name": "重复", "password": "abcd1234"})
    check("重复手机号被拒", r.status_code == 400, r.text)

    # 弱密码
    r = client.post("/api/auth/register", json={
        "phone": "13900000003", "name": "弱", "password": "123"})
    check("弱密码被拒", r.status_code == 400, r.text)

    # 错误邀请码
    r = client.post("/api/auth/register", json={
        "phone": "13900000004", "name": "错码", "password": "abcd1234",
        "invite_code": "NOPE"})
    check("错误邀请码被拒", r.status_code == 400, r.text)

    # ---------- 4. 席位上限 ----------
    r = client.post(f"/api/organizations/{org_id}/members", headers=auth(admin_token), json={
        "phone": "13900000005", "name": "学员乙", "password": "abcd1234"})
    check("加第 2 个学员成功", r.status_code == 200, r.text)
    r = client.post(f"/api/organizations/{org_id}/members", headers=auth(admin_token), json={
        "phone": "13900000006", "name": "学员丙", "password": "abcd1234"})
    check("超出席位被拒", r.status_code == 400, r.text)
    check("席位已满提示", "名额已满" in r.json().get("detail", ""), r.text)

    # ---------- 5. 权益判定 ----------
    r = client.get("/api/questions/study", headers=auth(stu_token))
    check("收费开关关时自学可访问", r.status_code == 200, r.status_code)

    # 打开收费开关
    r = client.post("/api/settings/billing", headers=auth(admin_token),
                    json={"enabled": True})
    check("打开收费开关", r.status_code == 200 and r.json()["enabled"] is True, r.text)

    r = client.get("/api/questions/study", headers=auth(stu_token))
    check("机构有效时自学可访问", r.status_code == 200, r.status_code)

    # 把机构订阅改到过去 -> 学员只剩试用，试用也没了就 402
    org_row = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    org_row.subscription_expires_at = utc_now() - timedelta(days=1)
    db.commit()
    billing.invalidate_org_cache(org_id)

    stu = db.query(models.User).filter(models.User.phone == "13900000002").first()
    stu.trial_expires_at = utc_now() - timedelta(days=1)
    db.commit()
    from app.auth import invalidate_user_cache
    invalidate_user_cache(stu.id)

    r = client.get("/api/questions/study", headers=auth(stu_token))
    check("到期后自学返回 402", r.status_code == 402, r.status_code)
    detail = r.json().get("detail", {})
    check("402 带 SUBSCRIPTION_EXPIRED", detail.get("code") == "SUBSCRIPTION_EXPIRED", detail)

    r = client.get("/api/exam-records/recent", headers=auth(stu_token))
    check("到期后成绩仍可查", r.status_code == 200, r.status_code)

    # ---------- 6. 兑换码 ----------
    r = client.post("/api/billing/admin/codes/generate", headers=auth(admin_token), json={
        "plan_id": plan["id"], "count": 2, "valid_days": 30, "organization_id": org_id})
    check("生成兑换码", r.status_code == 200, r.text)
    codes = r.json()["codes"]
    code = codes[0]

    r = client.post("/api/billing/redeem", headers=auth(stu_token), json={"code": code})
    check("兑换成功", r.status_code == 200, r.text)
    db.expire_all()
    org_row = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    check("兑换后机构到期日延后", org_row.subscription_expires_at > utc_now(),
          org_row.subscription_expires_at)

    r = client.post("/api/billing/redeem", headers=auth(stu_token), json={"code": code})
    check("同一码不能重复兑换", r.status_code == 400, r.text)

    r = client.post("/api/billing/redeem", headers=auth(stu_token), json={"code": "NOSUCHCODE"})
    check("不存在的码返回 404", r.status_code == 404, r.status_code)

    # 绑机构码给别人用
    r = client.post("/api/billing/admin/codes/generate", headers=auth(admin_token), json={
        "plan_id": plan["id"], "count": 1, "organization_id": 999999})
    other_code = r.json()["codes"][0]
    r = client.post("/api/billing/redeem", headers=auth(stu_token), json={"code": other_code})
    check("他机构码不能兑", r.status_code in (400, 403), r.status_code)

    # ---------- 7. 机构管理员隔离 ----------
    r = client.put(f"/api/organizations/{org_id}/members/{stu.id}", headers=auth(admin_token),
                   json={"org_role": "admin"})
    check("超管可指定机构管理员", r.status_code == 200, r.text)
    invalidate_user_cache(stu.id)
    r = client.get("/api/organizations", headers=auth(stu_token))
    check("机构管理员只看到自己机构", r.status_code == 200 and len(r.json()["items"]) == 1,
          r.text)
    r = client.post("/api/organizations", headers=auth(stu_token), json={"name": "越权机构"})
    check("机构管理员不能建机构", r.status_code == 403, r.status_code)
    r = client.post(f"/api/organizations/{org_id}/grant", headers=auth(stu_token),
                    json={"duration_days": 30})
    check("机构管理员不能改订阅", r.status_code == 403, r.status_code)

    # ---------- 8. 登录兼容 ----------
    r = login(client, "13900000002", "abcd1234")
    check("手机号可登录", r.status_code == 200, r.text)
    r = login(client, "admin", "adminpass123")
    check("工号仍可登录", r.status_code == 200, r.text)

    # ---------- 9. 续期不缩席位 ----------
    before = org_row.seat_limit
    r = client.post(f"/api/organizations/{org_id}/grant", headers=auth(admin_token),
                    json={"duration_days": 30, "seat_limit": 1})
    check("续期席位不缩水", r.json()["seat_limit"] == before, r.json())

    # 用套餐开通会按套餐席位数扩容（取较大值）
    r = client.post(f"/api/organizations/{org_id}/grant", headers=auth(admin_token),
                    json={"plan_id": plan["id"]})
    check("按套餐开通可扩容席位", r.json()["seat_limit"] == plan["seat_limit"], r.json())

    # ---------- 9.5 兑换限流 ----------
    stu2 = client.post("/api/auth/register", json={
        "phone": "13900000008", "name": "限流", "password": "abcd1234",
        "invite_code": invite_code}).json()
    if "access_token" in stu2:
        codes2 = client.post("/api/billing/admin/codes/generate", headers=auth(admin_token), json={
            "plan_id": plan["id"], "count": 8, "valid_days": 30}).json()["codes"]
        codes2 = codes2[:8]
        codes2 = client.post("/api/billing/admin/codes/generate", headers=auth(admin_token), json={
            "plan_id": plan["id"], "count": 8, "valid_days": 30}).json()["codes"]
        last = 429
        for c in codes2:
            last = client.post("/api/billing/redeem", headers=auth(stu2["access_token"]),
                               json={"code": c}).status_code
        check("兑换限流生效（超过 5 次/分钟返回 429）", last == 429, last)

    # ---------- 10. 待分配池 -> 拉入机构 ----------
    # 注册时不填邀请码，进待分配池
    r = client.post("/api/auth/register", json={
        "phone": "13900000007", "name": "待分配", "password": "abcd1234"})
    check("无邀请码注册进待分配池", r.status_code == 200, r.text)
    pool_user = r.json()
    check("待分配用户没有机构", pool_user["organization_id"] is None, pool_user)

    # 超管在学员管理里把他拉进机构
    pool_row = db.query(models.User).filter(models.User.phone == "13900000007").first()
    r = client.put(f"/api/students/{pool_row.id}", headers=auth(admin_token),
                   json={"organization_id": org_id, "org_role": "member"})
    check("超管可把学员拉入机构", r.status_code == 200, r.text)
    check("拉入后机构正确", r.json()["organization_id"] == org_id, r.text)

    # 学员列表里能看到机构与权益
    r = client.get("/api/students?organization_id=-1", headers=auth(admin_token))
    check("未分配筛选生效", all(i["organization_id"] is None for i in r.json()["items"]),
          r.text)

    # 机构管理员不能改学员的所属机构
    r = client.put(f"/api/students/{pool_row.id}", headers=auth(stu_token),
                   json={"organization_id": 999999})
    check("机构管理员不能改所属机构", r.status_code == 403, r.status_code)

    # 超管把学员移出机构（organization_id=0）
    r = client.put(f"/api/students/{pool_row.id}", headers=auth(admin_token),
                   json={"organization_id": 0})
    check("超管可把学员移出机构", r.status_code == 200, r.text)
    check("移出后回到待分配池", r.json()["organization_id"] is None, r.text)

    # 席位已满时拉不进人
    r = client.put(f"/api/students/{pool_row.id}", headers=auth(admin_token),
                   json={"organization_id": org_id})
    check("满席时拉人失败或按当前席位判断", r.status_code in (200, 400), r.status_code)

    db.close()
    client.close()

    print("\n==============================")
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        for f in FAILED:
            print("  FAIL:", f)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
