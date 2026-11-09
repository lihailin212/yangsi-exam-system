# -*- coding: utf-8 -*-
"""把检验科花名册录入「学员信息表」(users 表)。

数据来源：backend/scripts/lab_roster.csv（从纸质名单照片整理而来）。

规则：
  - 工号已存在 → **不重复建号**，只把缺失/不同的手机号补上
    （这就是「已经有的就不要再重复录入」）。
  - 工号不存在 → 新建账号：科室=检验科、职位=检验师、归属机构=<机构名>、
    初始密码见 INITIAL_PASSWORD。
  - 手机号如果已经被别人占用 → 跳过并报告，不覆盖他人资料。
  - 机构席位不够 → 停止新增（已存在的补录照常做）。

用法：
    cd backend && python scripts/import_lab_roster.py --dry-run     # 先看会发生什么
    cd backend && python scripts/import_lab_roster.py               # 真正写入
    cd backend && python scripts/import_lab_roster.py --csv ../scripts/lab_roster.csv
"""
import argparse
import csv
import pathlib

import bcrypt

from db import connect

DEFAULT_CSV = pathlib.Path(__file__).with_name("lab_roster.csv")
DEFAULT_ORG = "杨思医院检验科"
DEFAULT_DEPT = "检验科"
DEFAULT_ROLE = "检验师"
INITIAL_PASSWORD = "123456"   # 与现有检验科账号保持一致


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def read_roster(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            employee_id = (raw.get("工号") or "").strip()
            name = (raw.get("姓名") or "").strip()
            phone = (raw.get("手机号码") or "").strip()
            if not employee_id or not name:
                continue
            rows.append((employee_id, name, phone, (raw.get("备注") or "").strip()))
    return rows


def main():
    ap = argparse.ArgumentParser(description="录入检验科花名册到学员信息表")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="花名册 CSV 路径")
    ap.add_argument("--org", default=DEFAULT_ORG, help="归属机构名称")
    ap.add_argument("--dept", default=DEFAULT_DEPT, help="科室")
    ap.add_argument("--role", default=DEFAULT_ROLE, help="职位")
    ap.add_argument("--password", default=INITIAL_PASSWORD, help="新账号的初始密码")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发生的改动，不写库")
    args = ap.parse_args()

    roster = read_roster(args.csv)
    if not roster:
        raise SystemExit(f"花名册是空的：{args.csv}")

    conn = connect()
    created = updated = skipped = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, seat_limit FROM organizations WHERE name = %s", (args.org,))
            org = cur.fetchone()
            if not org:
                raise SystemExit(f"机构「{args.org}」不存在，先在后台创建或用 --org 指定现有机构")
            org_id, org_name, seat_limit = org

            for employee_id, name, phone, note in roster:
                cur.execute(
                    "SELECT id, name, phone FROM users WHERE employee_id = %s",
                    (employee_id,),
                )
                existing = cur.fetchone()

                if existing:
                    uid, old_name, old_phone = existing
                    if phone and phone != old_phone:
                        # 手机号被别人占用了就只报告，不抢
                        cur.execute("SELECT id, name FROM users WHERE phone = %s AND id <> %s",
                                    (phone, uid))
                        clash = cur.fetchone()
                        if clash:
                            print(f"[跳过] 工号 {employee_id} {name}：手机号 {phone} 已被「{clash[1]}」占用")
                            skipped += 1
                            continue
                        print(f"[补录] 工号 {employee_id} {name}：手机号 {old_phone or '(空)'} → {phone}")
                        if not args.dry_run:
                            cur.execute("UPDATE users SET phone = %s WHERE id = %s", (phone, uid))
                        updated += 1
                    else:
                        print(f"[跳过] 工号 {employee_id} {name}：已存在，不重复录入")
                        skipped += 1
                    continue

                # 新建
                if phone:
                    cur.execute("SELECT id, name FROM users WHERE phone = %s", (phone,))
                    clash = cur.fetchone()
                    if clash:
                        print(f"[跳过] 工号 {employee_id} {name}：手机号 {phone} 已被「{clash[1]}」占用")
                        skipped += 1
                        continue

                cur.execute(
                    "SELECT count(*) FROM users WHERE organization_id = %s AND is_active IS TRUE",
                    (org_id,),
                )
                used = cur.fetchone()[0]
                if used >= (seat_limit or 0):
                    raise SystemExit(
                        f"机构「{org_name}」席位已满（{used}/{seat_limit}），"
                        f"请先扩容再继续导入（工号 {employee_id} {name} 之后的人都没写入）"
                    )

                print(f"[新增] 工号 {employee_id} {name} {phone}"
                      + (f"  # {note}" if note else ""))
                if not args.dry_run:
                    cur.execute(
                        "INSERT INTO users (employee_id, name, password_hash, dept, role, phone, "
                        "is_admin, is_active, must_change_password, organization_id, org_role, "
                        "registered_via, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, FALSE, TRUE, FALSE, %s, 'member', "
                        "'admin', NOW())",
                        (employee_id, name, hash_password(args.password), args.dept, args.role,
                         phone, org_id),
                    )
                created += 1

        if not args.dry_run:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    tag = "[试运行]" if args.dry_run else "[完成]"
    print(f"\n{tag} 新增 {created} 人，补录手机号 {updated} 人，跳过 {skipped} 人，共 {len(roster)} 条")
    if created:
        print(f"新账号初始密码：{args.password}（学员首次登录后建议自行修改）")


if __name__ == "__main__":
    main()
