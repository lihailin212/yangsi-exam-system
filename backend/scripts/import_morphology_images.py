"""增量导入形态学图片到题库（不重建整个题库）。

用途：E 盘新增了图片，只需要把这批图按现有题库的规矩补进去，
原有的 1300 多道题和考试一律不动。

流程和 regenerate_morphology_bank.py 完全一致：
  1. 扫描图片 -> 去掉文件名里的编号得到规范答案，目录名决定分类
  2. MD5 + dHash 两级查重（和已有题库图片比）
  3. 压缩到最长边 1280，按 sha1(相对路径)+sha1(文件名) 命名存本地
  4. 上传 Vercel Blob（images/morph/）
  5. 每张图出一道单选题 + 一道填空题
     干扰项优先取"形态易混淆"，再取同分类随机，最后跨分类随机；
     正确答案位置在 A/B/C/D 之间均衡发牌
  6. 写进生产库，并把新题备份成 JSON（可一键回滚）

用法:
    cd backend
    python scripts/import_morphology_images.py --src "E:\\细胞形态学图片\\新增" --dry-run
    python scripts/import_morphology_images.py --src "E:\\细胞形态学图片\\新增" --apply
"""
import argparse
import collections
import hashlib
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

for line in open(REPO / ".env.local", encoding="utf-8-sig"):
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"'))

import regenerate_morphology_bank as R   # 复用标签规范化 / 易混淆表 / 答案别名

WORK_DIR = BACKEND / "uploads" / "images" / "morph"
BLOB_PREFIX = "images/morph"
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
SEED = 20261030


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash_of(path, size=16):
    from PIL import Image
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        row = px[r * (size + 1):(r + 1) * (size + 1)]
        for c in range(size):
            bits = (bits << 1) | (1 if row[c] < row[c + 1] else 0)
    return bits


