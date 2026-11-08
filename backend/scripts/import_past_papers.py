# -*- coding: utf-8 -*-
"""历年职称考试真题导入流水线。

分四个阶段，每个阶段都能单独重跑：

    ocr    PDF -> 每页一份 OCR 结果 JSON（缓存在 backend/.cache/ocr/）
    parse  OCR JSON -> 结构化题目 JSON（缓存在 backend/.cache/past_papers/）
    clean  题目 JSON -> 清洗后的题目 JSON + 清洗报告 CSV
    load   题目 JSON -> 写库（--apply 才真的写）

用法（在仓库根目录）：

    python backend/scripts/import_past_papers.py --src "D:\\李海林\\医学检验职称考试历年真题" --stage ocr --jobs 2
    python backend/scripts/import_past_papers.py --src "..." --stage parse
    python backend/scripts/import_past_papers.py --src "..." --stage clean
    python backend/scripts/import_past_papers.py --src "..." --stage load --apply

为什么要分阶段：OCR 慢（850 页约 2 小时），中间任何一步都能断点续跑；
出问题时也只重跑解析或清洗，不必重新 OCR。
"""
import argparse
import csv
import difflib
import io
import json
import os
import pathlib
import re
import sys
import time
from datetime import datetime

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import past_papers_lib as L  # noqa: E402
import past_papers_reocr as R  # noqa: E402

CACHE = BACKEND / ".cache"
OCR_DIR = CACHE / "ocr"
PARSE_DIR = CACHE / "past_papers"
REPORT_DIR = BACKEND / "backups"

PAPER_FILE_RE = re.compile(r"(\d{4})年.*(试卷|答案)\.pdf$")

# 6 份专业知识 PDF（电子文本，走 pdfplumber 抽表）
KNOWLEDGE_FILES = {
    "临检.pdf": "血液",
    "免疫.pdf": "免疫学",
    "生化.pdf": "生化",
    "微生物.pdf": "微生物",
    "血液.pdf": "血液",
    "寄生虫与质量控制.pdf": "寄生虫与质量控制",
}
PARASITE_RE = re.compile(
    r"虫|卵|囊|蚴|原虫|孢子|滴虫|疟|血吸|蛔|钩虫|鞭毛|利什曼|隐孢子|旋毛|绦虫|包囊|子孢|配子|鞭虫|贾第")


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


def pdf_files(src: pathlib.Path):
    """返回 [(路径, 类型)]，类型 ∈ exam/answer。"""
    out = []
    for p in sorted(src.glob("*.pdf")):
        if PAPER_FILE_RE.search(p.name):
            out.append((p, "answer" if "答案" in p.name else "exam"))
    return out


def knowledge_files(src: pathlib.Path):
    return [(src / n, c) for n, c in KNOWLEDGE_FILES.items() if (src / n).exists()]


# ================================================================ OCR 阶段

_OCR = None


def _ocr_engine():
    """建立 OCR 引擎（每个进程一个）。

    ONNX Runtime 默认每个 session 都开满所有核，并行跑 N 个进程就是 N 倍超订，
    实测反而更慢。这里按 RAPIDOCR_THREADS 控制每个 session 的线程数：
    设成 1 时最省上下文切换，但单进程速度只有默认的 1/4；
    多进程时用 2 个线程配 4 个进程，实测总吞吐最快。
    """
    global _OCR
    if _OCR is None:
        import onnxruntime as ort

        threads = int(os.environ.get("RAPIDOCR_THREADS", "0") or 0)
        if threads > 0:
            _Base = ort.SessionOptions

            class _TunedOptions(_Base):
                def __init__(self, *a, **k):
                    super().__init__(*a, **k)
                    self.intra_op_num_threads = threads
                    self.inter_op_num_threads = 1
                    self.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            ort.SessionOptions = _TunedOptions

        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


OCR_CACHE_VERSION = 4   # v4 = 识别前先抹掉浅灰扫描水印


def _cache_path(stem: str, pno: int) -> pathlib.Path:
    return OCR_DIR / f"{stem}__p{pno + 1:04d}.json"


def _cache_ok(path: pathlib.Path) -> bool:
    """缓存是否是当前版本的（v1 的缓存没分栏，要重做）。"""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(data, dict) and data.get("v") == OCR_CACHE_VERSION


