# -*- coding: utf-8 -*-
"""整页「多阈值重识别」，把整页 OCR 漏掉的行捞回来。

现象
----
RapidOCR 偶尔会整行漏检。典型例子：2017 年基础知识答案册第一页，
左栏里「3.答案：A。」(y=967) 和「解析：正常人体内存在多种微量自身抗体」(y=1268)
之间，本该有的「4. 答案：C。」(y≈1223) 整行没被识别出来，
于是这一卷的答案册少了一个号。

原因不是图上没字，而是检测阶段（DBNet）在浅色/低对比度的行上没给框：
把同一张图二值化之后再跑一次 OCR，那一行就出来了（见 `exp_var.py` 的实验）。

做法
----
1. 对指定页渲染 200dpi 灰度图，按若干阈值二值化，各跑一次 OCR；
2. 只保留「和已有框不重叠」的新框 —— 已经认出来的文字一个字都不动，
   免得重识别把好的行改坏；
3. 新框写进缓存（backend/.cache/past_papers/reocr/），重跑解析时直接读缓存。

坐标约定：OCR 缓存里的框是 200dpi 下的页面像素；PDF 用 fitz 打开，
缩放系数 k = 72/200。
"""
import json
import pathlib
import re

CACHE_VERSION = 5   # v5 = 抹掉浅灰水印后再识别

# 带子重识别用的阈值。整页重识别时 140/170 各能救回一些行，
# 带子里行少，原图 + 一个二值化就够了。
BAND_THRESHOLDS = (140,)

# 二值化阈值（灰度 < thr 视为墨迹）。150 附近对扫描件最稳，
# 120/180 补浅字和深字两头。
THRESHOLDS = (110, 140, 170)

_CACHE_DIR = None


def cache_dir(base: pathlib.Path):
    """重识别缓存目录。"""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = pathlib.Path(base) / ".cache" / "past_papers" / "reocr"
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


# 扫描水印是浅灰色的斜向叠加层。实测各年份答案册里的水印碎片框，
# 最暗的一笔灰度是 216；正文的墨迹都在 200 以下（很多在 60 以下）。
# 所以 205 这条线能把水印整片抹掉，而正文一个像素都不伤。
WATERMARK_SHADE = 205


def deshade(img, thr=WATERMARK_SHADE):
    """把浅灰色（扫描水印）的像素抹成白纸。

    水印是斜着盖在正文上的，OCR 认不出横排文字，
    只能读出一堆莫名其妙的碎片（「8：案答.00」「不前册其，变」），
    这些碎片会混进答案字母和解析正文里。抹掉水印比事后修补干净得多。
    """
    import numpy as np

    if img is None or img.size == 0:
        return img
    g = img.mean(axis=2)
    out = img.copy()
    out[g >= thr] = 255
    return out


def render_page(doc, pno, dpi=200, deshade_img=True):
    """渲染一页，返回 RGB numpy 数组（默认先抹掉浅灰水印）。"""
    import numpy as np

    pix = doc[pno].get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n)
    if img.shape[2] == 4:
        img = img[:, :, :3]
    if deshade_img:
        img = deshade(img)
    return img


def binarize(img, thr):
    """灰度后二值化：墨迹（暗）变白，纸底变黑。"""
    import cv2

    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return (g < thr).astype("uint8") * 255


def ocr_boxes(engine, img):
    """跑一次 OCR，返回页面坐标下的框列表。"""
    res, _ = engine(img)
    out = []
    for item in (res or []):
        box, txt, conf = item[0], item[1], item[2]
        if isinstance(conf, str):
            try:
                conf = float(conf)
            except ValueError:
                conf = 0.0
        out.append({
            "x": int(min(p[0] for p in box)),
            "y": int(min(p[1] for p in box)),
            "x2": int(max(p[0] for p in box)),
            "y2": int(max(p[1] for p in box)),
            "t": txt,
            "c": float(conf),
        })
    return out


def _norm(text):
    """归一化文字，用来比较两个框是不是同一句话。"""
    return re.sub(r"[\s:：,，。.、;；'\"“”‘’()（）\[\]【】\-—_~·]+", "", text or "")


def _overlap_area(a, b):
    ix = min(a["x2"], b["x2"]) - max(a["x"], b["x"])
    iy = min(a["y2"], b["y2"]) - max(a["y"], b["y"])
    if ix <= 0 or iy <= 0:
        return 0
    return ix * iy


def _box_area(a):
    return max(1, (a["x2"] - a["x"]) * (a["y2"] - a["y"]))


def _center_inside(inner, outer, pad=4):
    cx = (inner["x"] + inner["x2"]) / 2
    cy = (inner["y"] + inner["y2"]) / 2
    return (outer["x"] - pad <= cx <= outer["x2"] + pad
            and outer["y"] - pad <= cy <= outer["y2"] + pad)


def is_duplicate(new, old_boxes):
    """新框是不是旧框的重复（位置重合或文字一样）。

    重识别时，同一行会被认好几次：普通图一次、二值化若干次。
    旧框已经有的文字不该被替换，所以重复的一律丢掉。
    """
    ntxt = _norm(new["t"])
    for ob in old_boxes:
        if _overlap_area(new, ob) >= 0.25 * _box_area(new):
            return True
        if _center_inside(new, ob):
            return True
        if ntxt and ntxt == _norm(ob["t"]):
            return True
    return False


