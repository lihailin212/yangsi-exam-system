"""修正题目（题干/选项/解析）里的错别字。

题库是从 Excel、PDF、OCR 各种来源导进来的，键盘手误（比如输入法切到英文
多敲了一个字母）留下的错字只能靠人工发现再改。这个脚本按「原文 -> 新文」
精确替换，改前先把原文和新文都打出来，核对无误再写库。

用法：
    cd backend && python scripts/fix_question_text.py --question-id 22728 \
        --old "E常人" --new "常人" --dry-run
    cd backend && python scripts/fix_question_text.py --question-id 22728 \
        --old "E常人" --new "常人"
"""
import argparse
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from db import load_dotenv_local

# app.database 在 import 时就要读 DATABASE_URL，必须先加载 .env.local
load_dotenv_local()

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

FIELDS = ("content", "options", "analysis")


def main():
    ap = argparse.ArgumentParser(description="替换题目里的文字")
    ap.add_argument("--question-id", type=int, required=True)
    ap.add_argument("--field", choices=FIELDS + ("all",), default="all")
    ap.add_argument("--old", required=True, help="要替换的原文")
    ap.add_argument("--new", required=True, help="替换成什么")
    ap.add_argument("--dry-run", action="store_true", help="只打印改动，不写库")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        q = db.query(models.Question).filter(models.Question.id == args.question_id).first()
        if not q:
            raise SystemExit(f"题目 id={args.question_id} 不存在")

        fields = FIELDS if args.field == "all" else (args.field,)
        changed = []
        for field in fields:
            text = getattr(q, field) or ""
            if args.old not in text:
                continue
            new_text = text.replace(args.old, args.new)
            print(f"--- {field} 改前 ---\n{text}\n--- {field} 改后 ---\n{new_text}\n")
            setattr(q, field, new_text)
            changed.append(field)

        if not changed:
            db.rollback()
            raise SystemExit(f"题目 {args.question_id} 里没有找到 {args.old!r}，未改动")

        if args.dry_run:
            db.rollback()
            print("（--dry-run，未写库）")
        else:
            db.commit()
            print(f"已写入：题目 {args.question_id} 的 {', '.join(changed)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
