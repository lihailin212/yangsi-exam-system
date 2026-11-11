# -*- coding: utf-8 -*-
"""备份题库（questions 及关联表）到 backend/backups/question_bank.json。

每次运行覆盖同一个文件，所以永远是最新的那份，和"覆盖之前的"要求一致。

用法：
    cd backend && python scripts/backup_question_bank.py --dry-run
    cd backend && python scripts/backup_question_bank.py

默认连生产库（仓库根 .env.local 的 DATABASE_URL），
加 --local 连本地 SQLite（backend/exam.db）。
"""
import argparse
import json
import os
import pathlib
import sys
from datetime import datetime

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

# 备份要带的表：题库本体 + 挂在这批题上的卷子/考试/成绩。
# 少一张表，恢复时就会缺关联，考试和成绩对不上。
TABLES = [
    "questions",
    "question_papers",
    "exams",
    "exam_question",
    "exam_papers",
    "exam_attempts",
    "exam_records",
    "exam_distributions",
    "wrong_questions",
]

OUT_DIR = BACKEND / "backups"
OUT_FILE = OUT_DIR / "question_bank.json"


def load_dotenv_local():
    path = REPO / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def connect_prod():
    load_dotenv_local()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("未找到 DATABASE_URL（检查 .env.local 或环境变量）")
    import psycopg2
    return psycopg2.connect(url.replace("postgres://", "postgresql://"))


def connect_local():
    import sqlite3
    path = BACKEND / "exam.db"
    if not path.exists():
        sys.exit(f"本地库不存在：{path}")
    return sqlite3.connect(path)


def dump(conn, is_sqlite):
    out = {}
    cur = conn.cursor()
    for table in TABLES:
        try:
            cur.execute(f"SELECT * FROM {table}")
        except Exception as e:
            # 某张表还没建，跳过，不影响其余备份
            print(f"  跳过 {table}：{e}")
            continue
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            item = {}
            for k, v in zip(cols, row):
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                item[k] = v
            rows.append(item)
        out[table] = rows
        print(f"  {table}: {len(rows)} 行")
    return out


def main():
    ap = argparse.ArgumentParser(description="备份题库到 backend/backups/question_bank.json")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写文件")
    ap.add_argument("--local", action="store_true", help="连本地 SQLite 而不是生产库")
    args = ap.parse_args()

    print(f"[backup] 目标：{'本地 SQLite' if args.local else '生产库'}")
    conn = connect_local() if args.local else connect_prod()
    try:
        tables = dump(conn, args.local)
    finally:
        conn.close()

    total = sum(len(v) for v in tables.values())
    print(f"[backup] 共 {total} 行")
    if args.dry_run:
        print("[backup] --dry-run，未写文件")
        return

    payload = {
        "created_at": datetime.now().isoformat(),
        "source": "local" if args.local else "prod",
        "tables": tables,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 同一个文件名，覆盖上一份
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[backup] 已写入 {OUT_FILE}（覆盖旧文件，{OUT_FILE.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
