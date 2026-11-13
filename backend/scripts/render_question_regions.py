# -*- coding: utf-8 -*-
"""把「选项里有重复」的题渲染成高清图，供人工逐题核对。

题库里这批题是 2010~2023 年真题 PDF OCR 进来的，OCR 认不出的符号
（下标数字、↑↓ 箭头）被丢掉，于是同一道题的选项变成一串一样的字
（"G期""LD""M"），考生没法选。

RapidOCR 对这些符号无能为力（200/400/600dpi 都试过，箭头一律读成 "V"），
PaddleOCR 在这台机器上跑不起来（paddle 的 oneDNN/PIR 冲突），
所以改成：把 PDF 对应区域用 400dpi 渲染成图，人工核对后回填。

用法：
    cd backend && python scripts/render_question_regions.py
"""
import argparse
import json
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))
from db import connect  # noqa: E402

PDF_DIR = pathlib.Path(r"D:\李海林\医学检验职称考试历年真题")
OCR_DIR = BACKEND / ".cache" / "ocr"
OUT = BACKEND / ".cache" / "_qfix"

WIN = 8   # 滑窗长度：题干前 8 个字在框里能对上就算命中
_opt_re = re.compile(r"^\s*([A-E])\s*[.．、:：]\s*(.*)$")
_num_re = re.compile(r"^\s*\d{1,3}\s*[.．、]")


def norm(s):
    return re.sub(r"[\s，,。．.、：:；;？?！!（）()「」“”\"'【】\[\]]+", "", s or "")


def build_index():
    global _cache_index
    try:
        return _cache_index
    except NameError:
        pass
    idx = {}
    for f in sorted(OCR_DIR.glob("*.json")):
        m = re.match(r"(.+?)__p(\d+)\.json$", f.name)
        if not m:
            continue
        stem, page = m.group(1), int(m.group(2))
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for b in d.get("boxes", []):
            t = (b.get("t") or "").strip()
            t = re.sub(r"^\d{1,3}\s*[.．、]\s*", "", t)
            key = norm(t)
            for i in range(0, max(1, len(key) - WIN + 1)):
                idx.setdefault(key[i:i + WIN], []).append((f, page, stem, t))
    _cache_index = idx
    return idx


def find_page(stem):
    idx = build_index()
    s = norm(stem)
    for n in (20, 16, 12, 10, 8, 6):
        if len(s) < n:
            continue
        hits = idx.get(s[:n])
        if hits:
            return hits[0]
    return None


def _scan_column(boxes, y0, col_left):
    """在一栏里找这道题的选项，返回 {字母: (y, y2, x, x2)}"""
    lines = sorted([b for b in boxes
                    if (b.get("x", 0) < 600) == col_left and b.get("y", 0) >= y0 - 4],
                   key=lambda b: b.get("y", 0))
    found = {}
    for b in lines:
        t = (b.get("t") or "").strip()
        if not t:
            continue
        y = b.get("y", 0)
        if y - y0 > 700:
            break
        mo = _opt_re.match(t)
        if mo and mo.group(1) not in found:
            found[mo.group(1)] = b
            if len(found) >= 5:
                break
        elif _num_re.match(t) and found:
            break
    return found