def _cache_lines(path: pathlib.Path):
    """读缓存的行；老格式（纯数组）也能读。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("lines") or []
    return data or []


def _ocr_one_page(job):
    """渲染一页并做 OCR，返回原始文本框（不做分栏，分栏在解析阶段做）。

    缓存原始框而不是分好栏的行：分栏算法一旦要改，不用重跑两小时的 OCR。
    """
    path, page_no, dpi = job
    import fitz
    import numpy as np

    doc = fitz.open(path)
    try:
        pix = doc[page_no].get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if img.shape[2] == 4:
            img = img[:, :, :3]
        # 先把浅灰色的扫描水印抹掉再识别：
        # 水印是斜着盖在正文上的，认出来就是一堆碎片（「8：案答.00」），
        # 混进答案字母和解析正文里。抹掉之后 OCR 认到的就是干净的正文。
        img = R.deshade(img)
        res, _ = _ocr_engine()(img)
    finally:
        doc.close()

    boxes = []
    for item in (res or []):
        box, txt, conf = item[0], item[1], item[2]
        if isinstance(conf, str):
            try:
                conf = float(conf)
            except ValueError:
                conf = 0.0
        boxes.append({
            "x": int(min(p[0] for p in box)),
            "y": int(min(p[1] for p in box)),
            "x2": int(max(p[0] for p in box)),
            "y2": int(max(p[1] for p in box)),
            "t": txt,
            "c": float(conf),
        })
    return path, page_no, boxes, int(img.shape[1])


def stage_ocr(src: pathlib.Path, jobs: int, dpi: int):
    import fitz
    import multiprocessing as mp

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    jobs_list = []
    for path, _kind in pdf_files(src):
        doc = fitz.open(path)
        n = len(doc)
        doc.close()
        for pno in range(n):
            cache = OCR_DIR / f"{path.stem}__p{pno + 1:04d}.json"
            if _cache_ok(cache):
                continue
            jobs_list.append((str(path), pno, dpi))
    if not jobs_list:
        print("[ocr] 没有需要处理的新页面")
        return
    print(f"[ocr] 待处理 {len(jobs_list)} 页，并行 {jobs}，DPI {dpi}")

    t0 = time.time()
    done = 0
    ctx = mp.get_context("spawn")
    with ctx.Pool(jobs) as pool:
        for path, pno, boxes, width in pool.imap_unordered(
                _ocr_one_page, jobs_list, chunksize=1):
            cache = OCR_DIR / f"{pathlib.Path(path).stem}__p{pno + 1:04d}.json"
            tmp = cache.with_suffix(".tmp")
            tmp.write_text(json.dumps({"v": OCR_CACHE_VERSION, "boxes": boxes,
                                        "w": width}, ensure_ascii=False),
                           encoding="utf-8")
            os.replace(tmp, cache)      # 原子替换，半截文件不会被当成完成
            done += 1
            if done % 20 == 0 or done == len(jobs_list):
                el = time.time() - t0
                rate = el / done
                print(f"[ocr] {done}/{len(jobs_list)} 页，"
                      f"已用 {el/60:.1f} 分，预计还需 "
                      f"{(len(jobs_list)-done)*rate/60:.1f} 分", flush=True)
    print(f"[ocr] 完成，用时 {(time.time()-t0)/60:.1f} 分钟")


# ================================================================ 解析阶段

def _load_page_boxes(pdf_path: pathlib.Path):
    """读某个 PDF 的全部 OCR 缓存页，返回 {页码: {"boxes":..., "w":...}}。

    连「一页都没认出来」的页也留着（boxes 为空）——这种整页漏掉的页
    只能靠重识别补回来。
    """
    stem = pdf_path.stem
    out = {}
    for f in sorted(OCR_DIR.glob(stem + "__p*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        boxes = data.get("boxes") or []
        width = data.get("w") or (max(b["x2"] for b in boxes) if boxes else 0)
        pno = int(f.stem.rsplit("__p", 1)[-1])
        out[pno] = {"boxes": boxes, "w": width}
    return out


def _mark_page_numbers(lines):
    """标出版心上方那一带的页码行。

    页码是一行孤零零的数字，印在版心外侧。正文里也有孤零零的数字
    （表格里的数值、选项里的纯数字），不能一刀切全丢，所以只认
    「页面最上面那一带」（页码比正文高，差值在 30 像素以内）。

    只标记不删除：缺号补识别要靠这一行的位置来切带子
    （漏掉的那道题常常就压在栏首、页码下面一点的地方，
    2014 专业实践能力第 56 题就是这样）。

    不挡在阅读流里会出事：2020 试卷第 38 页的页码「112」正好夹在
    第 98 题的 A、B 两个选项之间，被当成 A 选项的续行粘了上去，
    选项变成「CD4+细胞比例显著降低112」。
    """
    if not lines:
        return lines
    ymin = min(ln["y"] for ln in lines)
    for ln in lines:
        t = (ln.get("t") or "").strip()
        if ln["y"] <= ymin + 30 and L.PAGE_NUM_RE.match(t):
            ln["page_no"] = True
    return lines


# 答案册里的卷名标题行，例如「2012师（基础知识）答案」。
# 早年答案册的页眉就是卷名（2012 年那本整册只有 4 行这种标题），
# 原书少印右括号时 OCR 会照抄成「2012师（专业实践能力答案」，一并认。
VOLUME_TITLE_RE = re.compile(r"^20\d{2}\s*师\s*[（(][^）)]{0,14}[）)]?\s*答案\s*$")


def _lines_from_boxes(raw):
    """原始 OCR 框 -> 分好栏的行。"""
    pages = {}
    for pno, item in raw.items():
        boxes = item["boxes"]
        if not boxes:
            continue
        lines = L.group_lines(boxes, page_width=item["w"])
        keep = []
        for ln in lines:
            t = (ln.get("t") or "").strip()
            if L.is_noise(t):
                # 卷名标题行也是页眉，is_noise 会把它当水印丢掉。
                # 但它是老答案册里唯一能认出「第几卷从这儿开始」的标记：
                # 2012 那本答案册全书就靠这 4 行切卷，丢了整册答案全废。
                if VOLUME_TITLE_RE.match(t):
                    ln["volume_title"] = True
                    keep.append(ln)
                continue
            keep.append(ln)
        lines = _mark_page_numbers(keep)
        pages[pno] = lines
    return pages


def _load_page_lines(pdf_path: pathlib.Path):
    """读某个 PDF 的全部 OCR 缓存页，返回 {页码: 行列表}。"""
    return _lines_from_boxes(_load_page_boxes(pdf_path))


def _page_order(lines, order):
    """一页的行按指定阅读顺序排好。"""
    if order == "LR":
        return L.column_major_order(lines)
    if isinstance(order, tuple) and order[0] == "TAIL":
        cut = order[1]
        out = []
        for band in (0, 1):
            sel = [l for l in lines if (l["y"] <= cut) == (band == 0)]
            for cc in ("L", "R"):
                out.extend(sorted([l for l in sel if l.get("col") == cc],
                                  key=lambda l: l["y"]))
        return out
    return L.build_reading_order(lines)


def _flow_from_pages(pages, order="LR"):
    """把分好栏的页面排成阅读流，同时给出全页行（含居中标题）。

    order 可以是字符串（整份文件一个顺序），
    也可以是 {页码: 顺序}（逐页不同）。
    """
    flow, markers = [], []
    for pno in sorted(pages):
        lines = pages[pno]
        for ln in lines:
            if ln.get("page_no"):
                continue          # 页码不进阅读流
            item = dict(ln)
            item["page"] = pno
            item["col"] = ln.get("col", "L")
            markers.append(item)
        o = order.get(pno, "LR") if isinstance(order, dict) else order
        for ln in _page_order(lines, o):
            if ln.get("page_no"):
                continue
            if ln.get("volume_title"):
                continue          # 卷名标题不进阅读流，只当卷的分界标记
            item = dict(ln)
            item["page"] = pno
            item["col"] = ln.get("col", "L")
            flow.append(item)
    return flow, markers


def _order_penalty(flow, is_answer):
    """按编号连续性给一种阅读顺序打分，分数越小越好。

    卷内编号是连续的（1,2,3...），所以：
      - 编号往前跳（漏号）  -> 扣 1 分（多半是 OCR 没认出来，弱信号）
      - 编号往回退         -> 扣 3 分（顺序读反了，强信号）
      - 编号回到 1 且上一题 >=20 -> 新的一卷，不扣分
    """
    if is_answer:
        rxs = (L.ANS_RE, L.ANS_RE_LOOSE)
    else:
        rxs = (L.QNUM_RE,)
    seq = []
    for ln in flow:
        t = (ln.get("t") or "").strip()
        for rx in rxs:
            m = rx.match(t)
            if m:
                seq.append(int(m.group(1)))
                break
    pen = 0
    for a, b in zip(seq, seq[1:]):
        if b == a + 1:
            continue
        if b == 1 and a >= 20:
            continue                      # 新卷开始
        pen += 1 if b > a else 3
    return pen


def _choose_order(pdf_path: pathlib.Path, is_answer, pages=None):
    """选这个 PDF 的阅读顺序。

    真题册有两种版式：
      - 早年：一张纸上并排两个小书页 -> 左竖条读完再右竖条（"LR"）
      - 近年：正常双栏页，页中间还有横接缝 -> 先上半页再下半页（"BAND"）
    哪种对，用卷内编号的连续性来判：读对了编号就是连着走的。
    """
    forced = os.environ.get("PAST_PAPERS_ORDER", "").strip().upper()
    if pages is None:
        pages = _load_page_lines(pdf_path)
    if not pages:
        return "LR", pages
    if forced in ("LR", "BAND"):
        return forced, pages
    best, best_pen = "LR", None
    for order in ("LR", "BAND"):
        flow, _m = _flow_from_pages(pages, order)
        pen = _order_penalty(flow, is_answer)
        if best_pen is None or pen < best_pen:
            best, best_pen = order, pen
    return best, pages


def _page_orders(pages, is_answer, default):
    """逐页定阅读顺序。

    只有"页中间有横接缝"的页，两种顺序才会不一样；这些页正是容易读错的地方，
    所以逐页用编号连续性判一次：读对了编号就一定是连着走的。
    判不出来（编号太少/太乱）就沿用整份文件的默认顺序。
    """
    orders = {}
    for pno, lines in pages.items():
        lr = L.column_major_order(lines)
        band = L.build_reading_order(lines)
        # 候选顺序：普通双栏 / 有横接缝的双栏 / 拼接页（某栏中途结束）
        cands = [("LR", lr), ("BAND", band)]
        for cut, order in L.tail_orders(lines):
            cands.append((("TAIL", cut), order))
        scored = [(_order_penalty(o, is_answer), name) for name, o in cands]
        best_pen = min(x[0] for x in scored)
        best = [x for x in scored if x[0] == best_pen]
        if len(best) > 1:
            orders[pno] = default        # 分不出来：沿用整份文件的默认顺序
            continue
        base_pen = [x[0] for x in scored if x[1] == default]
        if base_pen and base_pen[0] <= best_pen:
            orders[pno] = default
        else:
            orders[pno] = best[0][1]
    return orders


def _page_lines(pdf_path: pathlib.Path, order="LR"):
    """读某个 PDF 的全部 OCR 缓存页，返回 (阅读流, 全页行)。"""
    pages = _load_page_lines(pdf_path)
    return _flow_from_pages(pages, order)


def _answer_restarts(flow):
    """答案流里「新一卷开始」的位置。

    每卷的答案题号都会从 1 重新开始，所以「题号回到 1 附近」就是卷的分界。
    早期卷把「答案」两个字漏掉、或者写成「1.：B」，所以放宽到 num<=3，
    并且要求上一个题号 >=20，避免把中间的跳号误当成新卷。
    """
    out = []
    prev = None
    for i, ln in enumerate(flow):
        pairs = L.parse_answer_line((ln.get("t") or "").strip())
        if not pairs:
            continue
        num = pairs[0][0]
        if (prev is None and num <= 3) or (prev is not None and num <= 3 and prev >= 20):
            out.append(i)
        prev = num
    return out


def _flow_index_after(flow, page, y, col=None):
    """流里第一个不早于 (page, y) 的行下标。

    一页有左右两栏，流里的顺序是「左栏读完再右栏」，不是按 y 排的，
    所以必须带上栏位一起找：右栏 y=1300 的那一行，在流里排在
    左栏 y=1500 的那几行后面。只按 y 找会把卷的边界算到卷中间去。
    """
    for i, ln in enumerate(flow):
        if ln["page"] > page:
            break
        if ln["page"] < page:
            continue
        if col is not None and ln.get("col") != col:
            continue
        if ln["y"] >= y:
            return i
    return len(flow)


def _flow_index_of(flow, page, y, tol=3, col=None):
    """流里对应 (page, y) 的行下标（找不到返回 None）。"""
    for i, ln in enumerate(flow):
        if ln["page"] == page and abs(ln["y"] - y) <= tol:
            if col is not None and ln.get("col") != col:
                continue
            return i
    return None


def _paper_name_of(text):
    m = L.PAPER_NAME_RE.search(text or "")
    return m.group(1) if m else None


def _page_paper_name(markers, page):
    """某一页上的卷名（试卷侧用）：裸卷名行，或「基础知识（I）」这种标题行。"""
    for m in markers:
        if m["page"] != page:
            continue
        t = (m.get("t") or "").strip()
        mb = L.BARE_PAPER_RE.match(t)
        if mb:
            return mb.group(1)
        mm = re.match(r"^[\s　]*(相关专业知识|专业实践能力|专业知识|基础知识)\s*[（(]", t)
        if mm:
            return mm.group(1)
    return None


def _page_year(markers, page):
    """某一页上出现的年份（试卷侧标题行里带的年份）。"""
    for m in markers:
        if m["page"] != page:
            continue
        t = (m.get("t") or "").strip()
        if len(t) > 40:
            continue
        my = re.search(r"(20\d\d)", t)
        if my:
            return int(my.group(1))
    return None


# 说明段：「以下每一道考题…」。OCR 偶尔把「一」认丢（「以下每道」），
# 或者认成两根横杠（「以下每--道」），所以「每」和「道」之间允许夹几个杂字符。
# 认不出来说明段就等于认不出卷的边界：
# 2011 专业实践能力、2012 基础知识这两卷都是这么丢的，
# 结果整卷的题目被算到别的卷名下，答案也就配错了。
INSTR_RE_LOOSE = re.compile(r"以下每.{0,4}?道")


def _is_instruction(text):
    """是不是一卷开头的说明段。"""
    t = text or ""
    if L.INSTRUCTION_MARK in t:
        return True
    return bool(INSTR_RE_LOOSE.search(t))


def _segment_volumes(flow, markers, is_answer, default_year):
    """把一个 PDF 切成若干个卷段。

    返回 [{year, paper_name, title_guessed, start, end}]，start/end 是流的下标。

    试卷侧：卷与卷之间是「说明段」（以下每一道…），说明段就是分界。
    答案侧：卷与卷之间是题号归 1，卷名写在卷首的标题行上。
    """
    segs = []

    if not is_answer:
        # 说明段（取自全部行，居中栏的说明段也要算上）
        instrs = [m for m in markers if _is_instruction(m.get("t") or "")]
        instrs.sort(key=lambda m: (m["page"], m["y"]))
        starts = []
        for m in instrs:
            idx = _flow_index_after(flow, m["page"], m["y"], m.get("col"))
            if starts and idx <= starts[-1][0]:
                continue                      # 同一段说明被拆成多行
            starts.append((idx, m["page"], m["y"]))
        for k, (idx, page, y) in enumerate(starts):
            name = _page_paper_name(markers, page)
            year = _page_year(markers, page) or default_year
            guessed = name is None
            if guessed:
                name = L.PAPER_NAMES[min(k, 3)]
            segs.append({
                "year": year, "paper_name": name, "title_guessed": guessed,
                "start": idx, "end": starts[k + 1][0] if k + 1 < len(starts) else len(flow),
            })
        return segs

    # ---- 答案侧 ----
    titles = []
    for m in markers:
        t = (m.get("t") or "").strip()
        if not L.is_paper_title(t):
            continue
        ym = re.search(r"(20\d\d)", t)
        titles.append({
            "page": m["page"], "y": m["y"], "col": m.get("col"),
            "paper": _paper_name_of(t),
            "year": int(ym.group(1)) if ym else None,
        })
    titles.sort(key=lambda t: (t["page"], t["y"]))
    cands = _answer_restarts(flow)

    if titles:
        prev = -1
        for ti in titles:
            start = None
            for c in cands:
                if c > prev and flow[c]["page"] >= ti["page"]:
                    start = c
                    break
            if start is None:
                continue
            prev = start
            segs.append({
                "year": ti["year"] or default_year,
                "paper_name": ti["paper"],
                "title_guessed": False,
                "start": start,
                "end": len(flow),
                "title": ti,
            })
    else:
        # 没有卷名标题（2023 年）：按固定卷序推断
        for k, c in enumerate(cands):
            segs.append({
                "year": default_year,
                "paper_name": L.PAPER_NAMES[min(k, 3)],
                "title_guessed": True,
                "start": c,
                "end": cands[k + 1] if k + 1 < len(cands) else len(flow),
            })

    # 跨年：文件末尾常常是下一年第一卷（2010/2011/2012 的答案和试卷都是合订的）。
    # 标题里写了年份的就以年份为准，并把它之前的卷截断在标题处。
    for k, seg in enumerate(segs):
        ti = seg.get("title")
        if not ti or ti["year"] is None:
            continue
        if ti["year"] == seg["year"]:
            continue
        cut = _flow_index_of(flow, ti["page"], ti["y"], col=ti.get("col"))
        if cut is None:
            cut = _flow_index_after(flow, ti["page"], ti["y"], ti.get("col"))
        segs[k]["year"] = ti["year"]
        segs[k]["_cut_at"] = cut
        if k > 0:
            segs[k - 1]["end"] = min(segs[k - 1].get("end", len(flow)), cut)

    # 段落边界收口
    for k, seg in enumerate(segs):
        if k + 1 < len(segs):
            seg["end"] = min(seg.get("end", len(flow)), segs[k + 1]["start"])
        else:
            seg["end"] = seg.get("end", len(flow))
        seg.pop("_cut_at", None)
    return segs


# ================================================================ 漏行恢复

def _file_state(path, kind, default_year):
    """一个 PDF 的解析状态。

    raw   : 原始 OCR 框（只读）
    extra : 重识别补回来的框
    其余（行 / 阅读流 / 卷段）都由 raw+extra 派生，改完框重算一遍就行。
    """
    raw = _load_page_boxes(path)
    pages = _lines_from_boxes(raw)
    default_order, _ = _choose_order(path, kind == "answer", pages)
    st = {
        "path": path, "kind": kind, "year": default_year,
        "raw": raw, "pages": pages,
        "default_order": default_order,
        "orders": {}, "flow": [], "markers": [], "segs": [],
        # 重识别补回来的行：{页码: [行...]}，由 _rebuild 并进 pages
        "extra_rows": {},
        # 重识别认回来的题号：{页码: {(栏, y): 新文字}}，由 _rebuild 贴回原行
        "patches": {},
    }
    _rebuild(st)
    return st


def _merge_extra_rows(st, pages):
    """把重识别补回来的行并进页面行里。

    重识别是在缺号附近重新认一遍同一块版面，认出来的行带着完整的题号
    （「79.检测HBsAg最常用的方法是（」），而原来的 OCR 把题号那一小块
    漏掉或认成了别的字。把这些行按位置插回页面，后续的卷段切分和解析
    就能像正常行一样处理它们。
    """
    extra = st.get("extra_rows") or {}
    for pno, rows in extra.items():
        if not rows:
            continue
        lines = list(pages.get(pno, []))
        lines.extend(rows)
        lines.sort(key=lambda l: (l.get("col", "L"), l["y"]))
        pages[pno] = lines
    return pages


def _apply_patches(st, pages):
    """把重识别补回来的题号贴回原来的行。

    行是每次从原始 OCR 框重新算出来的（_lines_from_boxes 会新建一批对象），
    所以补丁不能挂在行对象上，只能按 (栏, y) 记住，重建之后再贴回去。
    少了这一步，补好的题号会在 _rebuild 里被丢掉，
    结果就是「题号找回来了，题却还是缺着」。
    """
    patches = st.get("patches") or {}
    for pno, items in patches.items():
        lines = pages.get(pno) or []
        by_key = {(_line_key(ln)): ln for ln in lines}
        for key, text in items.items():
            ln = by_key.get(key)
            if ln is not None:
                ln["t"] = text
    return pages


def _rebuild(st):
    """重算 行 -> 阅读流 -> 卷段。"""
    pages = _lines_from_boxes(st["raw"])
    pages = _apply_patches(st, pages)
    st["pages"] = _merge_extra_rows(st, pages)
    is_answer = (st["kind"] == "answer")
    st["orders"] = _page_orders(pages, is_answer, st["default_order"])
    st["flow"], st["markers"] = _flow_from_pages(pages, st["orders"])
    st["segs"] = _segment_volumes(st["flow"], st["markers"], is_answer, st["year"])


def _absorb(index, st):
    """把一个文件的卷段并进 index。"""
    for seg in st["segs"]:
        lines = st["flow"][seg["start"]:seg["end"]]
        key = (seg["year"], seg["paper_name"])
        slot = index.setdefault(key, {"exam": [], "answer": {}, "sources": []})
        slot["sources"].append({
            "file": st["path"].name,
            "page_from": lines[0]["page"] if lines else 0,
            "page_to": lines[-1]["page"] if lines else 0,
            "title_guessed": seg["title_guessed"],
        })
        if st["kind"] == "answer":
            answers, _order = L.parse_answers(lines)
            # 同一卷跨文件重复：按题号合并，保留解析更长的那份
            for num, val in answers.items():
                old = slot["answer"].get(num)
                if old is None or len(val["analysis"]) > len(old["analysis"]):
                    slot["answer"][num] = val
        else:
            slot["exam"].extend(L.parse_questions(
                lines, paper_name=seg["paper_name"], year=seg["year"]))


# OCR 常把「答案」两个字认花（「管案」「笨案」「容案」），或者把答案行和
# 上一行的正文粘在一起（「…大量水22．答案：B」）。行首的正则匹配不上时，
# 只能按题号在行里找「答/案」后面那个字母。
_LOOSE_ANS_RES = (
    re.compile(r"[答案][^0-9A-Za-z]{0,2}([A-Ea-e])(?![A-Za-z])"),
    re.compile(r"[:：][\s]{0,2}([A-Ea-e])(?![A-Za-z])"),
)


def _loose_answer_letters(text, want):
    """在一行文本里找题号 want 对应的答案字母。

    返回找到的候选字母（可能一个都没有）。行首不是题号时也能用：
    「红蛋白外…大量水22．答案：B」里的 22 就是这么找出来的。
    """
    t = text or ""
    out = []
    for m in re.finditer(r"(?<!\d)(\d{1,3})(?!\d)", t):
        if int(m.group(1)) != want:
            continue
        seg = t[m.end():m.end() + 14]
        for rx in _LOOSE_ANS_RES:
            mm = rx.search(seg)
            if mm:
                out.append(mm.group(1).upper())
                break
    return out


def _pick_letter(strict, loose):
    """从候选里挑一个答案字母。候选互相打架就不猜。"""
    for group in (strict, loose):
        if not group:
            continue
        uniq = set(group)
        if len(uniq) == 1:
            return group[0]
        return ""
    return ""


def _volume_view(index):
    """每个卷去重后的题号集合 / 答案号集合。"""
    view = {}
    for key, slot in index.items():
        qnums = {q["num"] for q in slot["exam"]}
        anums = {n for n, v in slot["answer"].items() if v["answer"]}
        view[key] = (qnums, anums)
    return view


def _expected_counts(view):
    """每个卷「应该有多少题」。

    试卷侧和答案侧互为参照，取两边更大的那个；
    再用全卷题数的众数当公称题数，这样「末尾几题整页没认出来」
    这种尾部缺号也能被发现。
    """
    exp = {}
    for key, (qnums, anums) in view.items():
        exp[key] = max(len(qnums), len(anums))
    if exp:
        from collections import Counter
        floor = Counter(exp.values()).most_common(1)[0][0]
        for key in exp:
            exp[key] = max(exp[key], floor)
    return exp


def _volume_gaps(view, expected):
    """每个卷缺哪些号。返回 {(key, kind): [缺号]}，kind ∈ exam/answer。"""
    gaps = {}
    for key, (qnums, anums) in view.items():
        for kind, nums in (("exam", qnums), ("answer", anums)):
            if not nums:
                continue
            hi = max(max(nums), expected.get(key, 0))
            missing = [n for n in range(1, hi + 1) if n not in nums]
            if missing:
                gaps[(key, kind)] = missing
    return gaps


def _gap_metric(view):
    """内部缺口数（只看各卷自身解析出来的范围）。

    这是个稳定的指标：公称题数带来的尾部缺号不算在内，
    用来判断「重识别之后是不是更糟了」。
    """
    total = 0
    for _key, (qnums, anums) in view.items():
        for nums in (qnums, anums):
            if not nums:
                continue
            hi = max(nums)
            total += sum(1 for n in range(1, hi + 1) if n not in nums)
    return total


def _key_segments(states, key):
    """所有文件里属于某个卷的卷段。"""
    for st in states.values():
        for seg in st["segs"]:
            if (seg["year"], seg["paper_name"]) == key:
                yield st, seg


def _key_num_seq(states, key, is_answer):
    """某个卷里出现的所有题号 -> [(题号, 文件名, 页码, 栏, y)]。"""
    seq = []
    want_kind = "answer" if is_answer else "exam"
    for st, seg in _key_segments(states, key):
        # 只看对应类型的文件：答案册里的「12.答突尔」也会被 QNUM_RE
        # 当成题号 12，混进来会把页码指错
        if st["kind"] != want_kind:
            continue
        for ln in st["flow"][seg["start"]:seg["end"]]:
            t = (ln.get("t") or "").strip()
            if is_answer:
                for num, _a, _x in L.parse_answer_line(t):
                    seq.append((num, st["path"].name, ln["page"],
                                ln.get("col", "L"), ln.get("y", 0)))
            else:
                m = L.QNUM_RE.match(t)
                if m:
                    seq.append((int(m.group(1)), st["path"].name, ln["page"],
                                ln.get("col", "L"), ln.get("y", 0)))
    return seq


def _volume_cols(states, key, is_answer):
    """某个卷在哪些 (文件, 页) 上占哪一栏。

    一页答案册常常左右两栏是两个卷。找缺号那一行时必须按栏过滤，
    否则会把隔壁卷同一题号的答案当成自己的。
    """
    out = {}
    for num, fname, page, col, _y in _key_num_seq(states, key, is_answer):
        out.setdefault((fname, page), set()).add(col)
    return out


def _gap_pairs(states, key, is_answer, missing):
    """缺号前后邻居所在的 (文件名, 页码)。

    缺的那一行就夹在前后邻居之间，所以重识别这两页就够了。
    前后邻居隔了好几页时，中间夹着的页也一并算上（整页漏掉的情况）。
    """
    seq = _key_num_seq(states, key, is_answer)
    if not seq:
        return set()
    out = set()
    for g in missing:
        prev = nxt = None
        for num, fname, page, _col, _y in seq:
            if num < g and (prev is None or num > prev[0]):
                prev = (num, fname, page)
            elif num > g and (nxt is None or num < nxt[0]):
                nxt = (num, fname, page)
        if prev:
            out.add((prev[1], prev[2]))
        if nxt:
            out.add((nxt[1], nxt[2]))
        if not prev:
            out.add((seq[0][1], seq[0][2]))
        if not nxt:
            out.add((seq[-1][1], seq[-1][2]))
        # 前后邻居在同一文件、隔了不止一页：中间的页也补上
        if prev and nxt and prev[1] == nxt[1] and prev[2] != nxt[2]:
            lo, hi = sorted((prev[2], nxt[2]))
            for p in range(lo, min(hi, lo + 4) + 1):
                out.add((prev[1], p))
    return out


def _page_size(st):
    """页面在 200dpi 下的像素尺寸。"""
    import fitz
    doc = fitz.open(st["path"])
    try:
        page = doc[0]
        k = 200 / 72
        return int(page.rect.height * k), int(page.rect.width * k)
    finally:
        doc.close()


def _all_pages(st):
    """一个文件的所有页码（1 起）。"""
    import fitz
    doc = fitz.open(st["path"])
    n = len(doc)
    doc.close()
    return range(1, n + 1)


# 带子最高多少像素。再高就切成好几段，一段一段认。
BAND_MAX_H = 420


def _col_span(st, page, col):
    """某一栏在页面上的 x 范围。"""
    lines = [ln for ln in st["pages"].get(page, []) if ln.get("col") == col]
    if not lines:
        return None
    x0 = max(0, min(ln["x"] for ln in lines) - 14)
    x1 = max(ln["x2"] for ln in lines) + 14
    return x0, x1


def _bands_in(st, page, col, y0, y1):
    """把 [y0, y1) 切成若干条带子。"""
    span = _col_span(st, page, col)
    if not span:
        return []
    x0, x1 = span
    out = []
    a = int(y0)
    b = int(y1)
    while a < b:
        c = min(b, a + BAND_MAX_H)
        out.append((a, c, x0, x1))
        a = c
    return out


def _gap_bands(states, key, is_answer, missing):
    """每个缺号该去哪条带子上找。

    缺的那一行就夹在前后两个已知题号之间，所以带子取它们中间的空白。
    返回 {文件名: {页码: [(y0, y1, x0, x1), ...]}}。
    """
    seq = _key_num_seq(states, key, is_answer)
    by_name = {st["path"].name: st for st in states.values()}
    out = {}
    for g in missing:
        prev = nxt = None
        for num, fname, page, col, y in seq:
            if num < g and (prev is None or num > prev[0]):
                prev = (num, fname, page, col, y)
            elif num > g and (nxt is None or num < nxt[0]):
                nxt = (num, fname, page, col, y)
        def add(fname, pno, band):
            slot = out.setdefault(fname, {}).setdefault(pno, {"bands": [], "nums": set()})
            if band not in slot["bands"]:
                slot["bands"].append(band)
            slot["nums"].add(g)

        def tail_of(e):
            """上一题所在栏的尾巴：缺的那道题可能就压在这一栏的末尾。"""
            st = by_name.get(e[1])
            if st is None:
                return
            lines = [ln for ln in st["pages"].get(e[2], [])
                     if ln.get("col") == e[3]]
            bottom = max((ln.get("y2", ln.get("y", 0)) for ln in lines),
                          default=e[4] + 200)
            for band in _bands_in(st, e[2], e[3], e[4] + 4, bottom + 10):
                add(e[1], e[2], band)

        def head_of(e):
            """下一题所在栏的开头：缺的那道题也可能压在栏首（跨页时最常见）。"""
            st = by_name.get(e[1])
            if st is None:
                return
            lines = [ln for ln in st["pages"].get(e[2], [])
                     if ln.get("col") == e[3]]
            top = min((ln.get("y", 0) for ln in lines), default=0)
            for band in _bands_in(st, e[2], e[3], top - 10, e[4] - 4):
                add(e[1], e[2], band)

        if prev and nxt and prev[1] == nxt[1] and prev[2] == nxt[2] \
                and prev[3] == nxt[3] and nxt[4] > prev[4]:
            st = by_name.get(prev[1])
            if st is not None:
                for band in _bands_in(st, prev[2], prev[3], prev[4] + 4, nxt[4] - 4):
                    add(prev[1], prev[2], band)
        elif prev and nxt:
            # 缺的那道题跨页/跨栏了：上一题在上一页的栏尾，下一题在下一页的栏头。
            # 两头都得重识别，只认一头的话，跨页的那道题永远找不回来
            # （2019 基础知识第 10 题就是这样丢的：题号行在第 2 页左栏的顶部，
            #   而带子只切到了第 1 页右栏的尾巴）。
            tail_of(prev)
            head_of(nxt)
        elif prev:
            tail_of(prev)
        elif nxt:
            head_of(nxt)
    return out


def _blank_pages(st):
    """整页一个框都没认出来的页。页号和解析层一致，从 1 起。"""
    import fitz
    doc = fitz.open(st["path"])
    n = len(doc)
    doc.close()
    return {p for p in range(1, n + 1)
            if not st["raw"].get(p, {}).get("boxes")}


def _reocr_bands_job(job):
    """子进程里跑一页若干条带子的重识别。job = (路径, stem, 页码, 带子, 旧框)。"""
    path_str, stem, pno, bands, old = job
    import fitz
    doc = fitz.open(path_str)
    try:
        engine = _ocr_engine()
        # pno 是 1 起的页号，fitz 是 0 起的下标
        new = R.reocr_bands(BACKEND, stem, pno - 1, doc, old, engine, bands)
        return path_str, pno, new
    finally:
        doc.close()


def _recover_pages(states, cand, jobs=4):
    """对候选带子做多阈值重识别，返回 {(文件名, 页码): 新框列表}。

    cand = {文件名: {页码: [带子, ...]}}。

    所有文件共用一个进程池：ONNX 模型每个进程加载一次，
    28 个文件各开一次池太浪费。
    """
    import multiprocessing as mp

    todo = []
    for st in states.values():
        fname = st["path"].name
        for pno, bands in sorted((cand.get(fname) or {}).items()):
            if not bands:
                continue
            item = st["raw"].get(pno)
            old = item["boxes"] if item else []
            todo.append((str(st["path"]), st["path"].stem, pno, bands, old))
    if not todo:
        return {}

    if jobs <= 1:
        results = [_reocr_bands_job(job) for job in todo]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(jobs) as pool:
            results = list(pool.imap_unordered(_reocr_bands_job, todo, chunksize=1))

    out = {}
    for path_str, pno, new in results:
        if new:
            # key 用文件名，和 _gap_pairs / _select_* 里的 (文件名, 页码) 对齐
            out[(pathlib.Path(path_str).name, pno)] = new
    return out


def _option_pairs(text):
    """只认行首（前面最多几个杂字）开始的选项行。"""
    t = (text or "").strip()
    if not t:
        return []
    if not L.OPT_MARK_RE.search(t[:6]):
        return []
    return L.split_option_line(t)


def _select_answers(states, gaps, cands):
    """答案册：把缺号的那一行找回来。

    只取缺号那一行，直接补成答案条目；不把补的框塞回页面重新解析 ——
    塞回去会改变分栏和阅读顺序，已经认对的答案会被带偏
    （2014 专业知识 77 的答案就从 C 变成了 B）。

    找法从严到宽：
      1. 整行就是「22.答案：B」这种标准答案行；
      2. 在行内按题号找「答/案 + 字母」（旧框把答案行和上一行的正文
         粘在一起时，行首的正则匹配不上）；
      3. 同上，但只看重识别出来的新框。
    候选字母互相打架时不猜，宁可留空。
    """
    out = {}
    by_name = {st["path"].name: st for st in states.values()}
    for (key, kind), missing in gaps.items():
        if kind != "answer":
            continue
        want = set(missing)
        cols = _volume_cols(states, key, True)
        for fname, page in sorted(_gap_pairs(states, key, True, missing)):
            st = by_name.get(fname)
            if st is None:
                continue
            allow = cols.get((fname, page))
            if allow is not None:
                # 接缝那一栏（col='C'）里常常混着答案行：答案行从接缝中间起头，
                # 分栏时分到「通栏」去了，阅读流里没有它，那道题的答案就丢了
                # （2013 基础知识 18/49/65、2017 专业实践能力 23 都是这样）。
                allow = set(allow) | {"C"}
            lines, rows = _page_rows_split(st, page, cands.get((fname, page)))
            old_texts = [ln.get("t") or "" for ln in lines
                         if allow is None or ln.get("col") in allow]
            new_texts = [r.get("t") or "" for r in rows
                         if allow is None or r.get("col") in allow]
            for num in sorted(want):
                strict, loose = [], []
                for text in old_texts:
                    got = L.parse_answer_line(text.strip())
                    hit = [x for x in got if x[0] == num and x[1]]
                    if hit:
                        strict.append(hit[0][1].upper())
                        continue
                    loose.extend(_loose_answer_letters(text, num))
                for text in new_texts:
                    got = L.parse_answer_line(text.strip())
                    hit = [x for x in got if x[0] == num and x[1]]
                    if hit:
                        strict.append(hit[0][1].upper())
                        continue
                    loose.extend(_loose_answer_letters(text, num))
                letter = _pick_letter(strict, loose)
                if not letter:
                    continue
                letters = [c for c in letter if c in "ABCDE"]
                if not letters or len(letters) != len(letter):
                    continue
                out.setdefault(key, {}).setdefault(
                    num, {"answer": ",".join(letters), "analysis": ""})
                want.discard(num)
            if not want:
                break
    return out


def _page_rows(st, pno, extra_boxes):
    """一页的行 = 原有行 + 重识别补的行（补的行按 x 归到最近的栏）。"""
    lines, rows = _page_rows_split(st, pno, extra_boxes)
    out = lines + rows
    out.sort(key=lambda l: (l.get("col", "L"), l["y"]))
    return out


def _page_rows_split(st, pno, extra_boxes):
    """一页的「原有行」和「重识别补的行」分开返回。

    补的框先按 x 归到离它最近的原有行的栏里，再在栏内拼行 ——
    直接整页拼行会把左右两栏（常常是两个卷）粘成一行。
    """
    lines = list(st["pages"].get(pno, []))
    if not extra_boxes:
        return lines, []
    by_col = {}
    for b in extra_boxes:
        best = None
        for ln in lines:
            if best is None or abs(ln["x"] - b["x"]) < abs(best["x"] - ln["x"]):
                best = ln
        col = best.get("col", "L") if best else "L"
        by_col.setdefault(col, []).append(b)
    rows = []
    for col, boxes in by_col.items():
        for r in L.merge_same_row(boxes):
            r["col"] = col
            rows.append(r)
    return lines, rows


def _question_head(text, want=None):
    """从一行里认出「题号 + 题干」。

    标准写法是行首的「51. 下列…」。但 OCR 常把相邻栏的文字粘上来
    （「贡51血氨升高的原因是」「A.异位妊娠79。患者男…」），这时题号
    不在行首，只在 want（要补的缺号）里才认。
    """
    m = L.QNUM_RE.match(text)
    if m:
        return int(m.group(1)), m.group(2).strip()
    if not want:
        return None, ""
    for num in sorted(want):
        mm = re.search(r"(?<!\d)" + str(num) + r"\s*[.、．]\s*", text)
        if not mm:
            continue
        rest = text[mm.end():].strip()
        if rest:
            return num, rest
    return None, ""


def _extract_questions(rows, want=None):
    """从一页的行里切出 [(题号, 题干, 选项)]。"""
    out = []
    cur = None
    for row in rows:
        text = (row.get("t") or "").strip()
        if not text:
            continue
        num, stem = _question_head(text, want)
        if num is not None:
            if cur is not None and num <= cur["num"]:
                continue                     # 题号往回退，多半是续行
            cur = {"num": num, "stem": stem, "options": {}}
            out.append(cur)
            continue
        if cur is None:
            continue
        pairs = _option_pairs(text)
        if pairs:
            for letter, val in pairs:
                if letter in cur["options"] and len(cur["options"]) >= 4:
                    continue
                cur["options"][letter] = val
            continue
        cur["stem"] = (cur["stem"] + text).strip()
    return out


def _select_questions(states, gaps, cands):
    """试卷：从重识别的行里挑出「缺号对应的那一道题」。"""
    out = {}
    by_name = {st["path"].name: st for st in states.values()}
    for (key, kind), missing in gaps.items():
        if kind != "exam":
            continue
        year, paper_name = key
        want = set(missing)
        cols = _volume_cols(states, key, False)
        for fname, page in sorted(_gap_pairs(states, key, False, missing)):
            st = by_name.get(fname)
            if st is None:
                continue
            allow = cols.get((fname, page))
            lines, rows = _page_rows_split(st, page, cands.get((fname, page)))
            keep = [ln for ln in lines
                    if allow is None or ln.get("col") in allow]
            keep += [r for r in rows if allow is None or r.get("col") in allow]
            keep.sort(key=lambda l: (l.get("col", "L"), l["y"]))
            for item in _extract_questions(keep, want):
                num, stem, opts = item["num"], item["stem"], item["options"]
                if num not in want:
                    continue
                if not stem or len(opts) < 2:
                    continue                 # 题干或选项不全，先不补
                out.setdefault(key, {})[num] = {
                    "num": num, "stem": stem, "options": opts,
                    "answer": "", "analysis": "", "conf": 1.0,
                    "shared": False, "year": year, "paper_name": paper_name,
                }
                want.discard(num)
            if not want:
                break
    return out


def _inject(index, extra_ans, extra_q):
    """把补出来的答案/题目并进 index。"""
    for key, d in extra_ans.items():
        slot = index.setdefault(key, {"exam": [], "answer": {}, "sources": []})
        for num, val in d.items():
            old = slot["answer"].get(num)
            if old is None or len(val["analysis"]) > len(old["analysis"]):
                slot["answer"][num] = val
    for key, d in extra_q.items():
        slot = index.setdefault(key, {"exam": [], "answer": {}, "sources": []})
        have = {q["num"] for q in slot["exam"]}
        for num, q in d.items():
            if num not in have:
                slot["exam"].append(q)


def _norm_text(t):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", t or "")


def _dedupe_boxes(boxes, y_tol=10):
    """重识别经常把同一行认两遍（整行一个框 + 半个行一个框），
    留下更完整的那份。"""
    out = []
    for b in sorted(boxes, key=lambda b: (b["y"], b["x"])):
        hit = None
        for o in out:
            if abs(o["y"] - b["y"]) > y_tol:
                continue
            ix = min(o["x2"], b["x2"]) - max(o["x"], b["x"])
            if ix <= 0:
                continue
            area = min(o["x2"] - o["x"], b["x2"] - b["x"])
            if ix < 0.6 * area:
                continue
            a, c = _norm_text(o["t"]), _norm_text(b["t"])
            if not a or not c:
                continue
            if a in c or c in a:
                hit = o
                break
            if difflib.SequenceMatcher(None, a, c).ratio() >= 0.75:
                hit = o
                break
        if hit is None:
            out.append(b)
        elif (len(_norm_text(b["t"])), b.get("c", 0)) > \
                (len(_norm_text(hit["t"])), hit.get("c", 0)):
            out[out.index(hit)] = b
    return out


def _num_prefix(num):
    return f"{num}."


def _with_num(text, num):
    """给一行题干加上题号（原来已经认出题号的就把题号换掉）。"""
    t = (text or "").strip()
    m = re.match(r"^\s*\d{1,3}\s*[.、．]\s*", t)
    if m:
        t = t[m.end():]
    return _num_prefix(num) + t


def _line_key(ln):
    """行的稳定标识：栏 + y。

    行对象每次重建都会换一批，只能用它来定位；
    同一份 raw 上 (栏, y) 是稳定的。
    """
    return (ln.get("col", "L"), int(round(ln.get("y", 0))))


def _line_near(lines, col, y0, y1, tol=14, skip_opts=False):
    """找 y 位置最接近、同一栏的那一行。

    skip_opts=True 时跳过选项行（「A.…」「B.…」）：
    题号框要贴的是题干行，绝不是上一题的选项行。
    """
    best = None
    for ln in lines:
        if ln.get("col", "L") != col:
            continue
        if skip_opts and L.OPT_RE.match((ln.get("t") or "").strip()):
            continue
        ly0 = ln.get("y", 0)
        ly1 = ln.get("y2", ly0 + 30)
        if ly0 <= y1 and ly0 + 30 >= y0:
            dist = 0
        elif ly0 > y1:
            dist = ly0 - y1
        else:
            dist = y0 - ly1
        if dist > tol:
            continue
        if best is None or dist < best[0]:
            best = (dist, ln)
    return best[1] if best else None


def _line_same_row(ln, box):
    """这一行和这个框是不是同一行（竖直方向上真的重叠）。

    OCR 的行高和框高不完全一样，给 6 像素的宽容。
    """
    if ln is None or box is None:
        return None
    ly0 = ln.get("y", 0)
    ly1 = ln.get("y2", ly0 + 30)
    by0 = box.get("y", 0)
    by1 = box.get("y2", by0 + 30)
    if ly0 <= by1 - 6 and ly1 >= by0 + 6:
        return ln
    return None


def _inject_gap_rows(states, want_by_page, cands):
    """把重识别认出来的题号并回页面。

    缺的那几道题，问题往往不是「整行没认出来」，而是「题号那一小块没认对」：
    2022 相关专业知识第 79 题，题干是「检测HBsAg最常用的方法是（）」，
    题号被 OCR 读成了别的字，整行就没了题号，解析层自然认不出这是第 79 题。
    重识别在同一块版面上重新认一遍，能把题号认回来。

    这里只取重识别认出来的**题号**，题干还是用原来的 OCR（原来的更全）：
    认出来的题号后面没有汉字时，说明只认到了题号那一小块，
    把题号补到对应那一行的开头就行。
    """
    by_name = {st["path"].name: st for st in states.values()}
    touched = set()
    for (fname, pno), nums in sorted(want_by_page.items()):
        st = by_name.get(fname)
        boxes = cands.get((fname, pno))
        if st is None or not boxes:
            continue
        boxes = _dedupe_boxes(boxes)
        lines = st["pages"].get(pno, [])
        have = set()
        for ln in lines:
            m = L.QNUM_RE.match((ln.get("t") or "").strip())
            if m:
                have.add(int(m.group(1)))
        add = []
        patch = {}
        for b in boxes:
            t = (b.get("t") or "").strip()
            m = re.match(r"^\s*(\d{1,3})\s*[.、．]\s*(.*)$", t)
            if not m:
                continue
            num = int(m.group(1))
            rest = m.group(2).strip()
            if num not in nums or num in have:
                continue
            if not L.CJK_RE.search(rest):
                rest = ""              # 只认到题号那一小块
            col = _nearest_col(lines, b)
            target = _line_near(lines, col, b["y"], b.get("y2", b["y"] + 30),
                                skip_opts=True)
            cur = (target.get("t") or "").strip() if target is not None else ""
            nrest, ncur = _norm_text(rest), _norm_text(cur)
            # 「同一行」= 竖直方向上和这个框真的重叠。
            # 重识别认出的是原文整行漏掉的一行时，旁边的行不能被顶掉
            # （2014 相关专业知识 20：顶掉「的（　）」，题干尾巴就没了）。
            target_same = _line_same_row(target, b)
            use = None
            if target_same is not None:
                use = target_same
            elif (target is not None and nrest and len(nrest) >= 4
                  and nrest in ncur):
                # 行位置差了一点，但文字对得上：就是这一行
                use = target
            if use is not None:
                ncur2 = _norm_text((use.get("t") or "").strip())
                if not rest:
                    # 只认到了题号那一小块，把题号补到这一行前面
                    patch[_line_key(use)] = _with_num(
                        (use.get("t") or "").strip(), num)
                elif nrest and nrest in ncur2:
                    # 原文这一行已经够全，只要把题号补上
                    patch[_line_key(use)] = _with_num(
                        (use.get("t") or "").strip(), num)
                elif ncur2 and len(ncur2) >= 2 and ncur2 in nrest:
                    # 重识别这一行更全，用它换掉原来那一行
                    patch[_line_key(use)] = _with_num(rest, num)
                else:
                    use = None
            if use is None:
                # 原文这一行整个漏了，把重识别认出来的整行补进去
                row = dict(b)
                row["t"] = _with_num(rest, num) if rest else _num_prefix(num)
                row["col"] = col
                add.append(row)
            have.add(num)
        if not add and not patch:
            continue
        if patch:
            # 记到 st 上，_rebuild 重建行之后再贴回去
            st.setdefault("patches", {}).setdefault(pno, {}).update(patch)
        if add:
            st.setdefault("extra_rows", {}).setdefault(pno, []).extend(add)
        touched.add(fname)
    for fname in sorted(touched):
        _rebuild(by_name[fname])
    return len(touched)


def _nearest_col(lines, box):
    best = None
    for ln in lines:
        d = abs(ln.get("x", 0) - box.get("x", 0))
        if best is None or d < best[0]:
            best = (d, ln.get("col", "L"))
    return best[1] if best else "L"


def _recover_gaps(states, rounds=4, jobs=4):
    """把整页 OCR 漏掉的行找回来。

    整页 OCR 偶尔会整行漏检（2017 基础知识第 4 题的「4.答案：C。」就没认出来），
    导致答案册缺号、试卷缺题。这里用多阈值重识别把漏掉的行捞回来，
    只补缺的那一条，不动已经解析好的内容。
    """
    extra_ans, extra_q = {}, {}
    for rnd in range(rounds):
        index = {}
        for st in states.values():
            _absorb(index, st)
        _inject(index, extra_ans, extra_q)
        view = _volume_view(index)
        expected = _expected_counts(view)
        gaps = _volume_gaps(view, expected)
        if not gaps:
            print("[parse] 没有缺口了")
            break

        want_by_page = {}
        cand = {}
        for st in states.values():
            for pno in sorted(_blank_pages(st)):
                # 整页一个框都没有：整页重识别
                cand.setdefault(st["path"].name, {}).setdefault(pno, []).append(
                    (0, _page_size(st)[0], 0, _page_size(st)[1]))
        for (key, kind), missing in gaps.items():
            bands = _gap_bands(states, key, kind == "answer", missing)
            for fname, pages in bands.items():
                for page, slot in pages.items():
                    dest = cand.setdefault(fname, {}).setdefault(page, [])
                    for band in slot["bands"]:
                        if band not in dest:
                            dest.append(band)
                    if kind == "exam":
                        want_by_page.setdefault((fname, page), set()).update(slot["nums"])
        cand = {f: p for f, p in cand.items() if p}
        if not cand:
            break

        cands = _recover_pages(states, cand, jobs=jobs)
        if not cands:
            print("[parse] 重识别没有捞到新内容")
            break
        n_inj = _inject_gap_rows(states, want_by_page, cands)
        if n_inj:
            print(f"[parse] 重识别把 {n_inj} 个文件的缺号题行并回去了", flush=True)
        a = _select_answers(states, gaps, cands)
        q = _select_questions(states, gaps, cands)
        n = sum(len(v) for v in a.values()) + sum(len(v) for v in q.values())
        if not n:
            print("[parse] 重识别找到的内容对不上缺号")
            break
        for key, d in a.items():
            extra_ans.setdefault(key, {}).update(d)
        for key, d in q.items():
            extra_q.setdefault(key, {}).update(d)
        print(f"[parse] 第 {rnd + 1} 轮重识别：补上 {n} 条"
              f"（答案 {sum(len(v) for v in a.values())}，"
              f"题目 {sum(len(v) for v in q.values())}）", flush=True)
    return extra_ans, extra_q


# ================================================================ 人工修补
#
# 扫描件本身有缺陷（整行漏检、箭头被水印压住、页码混进选项），
# OCR 规则修不回来，只能照着原页人工核对之后写死。
#
# key = (年份, 卷名, 题号)
#   "options": {选项字母: 正确内容}  —— 覆盖已有选项 / 补上漏掉的选项
#   "stem":    修正后的题干
#   "answer":  修正后的答案
MANUAL_FIXES = {
    # 2018 试卷 p18 右栏：第 10 题的 A 选项整行被 OCR 漏掉；
    # C 选项 MCV 后面那个 ↓ 箭头被水印压住，识别成了乱码。
    # （答案册给的是 A：缺铁性贫血是小细胞低色素性，RDW↑、MCV↓）
    (2018, "专业知识", 10): {
        "options": {
            "A": "RDW↑,MCV↓",
            "C": "RDW↓,MCV↓",
        },
    },
    # 2020 试卷 p37/p38：第 99 题 E 选项、第 100 题 D 选项后面
    # 粘着扫描水印的碎片（'。只个81愿'、'不育式想.8'）。
    (2020, "专业实践能力", 99): {
        "options": {"E": "GGT"},
    },
    (2020, "专业实践能力", 100): {
        "options": {"D": "HBV-RNA"},
    },
}


# ---------------------------------------------------------------- 水印污染的答案
#
# 答案册的页面上盖着斜向水印（「需要检验历年真题联系微信…」）。
# OCR 会把水印的碎片和答案字母并进同一行，于是
#     「12.答案：C」   被读成  「12.答案：CA」
#     「42.答案：CAVAAVO）」被读成 「42.答案：CA」
# 症状是这道题被当成多选题（multiple_score=2），卷子的满分凭空比题数多 1 分。
#
# 这批真题全是单项选择题（卷首说明写的是「每题一个最佳答案」，
# 「共用备选答案」的题组也是单选），所以答案里的第二个字母起一定是水印残骸。
# 下面这张表是逐条对着解析文字和选项内容人工核对过的答案，
# 同时也是兜底：自动规则万一漏判，以这张表为准。
#
# key = (年份, 卷名, 题号)  ->  正确的单个答案字母
WATERMARK_ANSWERS = {
    # 尿沉渣镜检细胞至少观察 10 个高倍镜视野（解析："细胞检查10个高倍镜视野"）
    (2016, "专业实践能力", 88): "B",
    # 甲状旁腺激素：升高血钙、降低血磷
    (2018, "基础知识", 16): "C",
    # 决定细菌性状和遗传特征的是核质
    (2020, "基础知识", 35): "A",
    # 活性维生素 D3 的叙述里，错误的是「减少肾钙、磷重吸收」
    (2020, "基础知识", 42): "C",
    # 缺铁性贫血服铁剂后网织红细胞 7~10 天达峰（选项 5~10 天）
    (2020, "相关专业知识", 20): "C",
    # 皮肤试验检测的是 I 型和 IV 型超敏反应
    (2020, "专业知识", 55): "B",
    # 血清总胆固醇正常值 ≤5.18mmol/L（解析点名第 5 版教材的 5.18）
    (2020, "专业实践能力", 12): "C",
    # IFCC 推荐的酶活性浓度测定温度为 37℃。
    # 跨年核对：2011 基础知识 17（选项 A22 B25 C30 D37 E42，答案 D）、
    # 2023 专业实践能力 63（同上选项，答案 D），两边都是 37℃，
    # 而本题 37℃ 正好是 C 栏，所以取 C。
    (2021, "基础知识", 69): "C",
    # 分离培养白喉杆菌用吕氏血清斜面培养基
    (2021, "相关专业知识", 18): "C",
    # 代谢性酸中毒时细胞外液钾升高（高血钾）
    (2021, "专业知识", 42): "A",
    # IV 型变态反应
    (2021, "专业实践能力", 48): "D",
    # 对凝血酶敏感的凝血因子。
    # 跨年核对：2013 基础知识 39「对凝血酶敏感的因子是」答案 A，
    # 该题选项 A = FI、FV、FVII、FXI，对应本题 A 栏。
    (2021, "专业实践能力", 52): "A",
    # 副溶血性弧菌
    (2021, "专业实践能力", 61): "C",
    # 新型隐球菌（解析末句"故选B"）
    (2022, "相关专业知识", 48): "B",
    # 慢性胰腺炎伴脂肪消化不良查粪便脂肪
    (2022, "相关专业知识", 97): "D",
    # 环形铁粒幼细胞主要见于铁粒幼细胞性贫血
    (2022, "专业知识", 12): "B",
    # 铁锈色痰 + 肺大叶实变 = 肺炎链球菌肺炎
    (2022, "专业知识", 90): "A",
    # 测总钙/离子钙不能用 EDTA 抗凝血浆
    (2022, "专业实践能力", 26): "E",
    # t(15;17) 见于急性早幼粒细胞白血病
    (2022, "专业实践能力", 43): "B",
    # 离子选择电极法测血电解质可用肝素锂抗凝
    (2022, "专业实践能力", 64): "C",
    # 流星状运动的细菌 = 霍乱弧菌
    (2022, "专业实践能力", 65): "C",
    # 消瘦多食怕热心悸甲状腺肿 = 甲亢
    (2022, "专业实践能力", 91): "D",
    # 荧光色素把吸收的光能转变成荧光的百分率 = 荧光效率。
    # 答案册里 83 号的题号被 OCR 读成了「微」（"微答案:A"），
    # 整条答案流里没有 83 号，靠 82 号后面的共享备选答案组定位。
    (2023, "基础知识", 83): "A",
}

# ------------------------------------------------- 答案册里压根没印答案的题
#
# 答案册的版式偶尔会漏排某一道题的答案行 —— 扫描件上那一行就是空的，
# 前后两题的答案行直接挨着（2012 基础知识第 27 题、2012 专业知识第 70 题
# 都是这样）。题号并不缺，缺的是答案，所以只能人工定答案。
#
# 定答案的三个依据（按可靠程度）：
#   1. 同一道题在别的年份的答案册里出现过，直接抄那边的答案；
#   2. 本卷答案册里这道题的解析文字本身点明了答案；
#   3. 医学常识 + 选项内容。
#
# key = (年份, 卷名, 题号)
#   "answer":   答案字母
#   "analysis": 解析（能查到就填上，方便考生看解析）
#   "note":     依据，写清楚，免得以后有人当成天经地义的事实
MISSING_ANSWERS = {
    # 解析："溶血性黄疸时，胆红素形成增多，代谢增加，尿液颜色变深，
    # 尿胆原强阳性。" —— 选项里就是「强阳性」。
    # 跨年核对：2010 相关专业知识 64、2019 相关专业知识 71 同题同答案 E。
    (2012, "专业实践能力", 59): {
        "answer": "E",
        "analysis": "溶血性黄疸时，胆红素形成增多，代谢增加，尿液颜色变深，"
                    "尿胆原强阳性。",
        "note": "答案册解析 + 2010/2019 同题均为 E",
    },
    # 跨年核对：2013 基础知识 98、2015 基础知识 95 同题同答案 A（酯酶法）；
    # 2015 的解析写明「尿白细胞检测采用白细胞脂酶法」。
    # 本组第 100 题（尿血红蛋白）答案 C（偶氮反应法），两个答案正好配套。
    (2012, "专业实践能力", 99): {
        "answer": "A",
        "analysis": "尿白细胞检测采用白细胞酯酶法。粒细胞中存在酯酶，"
                    "它能作用于膜块中的吲哚酚酯，使其产生吲哚酚，"
                    "与重氮盐反应形成紫色化合物，颜色深浅与白细胞含量成正比。",
        "note": "2013/2015 同题均为 A",
    },
    # 答案册第 46 题后面那段解析就是本题的：
    # 「染色偏红说明缓冲液体偏酸，应增高缓冲液pH」。
    (2012, "专业知识", 47): {
        "answer": "A",
        "analysis": "染色偏红说明缓冲液体偏酸，应增高缓冲液pH。",
        "note": "答案册解析",
    },
    # 答案册第 69 题之后的那段解析就是本题的：
    # 「……下一步确诊应做血细胞化学染色」，选项 A 就是血细胞化学染色。
    (2012, "专业知识", 70): {
        "answer": "A",
        "analysis": "如果患者有白血病的临床表现，骨髓涂片已经有白血病表现，"
                    "下一步确诊应做血细胞化学染色。",
        "note": "答案册解析",
    },
    # 有效滤过压 = 肾小球毛细血管压 −（血浆胶体渗透压 + 囊内压）。
    # 选项里的加减号扫描件上印的就是「−」「+」，
    # OCR 把「−」读成「一」、「+」读成「十」，已逐字核对像素确认。
    (2012, "基础知识", 27): {
        "answer": "A",
        "analysis": "肾小球的有效滤过压 = 肾小球毛细血管压 − "
                    "（血浆胶体渗透压 + 囊内压）。",
        "note": "选项加减号按像素核对",
    },
    # 答案册第 27 题的解析：
    # 「RIA是以Ag*与反应系统中Ag竞争结合限量的特异性Ab来测定待检样品中Ag量
    #  的一种技术。Ag*与Ag的免疫活性完全相同，对抗体具有相同的亲和力。」
    # 说的就是选项 A。B 错在「Ag的分子数多于Ag*」——待测 Ag 未必比标记 Ag* 多。
    (2012, "相关专业知识", 27): {
        "answer": "A",
        "analysis": "RIA是以Ag*与反应系统中Ag竞争结合限量的特异性Ab来测定"
                    "待检样品中Ag量的一种技术。Ag*与Ag的免疫活性完全相同，"
                    "对抗体具有相同的亲和力。",
        "note": "答案册解析",
    },
    # p-ANCA（核周型）的靶抗原是髓过氧化物酶（MPO）；
    # c-ANCA（胞浆型）的靶抗原是蛋白酶3。
    (2014, "专业实践能力", 28): {
        "answer": "C",
        "analysis": "核周型抗中性粒细胞胞质抗体（p-ANCA）的靶抗原是"
                    "髓过氧化物酶（MPO），胞浆型（c-ANCA）的靶抗原是蛋白酶3。",
        "note": "医学常识",
    },
    # 血浆中含量和种类最多的物质是蛋白质。
    (2014, "基础知识", 30): {
        "answer": "D",
        "analysis": "血浆中含量和种类最多的物质是蛋白质。",
        "note": "医学常识",
    },
    # 正常粪便中没有红细胞。
    (2015, "基础知识", 7): {
        "answer": "B",
        "analysis": "正常粪便中不应有红细胞。",
        "note": "医学常识",
    },
    # 疟原虫、丝虫都在血液里查。
    (2017, "专业知识", 7): {
        "answer": "A",
        "analysis": "检查疟原虫及丝虫时，常用血液标本。",
        "note": "医学常识",
    },
    # 维生素D过多症血钙升高；其余几种都使血钙降低。
    # 跨年核对：2012 相关专业知识 44 同题同答案 E。
    (2017, "相关专业知识", 44): {
        "answer": "E",
        "analysis": "维生素D过多症时血钙浓度升高，其余选项均可使血钙降低。",
        "note": "2012 同题同答案 E",
    },
    # CAMP 阳性的是 A 群链球菌。
    # 外斐试验是间接凝集试验，用已知变形杆菌抗原查患者血清抗体，
    # 常用试管凝集法（与肥达反应同法）。
    # 答案册 p14 那一行是「48.E」，OCR 读成了「148.答案：E。」，按像素核对过。
    (2018, "专业知识", 48): {
        "answer": "E",
        "analysis": "外斐试验是间接凝集试验，用已知抗原（变形杆菌OX19、OX2、"
                    "OXK抗原）检测患者血清中的相应抗体，最常用试管凝集法。",
        "note": "答案册像素核对（2018 答案册 p14 该行是「48.E」）",
    },
    (2019, "专业实践能力", 28): {
        "answer": "E",
        "analysis": "CAMP试验阳性的细菌是A群链球菌。",
        "note": "医学常识",
    },
    # 成人血培养每套采血量应为 8~10ml，「大于1ml即可」不符合要求。
    (2020, "专业实践能力", 1): {
        "answer": "E",
        "analysis": "血培养采血量要求成人每套8~10ml、儿童每套2~5ml，"
                    "仅大于1ml不符合质控要求。",
        "note": "医学常识",
    },
    # 跨年核对：2017 专业实践能力 52、2013 专业实践能力 53 同题同答案 C。
    (2020, "专业实践能力", 63): {
        "answer": "C",
        "analysis": "结核分枝杆菌所致结核病历经数年，从病程上来说属于慢性感染。",
        "note": "2013/2017 同题同答案 C",
    },
    # 酶免疫组化用普通光学显微镜就能看，HRP 是常用的酶。
    (2020, "专业实践能力", 75): {
        "answer": "C",
        "analysis": "酶免疫组织化学技术用普通光学显微镜即可观察结果，"
                    "常用的酶是HRP。",
        "note": "医学常识",
    },
    # 正常红细胞直径7~8μm，小红细胞<6μm，大红细胞>10μm。
    (2020, "专业知识", 75): {
        "answer": "C",
        "analysis": "正常红细胞直径约7~8μm，小红细胞直径小于6μm，"
                    "大红细胞直径大于10μm。",
        "note": "医学常识",
    },
    # MCV 67fL，小细胞低色素性贫血，最可能是缺铁性贫血。
    (2020, "专业知识", 88): {
        "answer": "C",
        "analysis": "患者为青年女性，长期节食，Hb降低、MCV 67fL，"
                    "属小细胞低色素性贫血，最可能为缺铁性贫血。",
        "note": "医学常识",
    },
    # 乙肝感染后血清标志物出现顺序：HBsAg 最先出现。
    (2020, "专业知识", 90): {
        "answer": "A",
        "analysis": "乙肝病毒感染后，血清中首先出现的标志物是HBsAg，"
                    "随后是抗-HBc IgM、HBeAg，最后是抗-HBs。",
        "note": "医学常识",
    },
    # 豆腐渣样白带、外阴瘙痒 —— 真菌性阴道炎。
    # 跨年核对：2013 专业知识 86、2019 专业知识 77 同题同答案 B。
    (2020, "专业知识", 100): {
        "answer": "B",
        "analysis": "白带呈豆腐渣样伴外阴瘙痒、灼痛，阴道分泌物未见杆菌、"
                    "见大量脓细胞和球菌，最可能是真菌性阴道炎。",
        "note": "2013/2019 同题同答案 B",
    },
    # HDL 的作用里没有「促进脂质通过肠壁的运输」（那是乳糜微粒的作用）。
    (2020, "基础知识", 33): {
        "answer": "C",
        "analysis": "HDL可激活脂蛋白酯酶、促进胆固醇酯化、把肝外过量的胆固醇"
                    "运回肝脏并限制动脉粥样硬化的发生发展；"
                    "促进脂质通过肠壁运输的是乳糜微粒。",
        "note": "医学常识",
    },
    # 血浆中分子量最大的蛋白质是 α2-巨球蛋白。
    (2020, "相关专业知识", 4): {
        "answer": "C",
        "analysis": "血浆中分子量最大的蛋白质是α2-巨球蛋白。",
        "note": "医学常识",
    },
    # PSA 是前列腺特异性抗原，属蛋白抗原，不是糖类抗原。
    (2020, "相关专业知识", 22): {
        "answer": "D",
        "analysis": "CA125、CA19-9、CA15-3、CEA均为糖类抗原，"
                    "PSA（前列腺特异性抗原）不属于糖类抗原。",
        "note": "医学常识",
    },
    # 红白血病 PAS 阳性，巨幼细胞性贫血 PAS 阴性，用 PAS 染色鉴别。
    # 跨年核对：2016 专业实践能力 30 同题同答案 B。
    (2022, "专业实践能力", 41): {
        "answer": "B",
        "analysis": "红白血病的原始红细胞PAS染色强阳性，"
                    "巨幼细胞性贫血的巨幼红细胞PAS染色阴性，故首选PAS染色鉴别。",
        "note": "2016 同题同答案 B",
    },
    # 尿管型检查用麝香草酚作防腐剂。
    (2023, "专业实践能力", 17): {
        "answer": "C",
        "analysis": "适宜尿管型检查的防腐剂是麝香草酚。",
        "note": "医学常识",
    },
    # ANCA 的荧光模式除胞浆型外还有核周型（p-ANCA）。
    (2023, "专业实践能力", 58): {
        "answer": "C",
        "analysis": "ANCA的荧光图谱模式有胞浆型（c-ANCA）、核周型（p-ANCA）"
                    "和颗粒型，题中所指除胞浆型外的是核周型。",
        "note": "医学常识",
    },
    # 间接血凝试验：红细胞形成布满孔底的片层即为凝集，以此判读滴度。
    (2023, "基础知识", 12): {
        "answer": "B",
        "analysis": "间接血凝试验中红细胞形成布满孔底的片层为凝集，"
                    "凝集程度以凝集稀释度（滴度）报告。",
        "note": "医学常识",
    },
    # 血细胞稀释液必须是等渗液，否则红细胞变形影响计数。
    (2023, "基础知识", 73): {
        "answer": "B",
        "analysis": "血细胞计数用稀释液应为等渗溶液，否则会使红细胞胀缩变形，"
                    "影响计数结果。",
        "note": "医学常识",
    },
    # 钩虫的感染方式经皮肤侵入。
    # 跨年核对：2018 相关专业知识 42、2016 相关专业知识 42 同题同答案 C。
    (2023, "相关专业知识", 8): {
        "answer": "C",
        "analysis": "钩虫的感染方式是经皮肤侵入人体；溶组织阿米巴、猪带绦虫、"
                    "蛔虫都经口感染。",
        "note": "2016/2018 同题同答案 C",
    },
    # 痛风与血尿酸（UA）升高有关。
    # 答案册 p5 那一行 OCR 读成了「4人谷案:C」，把该处重新识别才读出「答案：C」。
    (2023, "相关专业知识", 42): {
        "answer": "C",
        "analysis": "痛风与血尿酸（UA）水平升高有关；其余选项分别是尿素氮、氯、"
                    "肌酸激酶、总胆汁酸。",
        "note": "答案册重识别核对（2023 答案册 p5 读出「答案：C」）",
    },
    # 自身免疫病的实验室筛查指标是 ANA。
    # 答案册 p10 那一行 OCR 读成了「d案:C」，把该处重新识别才读出「98 答案：C」。
    (2023, "专业知识", 98): {
        "answer": "C",
        "analysis": "ANA（抗核抗体）是自身免疫性疾病的实验室筛查指标；"
                    "ENA抗体谱、ds-DNA、Sm抗体属于进一步的确诊与鉴别项目。",
        "note": "答案册重识别核对（2023 答案册 p10 读出「98 答案：C」）",
    },
    # 关于ABO血型鉴定，错误的描述是：
    #   A 用已知特异性抗体检查红细胞上的未知抗原，称为正向定型（对）
    #   B 用已知血型的标准红细胞检查血清中的未知抗体，称为反向定型（对）
    #   C O型血清在红细胞ABO亚型鉴定中不起作用（错）
    #   D O型红细胞用于检查是否存在不规则抗体（对）
    #   E 用抗A1血清可区分A亚型（对）
    # O型血清含抗A、抗B抗体，在ABO亚型鉴定中有重要作用（可辅助验证弱反应），
    # 所以「不起作用」是错的。
    # 2020 答案册 p3 左栏该行印刷字迹残缺（像素核对：只剩一个方框状墨迹，
    # 认不出字母），故查外部题库定答案。
    (2020, "基础知识", 38): {
        "answer": "C",
        "analysis": "正向定型是用已知特异性抗体检测红细胞上的未知抗原；"
                    "反向定型是用已知血型的标准红细胞检测血清中的未知抗体；"
                    "O型血清中含有抗A、抗B抗体，在ABO亚型鉴定中有重要作用，"
                    "因此「O型血清在红细胞ABO亚型鉴定中不起作用」错误；"
                    "O型红细胞表面无A、B抗原，可用于检查血清中是否存在不规则抗体；"
                    "抗A1血清可区分A1、A2亚型。",
        "note": "外部题库（2021年血液病主治医师专业知识同题）答案 C",
    },
}


# 真·多选题（同一题两个及以上答案）。这批真题里一道都没有，
# 留着这张表是为了以后碰到真多选时有个登记的地方，
# 也提醒后来人：答案里的第二个字母不是默认都能砍掉的。
MANUAL_MULTI_ANSWERS = {}


# 原书本身有排版缺陷（漏排题号、题目被挤到上一行），导致某一题的题干在
# 扫描件上根本认不出来，但答案册里能查到答案。这类题只能人工补录。
#
# key = (年份, 卷名, 题号)
#   "stem":     题干
#   "options":  {选项字母: 选项内容}
#   "answer":   答案
#   "analysis": 解析
MANUAL_QUESTIONS = {
    # 2012 试卷 p26 右栏：第 70 题的原书漏排了题号，题干和选项挤在两行里
    # (「肝硬变病人蛋白电泳出现β桥，多是由何种免疫球蛋白」/「白增加所致」，
    #  下一行是「A.IgA B.IgM C.IgG D.IgE E.IgD.71.某一脑汁标本，」)，
    #  解析器因此把题干当成上一行的续行，第 70 题整个消失。
    # 答案册 p15 左栏有「70、A」和解析（提到 IgA 增高）。
    (2012, "专业实践能力", 70): {
        "stem": "肝硬变病人蛋白电泳出现β桥，多是由何种免疫球蛋白增加所致",
        "options": {
            "A": "IgA",
            "B": "IgM",
            "C": "IgG",
            "D": "IgE",
            "E": "IgD",
        },
        "answer": "A",
        "analysis": "肝脏疾病时，血清蛋白电泳表现为清蛋白区带含量减少，"
                    "而β和球蛋白增高，出现β和难以分离和相连的β桥，"
                    "此现象往往由于IgA增高所致。",
    },
}

# 答案册里有答案、但扫描件上根本没有这道题（书上就没印/印重了），
# 题干无从还原，只能记账，不能瞁编一题进去。
UNRECOVERABLE_MISSING = {
    (2011, "专业实践能力", 48): "答案册 p9 给出 48.A，但试卷 p25 上第 47 题"
                                "被印了两遍（第 48 题的内容被覆盖），"
                                "题干在扫描件上不存在，无法还原",
}


def _apply_manual_questions(papers):
    """把人工补录的整题插进对应卷（按题号排序）。"""
    n = 0
    for p in papers:
        for (year, paper_name, num), q in MANUAL_QUESTIONS.items():
            if year != p["year"] or paper_name != p["paper_name"]:
                continue
            if any(x["num"] == num for x in p["questions"]):
                continue
            item = {
                "num": num,
                "stem": q["stem"],
                "options": dict(q["options"]),
                "answer": q["answer"],
                "analysis": q.get("analysis", ""),
                "conf": 1.0,
                "shared": False,
                "year": year,
                "paper_name": paper_name,
                "answer_source": "manual",
                "type": "multiple" if len(
                    [c for c in q["answer"] if c.isalpha()]) > 1 else "single",
                "manual_added": True,
            }
            p["questions"].append(item)
            p["questions"].sort(key=lambda x: x["num"])
            n += 1
            print(f"[parse] 人工补题 {year} {paper_name} 第 {num} 题")
    return n


def _apply_missing_answers(papers):
    """给答案册里压根没印答案的题补上人工核定的答案。

    只补「本来就没有答案」的题；自动认出来的答案不动，
    免得人工表把已经认对的题改错。
    """
    n = 0
    for p in papers:
        for q in p.get("questions") or []:
            if (q.get("answer") or "").strip():
                continue
            item = MISSING_ANSWERS.get((p["year"], p["paper_name"], q["num"]))
            if not item:
                continue
            q["answer"] = item["answer"]
            q["type"] = "single"
            q["answer_source"] = "manual"
            if item.get("analysis"):
                q["analysis"] = item["analysis"]
            n += 1
            print(f"[parse] 人工补答案 {p['year']} {p['paper_name']} "
                  f"第 {q['num']} 题 = {item['answer']}"
                  f"（{item.get('note', '')}）")
    if n:
        print(f"[parse] 人工补答案共 {n} 题")
    return n


def _apply_manual_fixes(papers):
    """套用人工修补表，返回改动的处数。"""
    n = 0
    for p in papers:
        for q in p["questions"]:
            fix = MANUAL_FIXES.get((p["year"], p["paper_name"], q["num"]))
            if not fix:
                continue
            for key, val in fix.items():
                if key == "options":
                    opts = q.setdefault("options", {})
                    for letter, text in val.items():
                        if opts.get(letter) != text:
                            opts[letter] = text
                            n += 1
                elif q.get(key) != val:
                    q[key] = val
                    n += 1
            q["manual_fixed"] = True
    if n:
        print(f"[parse] 人工修补 {n} 处")
    return n


def _normalize_answer(question, year, paper_name):
    """定下这道题的答案和题型，顺便把水印污染的答案修好。

    答案册页面上盖着斜向水印，OCR 会把水印碎片并进答案行，
    「答案：C」被读成「答案：CA」。这批真题全是单项选择题，
    所以答案里的第二个字母起一定是水印残骸，砍掉即可。

    人工核对过的题（WATERMARK_ANSWERS）以人工表为准，
    万一自动规则漏判，也有人工表兜底。

    返回 "trimmed"（被水印削过）/ "manual"（人工表改过）/ "" （没动）。
    """
    key = (year, paper_name, question["num"])
    ans = (question.get("answer") or "").strip().upper()
    letters = [c for c in ans if c in "ABCDE"]

    manual = WATERMARK_ANSWERS.get(key)
    if manual:
        question["answer"] = manual
        question["type"] = "single"
        question["answer_source"] = "manual"
        return "manual"

    multi = MANUAL_MULTI_ANSWERS.get(key)
    if multi:
        question["answer"] = multi
        question["type"] = "multiple"
        question["answer_source"] = "manual"
        return "manual"

    if len(letters) > 1:
        question["answer"] = letters[0]
        question["type"] = "single"
        question["watermark_trimmed"] = True
        print(f"[parse] {year} {paper_name} 第 {question['num']} 题"
              f"答案被水印污染成 {ans!r}，只取首字母 {letters[0]}")
        return "trimmed"

    question["type"] = "single"
    return ""




def stage_parse(src: pathlib.Path, jobs=4):
    PARSE_DIR.mkdir(parents=True, exist_ok=True)
    report = []

    states = {}
    for path, kind in pdf_files(src):
        m = PAPER_FILE_RE.search(path.name)
        default_year = int(m.group(1))
        st = _file_state(path, kind, default_year)
        states[path.name] = st
        if not st["flow"]:
            print(f"[parse] {path.name} 没有 OCR 缓存，跳过")
            continue
        n_lr = sum(1 for v in st["orders"].values() if v == "LR")
        print(f"[parse] {path.name}: {len(st['segs'])} 个卷段"
              f"（默认 {st['default_order']}，逐页 LR {n_lr}/{len(st['orders'])}）")

    # 整页 OCR 偶尔会整行漏检，用多阈值重识别把漏掉的行捞回来
    extra_ans, extra_q = {}, {}
    if os.environ.get("PAST_PAPERS_NO_REOCR", "") != "1":
        extra_ans, extra_q = _recover_gaps(states, jobs=jobs)

    index = {}          # (year, paper_name) -> {"exam": [...], "answer": {...}}
    for st in states.values():
        _absorb(index, st)
    _inject(index, extra_ans, extra_q)

    # 配对：试卷题号 ↔ 答案题号
    papers = []
    for (year, paper_name), slot in sorted(index.items()):
        questions = slot["exam"]
        answers = slot["answer"]
        # 同一卷跨文件重复的题，按题号去重（保留选项更全的）
        dedup = {}
        for q in questions:
            old = dedup.get(q["num"])
            if old is None or len(q["options"]) > len(old["options"]):
                dedup[q["num"]] = q
        questions = [dedup[k] for k in sorted(dedup)]

        unmatched = []
        if not answers:
            unmatched = [q["num"] for q in questions]
        else:
            by_num = {q["num"]: q for q in questions}
            # 答案册和试卷的题号是一一对应的（都是 1..100）。
            # 缺号是「这一题的答案没认出来」，不是「题号错位」——
            # 所以只按题号配。剩下的答案号是孤儿（试卷上没这道题），
            # 按顺序硬配会把别的题的答案安到这道题头上（2020 专业实践能力
            # 的 5 道题就是这样被安错的）。
            for qnum in by_num:
                if qnum not in answers:
                    continue
                q = by_num[qnum]
                q["answer"] = answers[qnum]["answer"]
                q["analysis"] = answers[qnum]["analysis"]
                q["answer_source"] = "exact"
            # 答案册上有斜向水印，OCR 把水印碎片并进了答案行，
            # "答案：C" 会变成 "答案：CA"。这批真题全是单选，
            # 所以第二个字母起一定是水印；人工核对过的题以人工表为准。
            for q in questions:
                _normalize_answer(q, year, paper_name)
            got = {q["num"] for q in questions if q.get("answer")}
            unmatched = [q["num"] for q in questions if q["num"] not in got]

        gaps = [num for (y, pn, num) in UNRECOVERABLE_MISSING
                if y == year and pn == paper_name]
        if gaps:
            print(f"[parse] 无法还原的缺题：{year} {paper_name} "
                  + "；".join(f"第 {n} 题" for n in gaps)
                  + f"（原因：{UNRECOVERABLE_MISSING[(year, paper_name, gaps[0])]}）")

        papers.append({
            "year": year,
            "paper_name": paper_name,
            "unrecoverable": {str(n): UNRECOVERABLE_MISSING[(year, paper_name, n)]
                              for n in gaps},
            "level": "初级",
            "title": f"{year}年临床医学检验技术（初级）· {paper_name}",
            "code": f"{year}_ji_{_paper_slug(paper_name)}",
            "sources": slot["sources"],
            "questions": questions,
            "unmatched": unmatched,
            "has_answer": bool(answers),
            "_answer_count": len(answers),
            "_title_guessed": any(s["title_guessed"] for s in slot["sources"]),
        })

    _apply_manual_fixes(papers)
    _apply_missing_answers(papers)
    _apply_manual_questions(papers)

    # 人工补答案、补题之后再统计还缺答案的题，不然报告里算的是补之前的数
    for p in papers:
        got = {q["num"] for q in p["questions"] if (q.get("answer") or "").strip()}
        p["unmatched"] = [q["num"] for q in p["questions"] if q["num"] not in got]

    # 报告在人工补题之后才统计，否则题数对不上
    for p in papers:
        report.append({
            "year": p["year"], "paper_name": p["paper_name"],
            "questions": len(p["questions"]),
            "answers": p.pop("_answer_count"),
            "unmatched": len(p["unmatched"]),
            "unrecoverable": ",".join(sorted(p.get("unrecoverable", {}))),
            "title_guessed": p.pop("_title_guessed"),
            "files": ",".join(s["file"] for s in p["sources"]),
        })

    # 6 份专业知识 PDF
    knowledge = []
    for path, cat in knowledge_files(src):
        items = _parse_knowledge_pdf(path)
        for it in items:
            category = cat
            if cat == "寄生虫与质量控制":
                category = "寄生虫" if PARASITE_RE.search(it["stem"] + it["answer"]) else "质量管理"
            it["category"] = category
        knowledge.append({
            "kind": "knowledge",
            "title": f"{path.stem}（专业知识清单）",
            "code": f"know_{_paper_slug(path.stem)}",
            "category_default": cat,
            "questions": items,
        })
        print(f"[parse] {path.name}: {len(items)} 条")

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "papers": papers,
        "knowledge": knowledge,
    }
    dest = PARSE_DIR / "parsed.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    dest2 = REPORT_DIR / "past_papers_parse_report.csv"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with dest2.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["year", "paper_name", "questions",
                                           "answers", "unmatched",
                                           "unrecoverable", "title_guessed",
                                           "files"])
        w.writeheader()
        for r in report:
            w.writerow(r)
    print(f"[parse] 卷段 {len(papers)} 个 -> {dest}")
    print(f"[parse] 报告 -> {dest2}")
    noans = [p for p in papers if not p["has_answer"]]
    if noans:
        print(f"[parse] 无答案的卷（不入库）: "
              f"{[(p['year'], p['paper_name']) for p in noans]}")
    guess = [p for p in papers if any(s["title_guessed"] for s in p["sources"])]
    if guess:
        print(f"[parse] 卷名靠推断的: "
              f"{[(p['year'], p['paper_name']) for p in guess]}")


def _paper_slug(name: str) -> str:
    return {
        "基础知识": "chushi",
        "相关专业知识": "xiangguan",
        "专业知识": "zhuanye",
        "专业实践能力": "shijian",
    }.get(name, re.sub(r"\W+", "", name) or "x")


def _parse_knowledge_pdf(path: pathlib.Path):
    """用 pdfplumber 抽表格（这两份是带边框的二维表格，抽出来就是精确配对）。"""
    import warnings
    warnings.filterwarnings("ignore")
    import pdfplumber

    items = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for table in pg.extract_tables():
                for row in table:
                    if len(row) < 2:
                        continue
                    stem = (row[0] or "").replace("\n", "").strip()
                    ans = (row[1] or "").replace("\n", "").strip()
                    if stem and ans:
                        items.append({"stem": stem, "answer": ans})
    return items


# ---------------------------------------------------------------- 词表

def build_lexicon(db=None, extra_texts=None):
    """从现有题库 + 真题语料收集 2~6 字的中文词，作为"哪些字组合是对的"的依据。

    现有 1300 多道形态学题的题干/解析里全是检验术语，拿它当词表很合适；
    真题语料本身也是重要来源 —— 有些正确写法只出现在真题里（比如"亲和素"）。
    """
    import collections
    cnt = collections.Counter()

    def add(text):
        if not text:
            return
        for run in re.findall(r"[一-龥]{2,}", text):
            for n in range(2, 7):
                for i in range(len(run) - n + 1):
                    cnt[run[i:i + n]] += 1

    rows = []
    try:
        from app import models
        from app.database import SessionLocal
        s = SessionLocal()
        try:
            rows = s.query(models.Question.content, models.Question.analysis,
                           models.Question.options).limit(4000).all()
        finally:
            s.close()
    except Exception as e:
        print(f"[clean] 词表从库里取失败（{e}），改用纯语料词表")
    for content, analysis, options in rows:
        add(f"{content or ''} {analysis or ''} {options or ''}")
    for t in (extra_texts or []):
        add(t)
    return cnt


# ---------------------------------------------------------------- 清洗规则表

SUPERSCRIPT = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
               "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}
SUPERSCRIPT_REV = {v: k for k, v in SUPERSCRIPT.items()}

# 词组级错字表。
# 每一条都用历年真题横向比对核实过（同一道题在别的年份卷子上的写法）。
# 只做"词组"替换，不做"单字"替换：像"人/入"这种字级替换会伤到
# "抗人球蛋白""正常人""病人""成人"这些完全正常的词（语料里上百处）。
CONFUSABLE_PAIRS = [
    ("人院", "入院"),
    ("加人", "加入"),
    ("进人", "进入"),
    ("吸人", "吸入"),
    ("投人", "投入"),
    ("注人", "注入"),
    ("侵人", "侵入"),
    ("置人", "置入"),
    ("食人", "食入"),
    ("中心淡染压", "中心淡染区"),
    ("亲合素", "亲和素"),
    ("三羟酸", "三羧酸"),
    ("晓虫", "蛲虫"),
    ("烧虫", "蛲虫"),
    ("后穹窟", "后穹隆"),
]

# 单位/量纲类 OCR 噪声：只收"不论语境都成立"的替换。
UNIT_FIXES = [
    (r"mo1(?![0-9])", "mol"),          # mmo1 -> mmol，μmo1 -> μmol
    (r"(?<=[0-9])f1(?![0-9])", "fl"),   # MCV130f1 -> MCV130fl
    (r"(?<![0-9A-Za-z])f1(?![0-9A-Za-z])", "fl"),  # 单位清单里的 fl
    (r"mg/d1", "mg/dl"),
    (r"d1E%", "dlE%"),
    (r"\bumol", "μmol"),
    (r"μml(?![A-Za-z])", "μmol"),
    (r"μ+mmol", "μmol"),
    (r"mm3", "mm³"),
    (r"um3", "um³"),
    (r"(?<=\d)\.O(?=mmol)", ".0"),   # 7.Ommol/L -> 7.0mmol/L
    (r"(?<=\d)\.O(?=h)", ".0"),       # 2.Oh内 -> 2.0h内
]

# 红细胞计数是 10^12，白细胞/血小板是 10^9 —— 指数被吃掉时按上下文猜
_RED_CNT = re.compile(r"RBC|HCT|血细胞比容|(?<!网织)红细胞(?!沉降率)")
_WHITE_CNT = re.compile(r"WBC|PLT|BPC|Ret|RET|网织|血小板|白细胞|中性粒|中性成熟")
_POW10_RE = re.compile(r"[×xX]\s*10")
_EXP_ARTIFACT = "°~'\"*l"
_UNIT_AFTER = set("/／LℓCm")


def _context_exponent(text, start, end):
    """×10 后面指数被 OCR 吃掉时，按上下文猜指数：红细胞 12，白细胞/血小板 9。"""
    lo = max(0, start - 45)
    hi = min(len(text), end + 25)
    win = text[lo:hi]
    center = (start + end) // 2 - lo
    d_red = d_white = 10 ** 6
    for mm in _RED_CNT.finditer(win):
        d_red = min(d_red, abs((mm.start() + mm.end()) // 2 - center))
    for mm in _WHITE_CNT.finditer(win):
        d_white = min(d_white, abs((mm.start() + mm.end()) // 2 - center))
    return "9" if d_white <= d_red else "12"


def _param_in(text, lo, hi):
    """text[lo:hi] 里离 hi 最近的指标是红细胞系还是白细胞系。

    返回 "red" / "white" / None（没提到具体指标）。
    """
    seg = text[lo:hi]
    d_red = d_white = None
    for mm in _RED_CNT.finditer(seg):
        d = hi - (lo + mm.end())
        if d_red is None or d < d_red:
            d_red = d
    for mm in _WHITE_CNT.finditer(seg):
        d = hi - (lo + mm.end())
        if d_white is None or d < d_white:
            d_white = d
    if d_red is None and d_white is None:
        return None
    if d_red is None:
        return "white"
    if d_white is None:
        return "red"
    return "red" if d_red < d_white else "white"


def _missing_exponent(text, m):
    """指数整个被 OCR 吃掉了：先看紧挨着数字的指标，再退回大范围上下文。"""
    p = _param_in(text, max(0, m.start() - 12), m.start())
    if p == "red":
        return "12"
    if p == "white":
        return "9"
    return _context_exponent(text, m.start(), m.end())


def _pow10_exponent(text, m):
    """算出 ×10 后面应该是几的幂。

    返回 (指数数字串, 指数在 text 中的结束位置)；判断不了时返回 (None, m.end())。
    """
    j = m.end()
    k = j
    while k < len(text) and text[k] in " 　":
        k += 1
    tok = ""
    while k < len(text) and (text[k].isdigit() or text[k] in _EXP_ARTIFACT
                             or text[k] in SUPERSCRIPT_REV or text[k] == "%"):
        tok += text[k]
        k += 1

    def after_unit(pos):
        q = pos
        while q < len(text) and text[q] in " 　":
            q += 1
        return text[q] if q < len(text) else ""

    if not tok:
        # "×10/2/L" —— OCR 把上标 12 认成 "/2"
        if text[k:k + 3] == "/2/":
            return "12", k + 2
        if after_unit(k) in _UNIT_AFTER:
            return _missing_exponent(text, m), k
        return None, m.end()

    digits = ""
    has_pct = False
    for i, ch in enumerate(tok):
        nxt = tok[i + 1] if i + 1 < len(tok) else ""
        follows_digit = nxt.isdigit() or nxt in SUPERSCRIPT_REV
        if ch in SUPERSCRIPT_REV:
            digits += SUPERSCRIPT_REV[ch]
        elif ch in "l'\"":
            # 只有紧跟数字时才是"1"（如 "l²"->"12"），否则是噪声字符
            if follows_digit:
                digits += "1"
        elif ch in "°~*":
            continue           # OCR 残留的噪声字符
        elif ch == "%":
            has_pct = True
        elif ch.isdigit():
            digits += ch
    if has_pct and digits:
        return None, m.end()   # ×100% 是百分比，不是 10^0
    if digits and set(digits) == {"0"}:
        return None, m.end()   # ×100/Y 是"乘以 100"，不是 10^0
    if not digits:
        if after_unit(k) in _UNIT_AFTER:
            return _missing_exponent(text, m), k
        return None, m.end()
    if after_unit(k) not in _UNIT_AFTER:
        return None, m.end()   # 指数后面必须是单位，否则可能是普通数字
    if digits == "12":
        # RBC 3.5×1012/L 是 10^12；但 "WBC16×1012/L" 只能是 10^9
        if _param_in(text, max(0, m.start() - 12), m.start()) == "white":
            return "9", k
        return "12", k
    if len(digits) == 1:
        # RBC 5.0×102/L 其实是 ×10^12/L（单个数字在红细胞计数里说不通）
        if _param_in(text, max(0, m.start() - 12), m.start()) == "red":
            return "12", k
        return digits, k
    if len(digits) == 2:
        # 两位指数里只有 12 在血常规里说得通，其余按上下文猜
        return _context_exponent(text, m.start(), m.end()), k
    return digits, k


def fix_confusables(text, log, lex=None):
    """按词组级错字表纠正 OCR 错字。

    词库（DB 现有题库 + 真题语料）用来校验替换目标确实是术语；
    词库查不到时照样替换，但在报告里标出来供人工复核。
    """
    if not text:
        return text
    for a, b in CONFUSABLE_PAIRS:
        if a not in text:
            continue
        known = True if lex is None else lex.get(b, 0) > 0
        log.append(("错别字" if known else "错别字(词库未收录)", a, b, text))
        text = text.replace(a, b)
    return text


def fix_units(text, log):
    """单位/量纲类 OCR 噪声。"""
    if not text:
        return text
    for pat, rep in UNIT_FIXES:
        new = re.sub(pat, rep, text)
        if new != text:
            log.append(("单位", pat, rep, text))
            text = new
    return text


def fix_superscript(text, log):
    """还原 OCR 丢掉的上下标：RBC1.6×1012/L -> 1.6×10¹²/L"""
    if not text:
        return text
    out = []
    pos = 0
    for m in _POW10_RE.finditer(text):
        if m.start() < pos:
            continue
        exp, end = _pow10_exponent(text, m)
        if exp is None:
            continue
        sup = "".join(SUPERSCRIPT[c] for c in exp)
        before = text[m.end():end] or "(指数缺失)"
        if text[m.end():end] == sup:
            continue          # 本来就是上标，原样保留
        out.append(text[pos:m.start()])
        out.append(f"{text[m.start():m.end()]}{sup}")
        pos = end
        log.append(("上标", before, sup, text))
    out.append(text[pos:])
    return "".join(out)


def fix_symbol(text, log):
    """Symbol 字体的私用区字符。"""
    mapping = {"\uf061": "α", "\uf067": "γ", "\uf06d": "μ"}
    for code, real in mapping.items():
        if code in text:
            log.append(("符号字体", code, real, text))
            text = text.replace(code, real)
    return text


def clean_text(text, log, lex=None):
    text = fix_symbol(text, log)
    text = fix_units(text, log)
    text = fix_superscript(text, log)
    text = fix_confusables(text, log, lex)
    return text


def validate(question):
    """结构校验。返回问题列表（空 = 通过）。"""
    problems = []
    opts = question.get("options") or {}
    if len(opts) < 4 or len(opts) > 5:
        problems.append(f"选项数 {len(opts)}")
    if not (question.get("stem") or "").strip():
        problems.append("题干为空")
    ans = (question.get("answer") or "").strip()
    if not ans:
        problems.append("没有答案")
    else:
        letters = [c for c in ans.upper() if c.isalpha()]
        if not letters:
            problems.append("答案不是字母")
        else:
            for c in letters:
                if c not in opts:
                    problems.append(f"答案 {c} 不在选项里")
                    break
    if question.get("type") == "multiple" and len(ans.replace(",", "")) < 2:
        problems.append("多选题只有一个答案")
    return problems


# ---------------------------------------------------------------- LLM 纠错

LLM_ENDPOINTS = [
    "https://api.minimaxi.com/v1/chat/completions",
    "https://api.minimax.chat/v1/text/chatcompletion_v2",
]


def llm_fix(text, kind):
    """把一段文本交给 MiniMax 纠错。只在 key 存在时调用。"""
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key or not text:
        return None
    prompt = (
        "你是医学检验题库的校对助手。下面是一段从扫描试卷 OCR 出来的中文文本，"
        "可能有识别错字。请只修正明显的错别字（例如形近字、上下标丢失、乱码），"
        "不要改动任何标点、数字、术语含义，不要增删内容，不要解释。"
        "如果原文没有明显错误，就原样返回。\n\n"
        f"类型：{kind}\n原文：{text}\n\n校正后："
    )
    for url in LLM_ENDPOINTS:
        try:
            if url.endswith("chatcompletion_v2"):
                payload = {
                    "model": "abab6.5s-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }
            else:
                payload = {
                    "model": "MiniMax-Text-01",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1200,
                }
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", "Bearer " + key)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "choices" in data:
                out = data["choices"][0]["message"]["content"]
            else:
                out = data["reply"]
            out = (out or "").strip()
            if out:
                return out
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- 清洗阶段

def iter_texts(groups):
    """把题目里所有文本（题干/解析/答案/选项）取出来，用来建词表。"""
    for _owner, questions, _kind in groups:
        for q in questions:
            for field in ("stem", "analysis", "answer"):
                v = q.get(field)
                if isinstance(v, str):
                    yield v
            opts = q.get("options")
            if isinstance(opts, dict):
                for v in opts.values():
                    if isinstance(v, str):
                        yield v


def stage_clean(use_llm=True):
    load_dotenv_local()      # 词表要从库里取，得有 DATABASE_URL
    src = PARSE_DIR / "parsed.json"
    if not src.exists():
        print("[clean] 找不到解析结果，先跑 --stage parse")
        return
    data = json.loads(src.read_text(encoding="utf-8"))

    groups = []
    for p in data.get("papers", []):
        groups.append((p, p.get("questions", []), "paper"))
    for k in data.get("knowledge", []):
        groups.append((k, k.get("questions", []), "knowledge"))

    lex = build_lexicon(extra_texts=list(iter_texts(groups)))
    print(f"[clean] 词表规模 {len(lex)}")

    report = []
    fixed_by_llm = 0
    llm_failed = 0

    for owner, questions, kind in groups:
        for q in questions:
            log = []
            for field in ("stem", "analysis", "answer"):
                if field in q and isinstance(q[field], str):
                    q[field] = clean_text(q[field], log, lex)
            opts = q.get("options")
            if isinstance(opts, dict):
                for key, val in list(opts.items()):
                    if isinstance(val, str):
                        opts[key] = clean_text(val, log, lex)
            for entry in log:
                report.append({
                    "kind": kind,
                    "year": owner.get("year", ""),
                    "paper": owner.get("paper_name", owner.get("title", "")),
                    "num": q.get("num", ""),
                    "rule": entry[0],
                    "before": entry[1],
                    "after": entry[2],
                    "context": entry[3][:80],
                })
            problems = validate(q)
            q["problems"] = problems
            low_conf = q.get("conf", 1.0) < 0.75
            if problems and use_llm:
                target = q.get("stem", "")
                fixed = llm_fix(target, "题干")
                if fixed and fixed != target and len(fixed) < len(target) * 3:
                    q["stem"] = fixed
                    q["llm_fixed"] = True
                    fixed_by_llm += 1
                    report.append({
                        "kind": kind, "year": owner.get("year", ""),
                        "paper": owner.get("paper_name", owner.get("title", "")),
                        "num": q.get("num", ""), "rule": "LLM纠错",
                        "before": target[:60], "after": fixed[:60], "context": "",
                    })
                    problems = validate(q)
                    q["problems"] = problems
                else:
                    llm_failed += 1
            q["needs_review"] = bool(problems) or low_conf

    dest = PARSE_DIR / "cleaned.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rep = REPORT_DIR / "past_papers_clean_report.csv"
    with rep.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "year", "paper", "num", "rule",
                                           "before", "after", "context"])
        w.writeheader()
        for r in report:
            w.writerow(r)

    need = [q for _o, qs, _k in groups for q in qs if q.get("needs_review")]
    print(f"[clean] 改动 {len(report)} 处，其中 LLM 纠错 {fixed_by_llm} 条"
          f"（调用失败 {llm_failed} 条）")
    print(f"[clean] 待人工复核 {len(need)} 题 -> {rep}")
    print(f"[clean] 结果 -> {dest}")


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


def ensure_schema():
    """建表 + 补列（幂等）。"""
    from sqlalchemy import text
    from app.database import Base, engine, SessionLocal
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ddl = [
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS paper_id INTEGER REFERENCES question_papers(id)",
        "ALTER TABLE exams ADD COLUMN IF NOT EXISTS kind VARCHAR(20) DEFAULT 'normal'",
        "ALTER TABLE exams ADD COLUMN IF NOT EXISTS paper_id INTEGER REFERENCES question_papers(id)",
        "CREATE INDEX IF NOT EXISTS ix_questions_paper ON questions (paper_id)",
        "CREATE INDEX IF NOT EXISTS ix_exams_kind ON exams (kind)",
        "CREATE INDEX IF NOT EXISTS ix_exams_paper ON exams (paper_id)",
    ]
    with engine.connect() as conn:
        for stmt in ddl:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()


def stage_load(apply=False):
    src = PARSE_DIR / "cleaned.json"
    if not src.exists():
        src = PARSE_DIR / "parsed.json"
    if not src.exists():
        print("[load] 找不到解析结果，先跑 --stage parse")
        return
    data = json.loads(src.read_text(encoding="utf-8"))

    load_dotenv_local()
    ensure_schema()
    from app import crud, models, schemas
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.is_admin.is_(True)).first()
        admin_id = admin.id if admin else None

        # ---------- 备份 ----------
        if apply:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = REPORT_DIR / f"past_papers_{stamp}.json"
            rows = db.query(models.Question).filter(
                models.Question.paper_id.isnot(None)).all()
            papers = db.query(models.QuestionPaper).all()
            exams = db.query(models.Exam).filter(
                models.Exam.kind == "past_paper").all()
            backup.write_text(json.dumps({
                "questions": [{"id": q.id, "paper_id": q.paper_id} for q in rows],
                "papers": [{"id": p.id, "code": p.code, "exam_id": p.exam_id,
                            "question_count": p.question_count} for p in papers],
                "exams": [{"id": e.id, "title": e.title, "paper_id": e.paper_id}
                           for e in exams],
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[load] 已备份现有真题相关数据 -> {backup}")

        # ---------- 卷宗 + 题目 ----------
        total_q = 0
        created_papers = 0
        created_exams = 0

        for p in data.get("papers", []):
            if not p.get("has_answer"):
                print(f"[load] 跳过无答案的卷：{p['year']} {p['paper_name']}")
                continue
            questions = [q for q in p.get("questions", []) if q.get("answer")]
            if not questions:
                print(f"[load] 跳过空卷：{p['year']} {p['paper_name']}")
                continue

            paper = db.query(models.QuestionPaper).filter_by(
                code=p["code"]).first()
            if paper is None:
                paper = models.QuestionPaper(code=p["code"])
                db.add(paper)
                created_papers += 1
            paper.year = p["year"]
            paper.level = p.get("level", "初级")
            paper.paper_name = p["paper_name"]
            paper.title = p["title"]
            paper.kind = "paper"
            paper.source_file = ",".join(s["file"] for s in p.get("sources", []))
            paper.source_title = ""
            paper.page_from = min([s["page_from"] for s in p.get("sources", [])] or [0])
            paper.page_to = max([s["page_to"] for s in p.get("sources", [])] or [0])
            paper.question_count = len(questions)
            db.flush()

            # 旧的题先删掉，重跑时不会重复
            old = db.query(models.Question).filter(
                models.Question.paper_id == paper.id).all()
            for q in old:
                db.query(models.ExamRecord).filter(
                    models.ExamRecord.answers.like(f'%{q.id}%')).delete(
                        synchronize_session=False)
                db.delete(q)
            db.flush()

            # 批量插入：远程库上一条一条 flush 会慢到离谱
            rows = []
            for q in questions:
                opts = {k: v for k, v in (q.get("options") or {}).items() if v}
                rows.append(models.Question(
                    type=q.get("type", "single"),
                    content=f"<p>{q.get('stem', '')}</p>",
                    options=json.dumps(opts, ensure_ascii=False),
                    answer=q.get("answer", ""),
                    analysis=q.get("analysis", ""),
                    category=p["paper_name"],
                    paper_id=paper.id,
                ))
            db.add_all(rows)
            db.flush()
            qids = [r.id for r in rows]
            total_q += len(qids)

            # ---------- 对应的考试卷 ----------
            exam = db.query(models.Exam).filter(
                models.Exam.paper_id == paper.id).first()
            if exam is None:
                exam = models.Exam(
                    title=p["title"],
                    duration=90,
                    pass_score=60,
                    # 真题每卷约 95~100 题，按真题的百分制给分：
                    # 单选 1 分、多选 2 分，满分 100、及格 60
                    single_score=1, fill_score=1,
                    multiple_score=2, judgment_score=1,
                    retake_limit=0,
                    kind="past_paper",
                    paper_id=paper.id,
                    created_by=admin_id,
                )
                db.add(exam)
                created_exams += 1
            exam.title = p["title"]
            exam.kind = "past_paper"
            exam.paper_id = paper.id
            exam.questions = db.query(models.Question).filter(
                models.Question.id.in_(qids)).all()
            exam.total_score = crud._calc_total_score(exam)
            db.flush()
            paper.exam_id = exam.id
            db.flush()

        # ---------- 专业知识清单 ----------
        for k in data.get("knowledge", []):
            items = k.get("questions", [])
            if not items:
                continue
            paper = db.query(models.QuestionPaper).filter_by(
                code=k["code"]).first()
            if paper is None:
                paper = models.QuestionPaper(code=k["code"])
                db.add(paper)
                created_papers += 1
            paper.title = k["title"]
            paper.kind = "knowledge"
            paper.source_file = k["title"]
            paper.question_count = len(items)
            db.flush()

            old = db.query(models.Question).filter(
                models.Question.paper_id == paper.id).all()
            for q in old:
                db.delete(q)
            db.flush()

            rows = []
            for it in items:
                stem = it.get("stem", "").strip()
                ans = it.get("answer", "").strip()
                if not stem or not ans:
                    continue
                rows.append(models.Question(
                    type="fill",
                    content=f"<p>{stem}<u>&emsp;&emsp;&emsp;&emsp;</u></p>",
                    options="{}",
                    answer=ans,
                    analysis="",
                    category=it.get("category") or k.get("category_default", ""),
                    paper_id=paper.id,
                ))
            db.add_all(rows)
            total_q += len(rows)
            db.flush()

        if apply:
            db.commit()
            print(f"[load] 已写库：卷宗 {created_papers} 条，题目 {total_q} 道，"
                  f"考试卷 {created_exams} 张")
        else:
            db.rollback()
            print(f"[load] 试运行（未写库）：将新增卷宗 {created_papers} 条，"
                  f"题目 {total_q} 道，考试卷 {created_exams} 张")
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser(description="历年真题导入流水线")
    ap.add_argument("--src", default=r"D:\李海林\医学检验职称考试历年真题",
                    help="PDF 所在目录")
    ap.add_argument("--stage", default="all",
                    choices=["ocr", "parse", "clean", "load", "all"])
    ap.add_argument("--jobs", type=int, default=2, help="OCR 并行进程数")
    ap.add_argument("--dpi", type=int, default=200, help="OCR 渲染 DPI")
    ap.add_argument("--apply", action="store_true", help="真的写库")
    ap.add_argument("--no-llm", action="store_true", help="跳过 LLM 纠错")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.exists():
        print(f"目录不存在：{src}")
        return 1

    if args.stage in ("ocr", "all"):
        stage_ocr(src, args.jobs, args.dpi)
    if args.stage in ("parse", "all"):
        stage_parse(src, jobs=args.jobs)
    if args.stage in ("clean", "all"):
        stage_clean(use_llm=not args.no_llm)
    if args.stage in ("load", "all"):
        stage_load(apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