def scan(src_root: Path):
    """扫描新增目录。相对路径以 src_root 的上级为基准，保证命名唯一。"""
    base = src_root.parent
    items = []
    for path in sorted(src_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMG_EXT:
            continue
        rel = str(path.relative_to(base))
        parts = rel.split(os.sep)
        sub = parts[1] if len(parts) >= 2 else ""
        answer = R.base_label(path.name, rel)
        items.append({
            "path": path,
            "rel": rel,
            "sub": sub if sub in R.CATEGORY_BY_SUB else "",
            "filename": path.name,
            "answer": answer,
        })
    return items


def existing_bank():
    """已有题库图片的 md5/dHash，用于查重。"""
    md5s, dhashes = set(), {}
    if not WORK_DIR.exists():
        return md5s, dhashes
    for p in WORK_DIR.iterdir():
        if p.suffix.lower() not in IMG_EXT or p.name.startswith("_"):
            continue
        md5s.add(md5_of(p))
        try:
            dhashes.setdefault(dhash_of(p), []).append(p.name)
        except Exception:
            pass
    return md5s, dhashes


def dedupe(items):
    md5s, dhashes = existing_bank()
    kept, dropped = [], []
    for it in items:
        m = md5_of(it["path"])
        if m in md5s:
            dropped.append((it, "与已有图片字节相同"))
            continue
        try:
            dh = dhash_of(it["path"])
        except Exception:
            dh = None
        # dHash 只在答案标签相同时才判重复，避免同形态不同照片被误删
        if dh is not None and dh in dhashes:
            same_label = False
            for name in dhashes[dh]:
                rel = json.loads((WORK_DIR / "_srcrel.json").read_text(encoding="utf-8")).get(name, "") \
                    if (WORK_DIR / "_srcrel.json").exists() else ""
                if rel:
                    same_label = True
                    break
            if same_label:
                dropped.append((it, "与已有图片内容重复(dHash)"))
                continue
        md5s.add(m)
        if dh is not None:
            dhashes.setdefault(dh, []).append(it["rel"])
        kept.append(it)
    return kept, dropped


def prepare_images(items):
    from PIL import Image
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    for it in items:
        name = hashlib.sha1(it["rel"].encode("utf-8")).hexdigest()[:10]
        tag = hashlib.sha1(it["filename"].encode("utf-8")).hexdigest()[:6]
        it["blob_name"] = f"{name}_{tag}.jpg"
        out_path = WORK_DIR / it["blob_name"]
        it["local_path"] = out_path
        if out_path.exists():
            continue
        im = Image.open(it["path"])
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > 1280:
            ratio = 1280 / max(w, h)
            im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
        im.save(out_path, "JPEG", quality=90, optimize=True)
        print("  已压缩 %s -> %s (%dx%d)" % (it["filename"], it["blob_name"], w, h))


def upload_to_blob(items, src_root=""):
    from app.storage import upload_bytes

    for it in items:
        data = open(it["local_path"], "rb").read()
        last = None
        for _ in range(3):
            try:
                it["url"] = upload_bytes(f"{BLOB_PREFIX}/{it['blob_name']}", data)
                break
            except Exception as exc:
                last = exc
                time.sleep(1.5)
        else:
            raise RuntimeError("上传失败 %s: %s" % (it["rel"], last))
    # 映射表一并更新，方便以后对账
    map_path = WORK_DIR / "_blob_map.json"
    cached = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else {}
    for it in items:
        cached[it["blob_name"]] = it["url"]
    map_path.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  已上传 %d 张到 Blob" % len(items))


def label_pool(conn):
    """从已有题库里取出各分类的可用答案（干扰项来源）。"""
    from sqlalchemy import text
    pool = collections.defaultdict(set)
    rows = conn.execute(text(
        "select category, options from questions "
        "where category like '形态学/%' and type='single'")).fetchall()
    for cat, opts in rows:
        try:
            d = json.loads(opts or "{}")
        except (TypeError, ValueError):
            continue
        for v in d.values():
            if v:
                pool[cat].add(v)
    return pool


def build_questions(items, pool, seed=SEED):
    """按现有题库的规矩出题：单选 + 填空。"""
    all_labels = set()
    for s in pool.values():
        all_labels |= s
    rng = random.Random(seed)
    CONFUSABLE = R.load_confusables()
    letters = ["A", "B", "C", "D"]
    # 正确答案位置均衡发牌
    deck = [letters[i % 4] for i in range(len(items))]
    rng.shuffle(deck)

    questions = []
    for idx, it in enumerate(items):
        answer = it["answer"]
        cat = R.CATEGORY_BY_SUB[it["sub"]]
        banned = R.FAMILY_MAP.get(answer, {answer})
        conf_list = [x for x in CONFUSABLE.get(answer, [])
                     if x in all_labels and x != answer and x not in banned]
        same = [x for x in pool[cat] if x != answer and x not in banned]
        other = [x for x in all_labels
                 if x != answer and x not in banned and x not in pool[cat]]
        rng.shuffle(same)
        rng.shuffle(other)
        picked = []
        for x in conf_list:
            if x not in picked:
                picked.append(x)
            if len(picked) == 3:
                break
        for x in same + other:
            if len(picked) == 3:
                break
            if x not in picked:
                picked.append(x)
        if len(picked) < 3:
            raise SystemExit("干扰项不足: %s (%s)" % (it["rel"], answer))

        options = picked + [answer]
        rng.shuffle(options)
        target = deck[idx]
        ti, ci = letters.index(target), letters.index(letters[options.index(answer)])
        options[ti], options[ci] = options[ci], options[ti]
        opt_json = {letters[i]: options[i] for i in range(4)}
        content = (
            f"<p>{R.STEM_BY_SUB[it['sub']]}：</p>"
            f'<img style="max-width:50%" src="{it["url"]}" alt="image" />'
        )
        questions.append({
            "type": "single", "content": content,
            "options": json.dumps(opt_json, ensure_ascii=False),
            "answer": target, "analysis": "", "category": cat,
            "_rel": it["rel"], "_answer": answer,
        })
        fill_content = (
            f"<p>{R.STEM_BY_SUB[it['sub']].replace('请选择下图所示的', '请填写下图所示的')}：</p>"
            f'<img style="max-width:50%" src="{it["url"]}" alt="image" />'
        )
        questions.append({
            "type": "fill", "content": fill_content, "options": "{}",
            "answer": R.fill_answer_for(answer), "analysis": "", "category": cat,
            "_rel": it["rel"], "_answer": answer,
        })
    return questions


def insert(conn, questions):
    """逐条插入并取回 id。

    不用 executemany + RETURNING：带 RETURNING 的批量插入在部分驱动上
    拿不到返回行（会报 ResourceClosedError），这里图省事就一条条插，
    32 条也就几秒。
    """
    from sqlalchemy import text
    stmt = text(
        "insert into questions (type, content, options, answer, analysis, category, created_at) "
        "values (:type, :content, :options, :answer, :analysis, :category, CURRENT_TIMESTAMP) "
        "returning id")
    ids = []
    for q in questions:
        row = conn.execute(stmt, {
            "type": q["type"], "content": q["content"], "options": q["options"],
            "answer": q["answer"], "analysis": q["analysis"], "category": q["category"],
        }).first()
        ids.append(row[0])
    conn.commit()
    return ids


def main():
    ap = argparse.ArgumentParser(description="增量导入形态学图片到题库")
    ap.add_argument("--src", required=True, help="新增图片所在目录")
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只演练）")
    ap.add_argument("--skip-upload", action="store_true",
                    help="只写库不上传（Blob 不可用时用；之后可再跑 --upload-only 补传）")
    ap.add_argument("--upload-only", action="store_true", help="只补传图片，不动数据库")
    ap.add_argument("--backup", default="", help="新题备份 JSON 路径")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        raise SystemExit("目录不存在: %s" % src)

    items = scan(src)
    print("扫描到 %d 张图片" % len(items))
    if not items:
        return
    for it in items:
        print("  %s -> 答案「%s」 分类 %s" % (it["rel"], it["answer"],
                                            R.CATEGORY_BY_SUB.get(it["sub"], "?")))
    kept, dropped = dedupe(items)
    for it, why in dropped:
        print("  [跳过] %s —— %s" % (it["rel"], why))
    print("去重后 %d 张" % len(kept))
    if not kept:
        return

    prepare_images(kept)

    if args.upload_only:
        upload_to_blob(kept, args.src)
        return

    if args.apply and not args.skip_upload:
        upload_to_blob(kept, args.src)
    else:
        from app.storage import storage_public_base
        base = storage_public_base()
        for it in kept:
            it["url"] = "%s/%s/%s" % (base, BLOB_PREFIX, it["blob_name"])
        print("（图片未上传，地址按规则拼出：存储恢复后补传即可）")

    from sqlalchemy import create_engine, text
    dsn = os.environ["DATABASE_URL"]
    engine = create_engine(dsn)
    with engine.connect() as conn:
        pool = label_pool(conn)
        questions = build_questions(kept, pool)
        print("生成 %d 道题（%d 单选 + %d 填空）" % (
            len(questions),
            sum(1 for q in questions if q["type"] == "single"),
            sum(1 for q in questions if q["type"] == "fill")))
        for q in questions[:4]:
            print("  样例[%s] %s -> %s" % (q["type"], q["_rel"], q["answer"]))
        if args.apply:
            ids = insert(conn, questions)
            print("已写入生产库，新题 id: %s" % ids)
            default_name = "morph_import_%s.json" % time.strftime("%Y%m%d_%H%M%S")
            backup = args.backup or str(BACKEND / "backups" / default_name)
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            with open(backup, "w", encoding="utf-8") as fp:
                json.dump({"question_ids": ids,
                           "questions": [{k: v for k, v in q.items() if not k.startswith("_")}
                                         for q in questions],
                           "images": [{"rel": it["rel"], "blob_name": it["blob_name"],
                                       "url": it["url"]} for it in kept]},
                          fp, ensure_ascii=False, indent=1)
            print("备份 -> %s" % backup)
            print("（回滚：python scripts/rollback_morphology_import.py %s）" % backup)
    engine.dispose()


if __name__ == "__main__":
    main()
