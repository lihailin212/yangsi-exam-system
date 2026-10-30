"""回滚一次「增量导入形态学图片」：删掉那批新题。

用法：
    cd backend && python scripts/rollback_morphology_import.py backups/morph_import_20261030_215857.json
"""
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
for line in open(REPO / ".env.local", encoding="utf-8-sig"):
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"'))

from sqlalchemy import create_engine, text

path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if path is None:
    cands = sorted((BACKEND / "backups").glob("morph_import_*.json"))
    if not cands:
        raise SystemExit("没有可回滚的备份")
    path = cands[-1]
data = json.loads(path.read_text(encoding="utf-8"))
ids = data["question_ids"]
print("备份文件:", path)
print("将删除 %d 道题" % len(ids))

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    # 先解绑考试关联，再删题
    removed_link = conn.execute(text(
        "delete from exam_question where question_id = any(:ids)"), {"ids": ids}).rowcount
    removed = conn.execute(text(
        "delete from questions where id = any(:ids)"), {"ids": ids}).rowcount
    conn.commit()
print("解除考试关联 %d 条，删除题目 %d 道" % (removed_link, removed))
engine.dispose()
