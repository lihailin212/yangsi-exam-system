# -*- coding: utf-8 -*-
"""一次性迁移脚本：把存量工号学员收进默认机构「杨思学」。

做三件事：
1. 创建默认机构（名称可改），席位上限默认 50，生成邀请码
2. 把所有还没有机构的老用户挂到该机构下，角色为普通学员
3. 保证 billing 设置存在（收费开关默认关闭，改造上线后老用户照常用）

幂等：重复执行不会重复建机构、不会把已分配的用户改回去。
用法：python backend/scripts/migrate_billing.py
"""
import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.db import connect, load_dotenv_local  # noqa: E402

DEFAULT_ORG_NAME = "杨思学"
DEFAULT_SEAT_LIMIT = 50


def ensure_schema():
    """先把新表和 users 的新列建出来，脚本才能独立跑。

    服务端的 main.py 也会做同样的事（幂等），这里重复一遍是为了让这个
    脚本在"还没部署新后端"的库上也能直接执行。
    """
    load_dotenv_local()
    from app.database import Base, engine  # noqa: E402
    from app import models  # noqa: F401,E402
    from sqlalchemy import text

    # 新表：organizations / subscription_plans / redemption_codes /
    # payment_orders / sms_codes
    Base.metadata.create_all(bind=engine)

    ddl = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS org_role VARCHAR(20) DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_expires_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS registered_via VARCHAR(20) DEFAULT 'admin'",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)",
        "CREATE INDEX IF NOT EXISTS ix_users_organization ON users (organization_id)",
    ]
    with engine.connect() as conn:
        for stmt in ddl:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[迁移] 跳过 {stmt.split(' ')[2:5]}：{e}")
    print("[迁移] 表结构已就绪")


def main():
    ensure_schema()
    conn = connect()
    cur = conn.cursor()

    # 1. 默认机构
    cur.execute("SELECT id, name, invite_code FROM organizations WHERE name = %s",
                (DEFAULT_ORG_NAME,))
    row = cur.fetchone()
    if row is None:
        from app import billing
        invite_code = billing.generate_invite_code()
        cur.execute(
            "INSERT INTO organizations (name, invite_code, contact_name, contact_phone,"
            " seat_limit, subscription_plan_code, is_active, created_at)"
            " VALUES (%s, %s, '', '', %s, '', TRUE, NOW())",
            (DEFAULT_ORG_NAME, invite_code, DEFAULT_SEAT_LIMIT),
        )
        conn.commit()
        org_id = cur.fetchone()[0] if cur.description else None
        cur.execute("SELECT id FROM organizations WHERE name = %s", (DEFAULT_ORG_NAME,))
        org_id = cur.fetchone()[0]
        print(f"[迁移] 已创建默认机构「{DEFAULT_ORG_NAME}」，id={org_id}，邀请码={invite_code}")
    else:
        org_id, name, invite_code = row
        print(f"[迁移] 默认机构已存在：id={org_id} 名称={name} 邀请码={invite_code}")

    # 2. 老用户挂到该机构（只处理还没有机构的）
    cur.execute(
        "UPDATE users SET organization_id = %s, org_role = 'member',"
        " registered_via = COALESCE(NULLIF(registered_via, ''), 'admin')"
        " WHERE organization_id IS NULL AND is_admin = FALSE",
        (org_id,),
    )
    moved = cur.rowcount
    conn.commit()
    print(f"[迁移] 已把 {moved} 个存量学员挂到「{DEFAULT_ORG_NAME}」")

    # 3. billing 设置
    cur.execute("SELECT id, value FROM system_settings WHERE key = 'billing'")
    row = cur.fetchone()
    if row is None:
        import json
        from app import billing as billing_lib
        payload = json.dumps(billing_lib.DEFAULT_BILLING_SETTINGS, ensure_ascii=False)
        cur.execute("INSERT INTO system_settings (key, value, updated_at) VALUES ('billing', %s, NOW())",
                    (payload,))
        conn.commit()
        print("[迁移] 已写入 billing 设置（收费开关关闭）")
    else:
        print("[迁移] billing 设置已存在，保持原值")

    cur.execute("SELECT COUNT(*) FROM users WHERE organization_id = %s", (org_id,))
    print(f"[迁移] 机构「{DEFAULT_ORG_NAME}」当前成员数：{cur.fetchone()[0]}/{DEFAULT_SEAT_LIMIT}")
    conn.close()


if __name__ == "__main__":
    main()