def merge_new_boxes(old_boxes, new_boxes):
    """把重识别出来的新框并进旧框表，返回真正新增的那些。

    v3 起不再丢掉和旧框重叠的新框。旧框把答案行和上一行的正文粘在
    一起时（「…大量水22．答案：B」），旧框本身解析不出答案，只有
    二值化识别出来的「22．答案:B」能救回来 —— 这时候必须让新框留下来。
    文字和旧框一模一样的仍然丢掉，免得缓存白白变大。
    """
    added = []
    old_norm = {_norm(ob.get("t")) for ob in old_boxes}
    for nb in new_boxes:
        if not (nb.get("t") or "").strip():
            continue
        ntxt = _norm(nb["t"])
        if not ntxt or ntxt in old_norm:
            continue
        if any(_norm(ob.get("t")) == ntxt for ob in added):
            continue
        added.append(nb)
    return added


def _cache_path(base, stem, pno):
    return cache_dir(base) / f"{stem}__p{pno + 1:04d}.json"


def reocr_page(base, stem, pno, doc, old_boxes, engine, thresholds=THRESHOLDS,
               use_cache=True, include_plain=False):
    """对一页做多阈值重识别，返回新增的框。

    old_boxes 是这一页原本就有的框（用于剔除重复）。
    include_plain=True 时额外跑一次原图 —— 整页漏掉的页用它最稳，
    别的页原图的结果会和 old_boxes 重复而被自动剔除。

    结果按页缓存：同一页只算一次，重跑解析直接读缓存。
    """
    cp = _cache_path(base, stem, pno)
    if use_cache and cp.exists():
        try:
            data = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            data = None
        if data and data.get("v") == CACHE_VERSION:
            return data.get("boxes") or []

    img = render_page(doc, pno)
    found = []
    if include_plain:
        try:
            found.extend(ocr_boxes(engine, img))
        except Exception as exc:                       # noqa: BLE001
            print(f"[reocr] {stem} p{pno + 1} 原图失败: {exc}")
    for thr in thresholds:
        try:
            found.extend(ocr_boxes(engine, binarize(img, thr)))
        except Exception as exc:                       # noqa: BLE001
            print(f"[reocr] {stem} p{pno + 1} thr{thr} 失败: {exc}")
    added = merge_new_boxes(old_boxes, found)
    cp.write_text(json.dumps({"v": CACHE_VERSION, "boxes": added},
                             ensure_ascii=False), encoding="utf-8")
    return added


def _band_cache_path(base, stem, pno):
    return cache_dir(base) / f"{stem}__p{pno + 1:04d}_bands.json"


def _band_key(band):
    return "%d_%d_%d_%d" % tuple(int(v) for v in band)


def reocr_bands(base, stem, pno, doc, old_boxes, engine, bands,
                thresholds=BAND_THRESHOLDS, use_cache=True):
    """对一页的若干条「带子」做重识别，返回新增的框（页面坐标）。

    带子 = (y0, y1, x0, x1)，200dpi 的页面像素。

    为什么只识别带子
    ----------------
    整页重识别一次要 35 秒：解析文字有上百行，识别模型要逐行跑一遍。
    带子里只有几行，一两秒就完。而且带子越小识别越准 ——
    整页识别会整行漏掉的「4.答案：C。」，在带子里能清清楚楚读出来。

    坐标约定：OCR 缓存里的框是 200dpi 下的页面像素；PDF 用 fitz 打开，
    缩放系数 k = 72/200。fitz 的页码是 0 起的。
    """
    cp = _band_cache_path(base, stem, pno)
    data = {"v": CACHE_VERSION, "bands": {}}
    if use_cache and cp.exists():
        try:
            old = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            old = None
        if old and old.get("v") == CACHE_VERSION:
            data = old

    img = None
    for band in bands:
        key = _band_key(band)
        if key in data["bands"]:
            continue
        if img is None:
            img = render_page(doc, pno)
        y0, y1, x0, x1 = (int(v) for v in band)
        sub = img[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        if sub.size == 0:
            data["bands"][key] = []
            continue
        found = []
        try:
            found.extend(ocr_boxes(engine, sub))
        except Exception as exc:                       # noqa: BLE001
            print(f"[reocr] {stem} p{pno + 1} 带子{key} 原图失败: {exc}")
        for thr in thresholds:
            try:
                found.extend(ocr_boxes(engine, binarize(sub, thr)))
            except Exception as exc:                   # noqa: BLE001
                print(f"[reocr] {stem} p{pno + 1} 带子{key} thr{thr} 失败: {exc}")
        for b in found:                               # 换算回页面坐标
            b["x"] += x0
            b["x2"] += x0
            b["y"] += y0
            b["y2"] += y0
        data["bands"][key] = merge_new_boxes(old_boxes, found)

    cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = []
    for band in bands:
        out.extend(data["bands"].get(_band_key(band)) or [])
    return out
