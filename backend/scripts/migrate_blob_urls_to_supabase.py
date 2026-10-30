"""把题库里指向 Vercel Blob 的图片 URL 批量替换为 Supabase Storage 公网地址。

用法:
    python scripts/migrate_blob_urls_to_supabase.py            # 预览
    python scripts/migrate_blob_urls_to_supabase.py --apply    # 执行（自动备份到 backend/backups/）

环境变量: DATABASE_URL / SUPABASE_STORAGE_PUBLIC_BASE
"""
import json, os, sys, time
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, ".env.local"), os.path.join(os.path.dirname(ROOT), ".env.local"), os.path.join(ROOT, ".env")):
    if os.path.exists(_p):
        load_dotenv(_p, override=True)

OLD = os.environ.get("BLOB_BASE_URL", "https://u2wff8olceezsvlg.public.blob.vercel-storage.com").rstrip("/")
NEW = os.environ.get("SUPABASE_STORAGE_PUBLIC_BASE", "").rstrip("/")
TARGETS = [("questions", "content"), ("system_settings", "value")]


def main():
    apply = "--apply" in sys.argv
    if not NEW:
        raise SystemExit("缺少 SUPABASE_STORAGE_PUBLIC_BASE")
    eng = create_engine(os.environ["DATABASE_URL"])
    backup = []
    with eng.begin() as conn:
        for table, col in TARGETS:
            rows = conn.execute(text(
                f'select id, "{col}" from "{table}" where "{col}" like :pat'
            ), {"pat": f"%{OLD}%"}).fetchall()
            for rid, val in rows:
                backup.append({"table": table, "column": col, "id": rid, "old": val})
            print(f"{table}.{col}: 命中 {len(rows)} 行")
    if not backup:
        print("没有需要迁移的 URL")
        return

    bak_dir = os.path.join(ROOT, "backups")
    os.makedirs(bak_dir, exist_ok=True)
    bak_file = os.path.join(bak_dir, f"blob2supabase_urls_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(bak_file, "w", encoding="utf8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)
    print(f"备份已写入: {bak_file}  ({len(backup)} 条)")

    if not apply:
        print("预览模式，加 --apply 执行")
        return

    changed = 0
    with eng.begin() as conn:
        for table, col in TARGETS:
            res = conn.execute(text(
                f'update "{table}" set "{col}" = replace("{col}", :old, :new) where "{col}" like :pat'
            ), {"old": OLD, "new": NEW, "pat": f"%{OLD}%"})
            changed += res.rowcount
    print(f"已更新 {changed} 行")

    left = 0
    with eng.connect() as conn:
        for table, col in TARGETS:
            left += conn.execute(text(
                f'select count(*) from "{table}" where "{col}" like :pat'
            ), {"pat": f"%{OLD}%"}).scalar()
    print(f"仍残留旧 URL 的行: {left}")


if __name__ == "__main__":
    main()