def option_region(cache_file, page_no, stem_text):
    """从该页的 OCR 框里找出这道题（含题干和 A~E 选项）的矩形区域。

    返回 (x0, y0, x1, y1)，坐标是 200dpi 下的页面像素。
    题干可能跨行、选项也可能续到另一栏，所以两栏都试，取能凑齐选项的那栏。
    """
    d = json.loads(cache_file.read_text(encoding="utf-8"))
    boxes = [b for b in d.get("boxes", []) if b.get("t")]
    stem_key = norm(stem_text)[:8]
    cand = None
    for b in boxes:
        t = re.sub(r"^\d{1,3}\s*[.．、]\s*", "", b.get("t") or "").strip()
        if stem_key and stem_key in norm(t):
            cand = b
            break
    if cand is None:
        return None
    y0 = cand.get("y", 0)
    stem_left = cand.get("x", 0) < 600

    best = None
    for col_left in (stem_left, not stem_left):
        found = _scan_column(boxes, y0, col_left)
        if len(found) >= 3:
            best = (col_left, found)
            break
    if best is None:
        found = _scan_column(boxes, y0, stem_left) or _scan_column(boxes, y0, not stem_left)
        if not found:
            return None
        best = (stem_left, found)
    col_left, found = best

    lo_x, hi_x = (100, 650) if col_left else (740, 1590)
    last_y = cand.get("y2", y0)
    for b in found.values():
        last_y = max(last_y, b.get("y2", b.get("y", 0)))
    return (lo_x, max(0, y0 - 8), hi_x, min(last_y + 10, 6600))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=400)
    ap.add_argument("--sheet", type=int, default=4, help="一张图里放几道题")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    import fitz
    from PIL import Image, ImageDraw

    ids = []
    rep = BACKEND / "scripts" / "audit_report.txt"
    for line in rep.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\[选项重复\] id=(\d+)", line)
        if m and int(m.group(1)) not in ids:
            ids.append(int(m.group(1)))

    conn = connect()
    cur = conn.cursor()
    docs = {}
    tasks = []
    for qid in ids:
        cur.execute("select content, options, answer, category from questions where id=%s", (qid,))
        row = cur.fetchone()
        if not row:
            continue
        content = re.sub(r"<[^>]+>", "", row[0] or "")
        hit = find_page(content)
        if not hit:
            tasks.append({"id": qid, "ok": False, "stem": content[:50]})
            continue
        cache_file, page_no, pdf_stem, matched = hit
        pdf = PDF_DIR / f"{pdf_stem}.pdf"
        if not pdf.exists():
            tasks.append({"id": qid, "ok": False, "stem": content[:50]})
            continue
        if pdf_stem not in docs:
            docs[pdf_stem] = fitz.open(pdf)
        doc = docs[pdf_stem]
        if page_no - 1 >= doc.page_count:
            tasks.append({"id": qid, "ok": False, "stem": content[:50]})
            continue
        region = option_region(cache_file, page_no, matched)
        if not region:
            tasks.append({"id": qid, "ok": False, "stem": content[:50]})
            continue
        k = 200 / 72.0
        page = doc[page_no - 1]
        clip = fitz.Rect(region[0] / k, region[1] / k, region[2] / k, region[3] / k)
        pix = page.get_pixmap(dpi=args.dpi, clip=clip)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        f = OUT / f"q{qid}.png"
        img.save(f)
        tasks.append({"id": qid, "ok": True, "png": str(f), "pdf": pdf_stem,
                      "page": page_no, "stem": content[:70],
                      "options": json.loads(row[1] or "{}"), "answer": row[2],
                      "category": row[3]})
    conn.close()

    ok = [t for t in tasks if t["ok"]]
    print(f"共 {len(ids)} 题，渲染成功 {len(ok)} 题")

    # 拼成联系表：一张图几道题，标上题号
    per = args.sheet
    sheet_dir = OUT / "sheets"
    sheet_dir.mkdir(exist_ok=True)
    for i in range(0, len(ok), per):
        group = ok[i:i + per]
        imgs = [Image.open(t["png"]).convert("RGB") for t in group]
        w = max(im.width for im in imgs) + 20
        h = sum(im.height + 34 for im in imgs) + 20
        sheet = Image.new("RGB", (w, h), "white")
        dr = ImageDraw.Draw(sheet)
        y = 10
        for t, im in zip(group, imgs):
            dr.text((12, y), f"### id={t['id']}  answer={t['answer']}  {t['stem'][:40]}",
                    fill=(200, 0, 0))
            y += 26
            sheet.paste(im, (12, y))
            y += im.height + 8
        sheet.save(sheet_dir / f"sheet{i//per:02d}.png")
    print(f"联系表 {len(list(sheet_dir.glob('*.png')))} 张 -> {sheet_dir}")

    (OUT / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    miss = [t for t in tasks if not t["ok"]]
    for t in miss:
        print(f"  ✗ id={t['id']} {t['stem'][:40]}")


if __name__ == "__main__":
    main()
