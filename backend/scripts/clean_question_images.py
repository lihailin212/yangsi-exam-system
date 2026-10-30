"""清理题库图片水印并重新上传。

两类水印：
1. 室间质评版权水印——右下角三行中文小字（国家卫生健康委临床检验中心…），
   用黑帽形态学 + 模板匹配定位，笔画抠出来做 inpaint。
2. "细胞助手"公众号角标——白色浮雕字，用 Canny 边缘模板匹配定位，
   把亮笔画抠出来做 inpaint。

用法：
    cd backend
    python scripts/clean_question_images.py --staging ../_wm_out      # 只处理到暂存目录
    python scripts/clean_question_images.py --staging ../_wm_out --upload   # 再上传 Blob
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

# ---- 室间质评水印模板 ----
EQA_SEED = "b6705444fe_006a02.jpg"
EQA_SEED_BOX = (388, 466, 425, 688)   # y0, y1, x0, x1
EQA_SEED_WIDTH = 696
BH_KERNEL = np.ones((15, 15), np.uint8)
EQA_THRESHOLD = 0.40

# ---- 细胞助手角标模板 ----
LOGO_SEED = "400ca21b19_cd5875.jpg"
LOGO_BOX = (556, 604, 958, 1080)      # y0, y1, x0, x1
LOGO_THRESHOLD = 0.45


def _echa_template(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    y0, y1, x0, x1 = EQA_SEED_BOX
    tpl = img[y0:y1, x0:x1]
    resp = cv2.morphologyEx(tpl, cv2.MORPH_BLACKHAT, BH_KERNEL)
    return cv2.GaussianBlur(resp, (0, 0), 1.0)


def _match_all(img_gray, tpl, scales):
    resp = cv2.GaussianBlur(cv2.morphologyEx(img_gray, cv2.MORPH_BLACKHAT, BH_KERNEL), (0, 0), 1.0)
    best, box = -1.0, None
    for s in scales:
        t = cv2.resize(tpl, None, fx=float(s), fy=float(s), interpolation=cv2.INTER_CUBIC)
        if t.shape[0] >= resp.shape[0] or t.shape[1] >= resp.shape[1]:
            continue
        r = cv2.matchTemplate(resp, t, cv2.TM_CCOEFF_NORMED)
        idx = int(r.argmax())
        v = float(r.flat[idx])
        if v > best:
            ty, tx = divmod(idx, r.shape[1])
            best, box = v, (int(tx), int(ty), t.shape[1], t.shape[0])
    return best, box


def find_eqa(gray, tpl):
    h, w = gray.shape[:2]
    base = w / float(EQA_SEED_WIDTH)
    scales = [base + d for d in (-0.10, -0.06, -0.03, 0.0, 0.03, 0.06, 0.10) if base + d > 0.05]
    score, box = _match_all(gray, tpl, scales)
    # 水印压在图片下半部分；上半部分匹配到的多半是网页截图里的文字
    if box is not None and box[1] < h * 0.45:
        return 0.0, None
    return score, box


def find_logo(gray, tpl):
    e = cv2.Canny(gray, 40, 120)
    best, box = -1.0, None
    for s in (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4):
        t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
        if t.shape[0] >= e.shape[0] or t.shape[1] >= e.shape[1]:
            continue
        r = cv2.matchTemplate(e, t, cv2.TM_CCOEFF_NORMED)
        idx = int(r.argmax())
        v = float(r.flat[idx])
        if v > best:
            ty, tx = divmod(idx, r.shape[1])
            best, box = v, (int(tx), int(ty), t.shape[1], t.shape[0])
    return best, box


def _region(gray, box, pad=0):
    x, y, w, h = box
    h_img, w_img = gray.shape[:2]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w_img, x + w + pad), min(h_img, y + h + pad)
    return gray[y0:y1, x0:x1], (x0, y0, x1, y1)


def eqa_mask(gray, box):
    """抠出文字的细笔画：笔画细，细胞核/组织块粗，用笔画宽度区分。"""
    region, (x0, y0, x1, y1) = _region(gray, box)
    if region.size == 0:
        return None
    w = x1 - x0
    k = max(3, int(round(w / 12.0)) | 1)
    bh = cv2.morphologyEx(region, cv2.MORPH_BLACKHAT, np.ones((k, k), np.uint8))
    bg = cv2.GaussianBlur(region, (0, 0), max(3, k))
    diff = bg.astype(np.int16) - region.astype(np.int16)
    mask = (diff > 25).astype(np.uint8) * 255
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 3)
    mask[dist > 3.0] = 0
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 3:
            keep[labels == i] = 255
    mask = cv2.dilate(keep, np.ones((3, 3), np.uint8), iterations=1)
    full = np.zeros_like(gray)
    full[y0:y1, x0:x1] = mask
    return full


def logo_mask(gray, box):
    """角标是白色浮雕字：白色笔画 + 灰色投影。

    开运算去掉亮笔画、闭运算去掉暗投影，两者和原图的差就是角标本身。
    """
    x, y, w, h = box
    h_img, w_img = gray.shape[:2]
    x0, y0 = max(0, x - 22), max(0, y - int(h * 0.55))
    x1, y1 = min(w_img, x + w + 8), min(h_img, y + h + 8)
    region = gray[y0:y1, x0:x1]
    if region.size == 0:
        return None
    ker = np.ones((11, 11), np.uint8)
    op = cv2.morphologyEx(region, cv2.MORPH_OPEN, ker)
    cl = cv2.morphologyEx(region, cv2.MORPH_CLOSE, ker)
    d1 = region.astype(np.int16) - op.astype(np.int16)
    d2 = region.astype(np.int16) - cl.astype(np.int16)
    mask = ((d1 > 4) | (d2 < -4)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=2)
    full = np.zeros_like(gray)
    full[y0:y1, x0:x1] = mask
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="uploads/images/morph")
    ap.add_argument("--staging", required=True)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.jpg")) +
                   glob.glob(os.path.join(args.dir, "*.jpeg")) +
                   glob.glob(os.path.join(args.dir, "*.png")))
    eqa_tpl = _echa_template(os.path.join(args.dir, EQA_SEED))
    lg = cv2.imread(os.path.join(args.dir, LOGO_SEED), cv2.IMREAD_GRAYSCALE)
    y0, y1, x0, x1 = LOGO_BOX
    logo_tpl = cv2.Canny(lg[y0:y1, x0:x1], 40, 120)

    os.makedirs(args.staging, exist_ok=True)
    records = []
    for i, f in enumerate(files):
        bgr = cv2.imread(f)
        if bgr is None:
            continue
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        kinds = []
        score, box = find_eqa(gray, eqa_tpl)
        if box is not None and score >= EQA_THRESHOLD:
            kinds.append(("eqa", score, box))
        score2, box2 = find_logo(gray, logo_tpl)
        if box2 is not None and score2 >= LOGO_THRESHOLD:
            kinds.append(("logo", score2, box2))
        if not kinds:
            continue
        out = bgr.copy()
        for kind, sc, bx in kinds:
            mask = eqa_mask(gray, bx) if kind == "eqa" else logo_mask(gray, bx)
            if mask is None or mask.sum() == 0:
                continue
            out = cv2.inpaint(out, mask, 6 if kind == "logo" else 4, cv2.INPAINT_TELEA)
            records.append({"file": os.path.basename(f), "kind": kind,
                            "score": round(sc, 4), "box": list(bx)})
        dst = os.path.join(args.staging, os.path.basename(f))
        cv2.imwrite(dst, out, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        print("[FIX] %-28s %s" % (os.path.basename(f), " ".join(k for k, _, _ in kinds)))
        if (i + 1) % 100 == 0:
            print("... %d/%d" % (i + 1, len(files)))

    files_fixed = sorted({r["file"] for r in records})
    print("\n共 %d 张图片，%d 张带水印" % (len(files), len(files_fixed)))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fp:
            json.dump(records, fp, ensure_ascii=False, indent=1)

    if args.upload:
        for line in open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), ".env.local"), encoding="utf-8-sig"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"'))
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.storage import upload_bytes
        for name in files_fixed:
            path = os.path.join(args.staging, name)
            with open(path, "rb") as fh:
                data = fh.read()
            url = upload_bytes("images/morph/" + name, data)
            print("[上传] images/morph/" + name + " -> " + url)


if __name__ == "__main__":
    main()

