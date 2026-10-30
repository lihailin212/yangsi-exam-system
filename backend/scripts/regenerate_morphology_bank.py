"""重建形态学题库：用 E 盘原始图片生成单选题。

用法:
    cd backend && python scripts/regenerate_morphology_bank.py --dry-run
    cd backend && python scripts/regenerate_morphology_bank.py --target prod
    cd backend && python scripts/regenerate_morphology_bank.py --restore-from backups/backup_xxx.json

设计要点:
  * 文件名 = 诊断名。数字是同目录下的去重编号(如 原始细胞1/2/3 是三张不同的图)，
    所以数字要从答案里去掉，但每张图各自出一道题。
  * 两级查重: MD5(字节相同) + dHash(同一张图重新导出过)。
  * 同义写法归并成唯一规范答案，避免同一形态出现两个"正确答案"。
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import random
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
BACKUP_DIR = BACKEND_DIR / "backups"
LOCAL_DB = BACKEND_DIR / "exam.db"
SRC_ROOT = Path(r"E:\细胞形态学图片\杨思医院检验科形态学考核题库原始图片")
WORK_DIR = BACKEND_DIR / "uploads" / "images" / "morph"
BLOB_PREFIX = "images/morph"
RANDOM_SEED = 20261030
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

CATEGORY_BY_SUB = {
    "血细胞": "形态学/血细胞形态学",
    "寄生虫": "形态学/寄生虫形态学",
    "尿沉渣": "形态学/尿沉渣形态学",
    "其他体液": "形态学/其他体液形态学",
}
STEM_BY_SUB = {
    "血细胞": "请选择下图所示的血细胞名称",
    "寄生虫": "请选择下图所示的寄生虫名称",
    "尿沉渣": "请选择下图所示的尿沉渣成分名称",
    "其他体液": "请选择下图所示的细胞或成分名称",
}

# 逐图确认过的答案覆盖：文件名只写了泛称，看图确认后给出准确答案
FILE_LABEL_OVERRIDE = {
    "其他/寄生虫/疟原虫.png": "疟原虫环状体",          # 环状体，箭头所指
    "其他/寄生虫/疟原虫 (2).png": "疟原虫配子体",      # 香蕉形配子体
    "其他/其他体液/真菌.jpg": "真菌菌丝",              # 有隔菌丝，箭头所指
    "2025国家第一次室间形态学图片/尿沉渣/真菌.jpg": "真菌孢子",   # 卵圆形酵母样细胞
    "2025年寄生虫形态学国家室间质评及答案/寄生虫/真菌\u00a0.png": "真菌孢子",
}

# 错别字 / 写法规范修正
TYPO_FIX = {
    "中幼红（胞间桥）": "中幼红细胞（胞间桥）",
    "chediak-higashi颗粒": "Chediak-Higashi 颗粒",
}

# 同族标签：互为上位/下位或形态高度重叠，同一道题里不能同时出现，
# 否则会出现"两个正确答案"。生成干扰项时整族排除。
FAMILY_GROUPS = [
    ["癌细胞", "腺癌细胞", "恶性肿瘤细胞"],
]


CONFUSABLE_FILE = Path(__file__).with_name("morphology_confusables.json")


def load_confusables():
    """形态易混淆对照表：标签 -> 容易看混的标签(按优先级)"""
    if not CONFUSABLE_FILE.exists():
        return {}
    return json.loads(CONFUSABLE_FILE.read_text(encoding="utf-8"))


def build_family_map():
    m = collections.defaultdict(set)
    for group in FAMILY_GROUPS:
        for x in group:
            m[x] |= set(group)
    return m


FAMILY_MAP = build_family_map()

# 人工复核、不自动出题的文件（文件名含多个成分或答案不唯一）
MANUAL_LABELS = {
    "四联球菌2链杆菌",
    "肾小管上皮细胞管型（上皮细胞管型）混合管型（混合细胞管型）",
    "血小板或红细胞",
}

# 同义归并：每组第一个是规范答案，其余写法并入
SYNONYM_GROUPS = [
    ["Auer小体", "auer小体", "奥氏小体", "奥氏小体（Auer rod）"],
    ["杜勒小体", "Dohle小体"],
    ["口形红细胞", "口型红细胞"],
    ["靶形红细胞", "靶型红细胞"],
    ["锯齿形红细胞", "锯齿型红细胞"],
    ["红细胞碎片", "裂红细胞", "裂红细胞（红细胞碎片）"],
    ["红细胞缗钱状排列", "缗钱状排列红细胞"],
    ["嗜多色红细胞", "嗜多色性红细胞", "噬多色红细胞"],
    ["巨大血小板", "巨、大血小板"],
    ["骨髓瘤细胞", "多发性骨髓瘤细胞"],
    ["血小板卫星现象", "单核细胞血小板卫星现象", "淋巴细胞血小板卫星现象", "中性粒细胞血小板卫星现象"],
    ["巨噬细胞", "巨噬细胞（组织细胞）"],
    ["肥大细胞", "肥大细胞或组织嗜碱细胞"],
    ["中性中幼粒细胞", "中性中幼粒", "中性中幼粒细胞-误认早幼粒细胞"],
    ["多分叶中性粒细胞", "多分叶核中性粒细胞", "中性粒细胞多分叶现象", "分叶过多的中性粒细胞", "中性粒细胞分叶过多"],
    ["原始单核细胞", "幼稚单核细胞"],
    ["篮细胞", "篮细胞（涂抹细胞）"],
    ["戈谢细胞", "戈谢细胞（Gaucher’s cell）"],
    ["多颗粒中性粒细胞（中毒颗粒）", "含中毒颗粒的中性粒细胞"],
    ["巨杆状核粒细胞", "巨（中性）杆状核粒细胞"],
    ["巨幼变幼红细胞", "类或巨幼变幼红细胞", "巨幼变幼红细胞-核幼浆老"],
    ["吞噬细胞", "吞噬焦磷酸钙结晶的吞噬细胞"],
    ["卡波氏环", "卡波环"],
    ["钩虫卵", "够虫卵", "钩虫（虫卵）"],
    ["钩虫成虫", "钩虫杆状蚴"],
    ["疟原虫滋养体", "疟原虫（滋养体）"],
    ["疟原虫环状体", "疟原虫（环状体）"],
    ["疟原虫裂殖体", "疟原虫（裂殖体）", "间日疟原虫裂殖体"],
    ["疟原虫配子体", "疟原虫雌性配值体"],
    ["华支睾吸虫卵", "肝吸虫卵", "肝吸虫卵(华支睾吸虫卵)", "肝吸虫卵（华支睾吸虫卵）", "华支睾吸虫（虫卵）"],
    ["绦虫卵", "绦虫卵（六钩幼）", "带绦虫（虫卵）"],
    ["蛔虫卵", "蛔虫卵（受精）", "蛔虫卵(受精)", "蛔虫卵(受精)-误认血吸虫卵", "受精蛔虫卵", "蛔虫卵(未受精)"],
    ["蛔虫成虫", "蛔虫（成虫）"],
    ["蛲虫卵", "蛲虫（虫卵）"],
    ["鞭虫卵", "鞭虫（虫卵）"],
    ["阿米巴包囊", "溶组织内阿米巴包囊"],
    ["蓝氏贾第鞭毛虫包囊"],
    ["蓝氏贾第鞭毛虫滋养体", "篮氏贾第鞭毛虫滋养体"],
    ["姜片虫卵", "布氏姜片虫"],
    ["牛带绦虫孕节", "牛肉绦虫孕节"],
    ["真菌孢子", "真菌（孢子）"],
    ["真菌菌丝", "真菌（菌丝）"],
    ["疥螨", "螨虫"],
    ["夏科-雷登结晶", "夏科莱登结晶"],
    ["环形红细胞（面包圈样）", "环形红细胞-面包圈样"],
    ["底层移行上皮细胞", "底层尿路上皮细胞", "上皮细胞-底层尿路上皮细胞"],
    ["移行上皮细胞", "中层移行上皮细胞", "表层移行上皮细胞"],
    ["磷酸铵镁结晶", "磷酸铵镁结晶（三联磷酸盐结晶）", "磷酸铵镁结晶（三联磷酸盐）", "磷酸铵镁结晶-误认磷酸钙结晶"],
    ["蜡样管型", "腊样管型"],
    ["红细胞", "正常红细胞"],
    ["尿酸钠结晶", "尿酸钠或磷酸钙结晶"],
    ["恶性肿瘤细胞", "恶行肿瘤细胞"],
    ["嗜碱性粒细胞", "嗜碱性粒细胞（肥大细胞）", "组织嗜碱细胞（肥大细胞）"],
    ["中性粒细胞", "中性粒细胞（杆状核或分叶核）"],
    ["纤毛柱状上皮细胞", "柱状上皮细胞"],
    ["间皮细胞", "双核间皮细胞"],
    ["巨噬细胞", "巨噬细胞（组织细胞）", "巨噬细胞-含铁血黄素", "巨噬细胞（含红细胞）", "泡沫细胞", "噬血细胞"],
    ["黏液丝", "粘液丝"],
    ["中层移行上皮细胞", "移行上皮细胞（中层）"],
    ["表层移行上皮细胞", "移行上皮细胞（表层）"],
    ["夏科-雷登结晶", "夏科莱登结晶", "Charcot-Leyden 结晶", "Charcot-Leyden结晶"],
]

def _squash(s):
    return re.sub(r"\s+", "", s or "")


def build_canonical_map():
    """同义写法 -> 规范答案（查表时忽略空白，兼容 "Auer 小体" / "Auer小体"）"""
    m = {}
    for group in SYNONYM_GROUPS:
        canonical = group[0]
        for variant in group:
            m[_squash(variant)] = canonical
    return m


CANON = build_canonical_map()


def clean_name(filename):
    """文件名 -> 去掉副本标记、补全括号、去首尾空白的原始标签"""
    s = os.path.splitext(filename)[0].replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"[\(（]\s*\d+\s*[\)）]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.count("（") > s.count("）"):
        s += "）"
    if s.count("(") > s.count(")"):
        s += ")"
    return s


def strip_number(s):
    """去掉同目录去重编号：前导数字(可带分隔符)与后缀数字。

    原始细胞1 / 原始细胞2 是三张不同的图，答案都是"原始细胞"。
    """
    s = re.sub(r"^\s*\d+\s*[.、)．]?\s*", "", s)
    s = re.sub(r"[\s_]*\d+$", "", s)
    return s.strip()


def raw_label(filename):
    """文件名 -> 基础标签(去编号、去教学后缀，未做同义归并)"""
    s = clean_name(filename)
    s = strip_number(s)
    s = re.sub(r"[-－]\s*误认[^）)]*", "", s)   # "中性中幼粒细胞-误认早幼粒细胞" -> "中性中幼粒细胞"
    return s.strip()


def base_label(filename, rel=""):
    """文件名 -> 规范答案(去编号 + 同义归并 + 逐图覆盖)"""
    key = rel.replace("\\", "/")
    if key in FILE_LABEL_OVERRIDE:
        return FILE_LABEL_OVERRIDE[key]
    s = raw_label(filename)
    s = TYPO_FIX.get(s, s)
    return CANON.get(_squash(s), s)


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(path, size=16):
    """256-bit 差值哈希，用于识别"同一张图重新导出"的情况"""
    from PIL import Image
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        row = px[r * (size + 1):(r + 1) * (size + 1)]
        for c in range(size):
            bits = (bits << 1) | (1 if row[c] < row[c + 1] else 0)
    return bits


def scan_images():
    """扫描源目录，返回图片清单"""
    items = []
    for root, _dirs, files in os.walk(SRC_ROOT):
        rel = os.path.relpath(root, SRC_ROOT)
        parts = rel.split(os.sep)
        top = parts[0]
        sub = parts[1] if len(parts) >= 2 else ""
        for name in files:
            if os.path.splitext(name)[1].lower() not in IMG_EXT:
                continue
            path = Path(root) / name
            items.append({
                "path": path,
                "rel": str(path.relative_to(SRC_ROOT)),
                "top": top,
                "sub": sub if sub in CATEGORY_BY_SUB else "",
                "filename": name,
            })
    return items


def dedupe(items, log):
    """两级查重：MD5 -> dHash。dHash 只在标签一致时才判定为重复。"""
    by_md5 = collections.defaultdict(list)
    for it in items:
        by_md5[md5_of(it["path"])].append(it)
    kept = []
    for md5, group in by_md5.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        # 同名不同后缀的副本(原始细胞1/2)不会被 MD5 归到一起，这里安全
        winner = sorted(group, key=lambda x: (0 if x["top"] == "其他" else 1, x["rel"]))[0]
        kept.append(winner)
        for other in group:
            if other is winner:
                continue
            log.append({"kind": "md5", "kept": winner["rel"], "dropped": other["rel"], "md5": md5})
    kept.sort(key=lambda x: x["rel"])

    hashes = {}
    for it in kept:
        try:
            hashes[id(it)] = dhash(it["path"])
        except Exception as exc:
            print(f"  ! dhash 失败 {it['rel']}: {exc}", file=sys.stderr)

    dropped = set()
    for a, b in itertools.combinations(kept, 2):
        if id(a) in dropped or id(b) in dropped:
            continue
        ha, hb = hashes.get(id(a)), hashes.get(id(b))
        if ha is None or hb is None:
            continue
        dist = bin(ha ^ hb).count("1")
        if dist > 12:
            continue
        if raw_label(a["filename"]) != raw_label(b["filename"]):
            # 同一张图挂了两个不同标签 -> 是错标不是重复，保留
            log.append({"kind": "label_conflict", "a": a["rel"], "b": b["rel"], "distance": dist,
                        "labels": [raw_label(a["filename"]), raw_label(b["filename"])]})
            continue
        winner = a if (a["top"] == "其他" or (b["top"] != "其他" and a["rel"] < b["rel"])) else b
        loser = b if winner is a else a
        dropped.add(id(loser))
        log.append({"kind": "dhash", "kept": winner["rel"], "dropped": loser["rel"], "distance": dist})

    return [it for it in kept if id(it) not in dropped], log

def build_questions(items, seed=RANDOM_SEED):
    """按图片生成单选题"""
    pool = collections.defaultdict(set)          # 分类 -> 可用作干扰项的答案集合
    for it in items:
        pool[it["sub"]].add(it["answer"])
    all_labels = set()
    for s_ in pool.values():
        all_labels |= s_

    rng = random.Random(seed)
    CONFUSABLE = load_confusables()
    letters = ["A", "B", "C", "D"]
    # 答案位置均衡发牌：先按 A/B/C/D 循环铺满再整体洗牌，四档数量几乎相等
    deck = [letters[i % 4] for i in range(len(items))]
    rng.shuffle(deck)

    questions = []
    for idx, it in enumerate(items):
        answer = it["answer"]
        banned = FAMILY_MAP.get(answer, {answer})
        conf_list = [x for x in CONFUSABLE.get(answer, [])
                     if x in all_labels and x != answer and x not in banned]
        same = [x for x in pool[it["sub"]] if x != answer and x not in banned]
        other = [x for x in all_labels
                 if x != answer and x not in banned and x not in pool[it["sub"]]]
        rng.shuffle(same)
        rng.shuffle(other)
        # 干扰项优先级：形态易混淆 > 同分类随机 > 跨分类随机
        picked = []
        for x in conf_list:
            if x not in picked:
                picked.append(x)
            if len(picked) == 3:
                break
        conf_n = len(picked)
        for x in same + other:
            if len(picked) == 3:
                break
            if x not in picked:
                picked.append(x)
        if len(picked) < 3:
            raise SystemExit(f"干扰项不足: {it['rel']} ({answer})")

        options = picked + [answer]
        rng.shuffle(options)
        # 把正确答案挪到 deck 指定的位置
        target = deck[idx]
        ti, ci = letters.index(target), letters.index(letters[options.index(answer)])
        options[ti], options[ci] = options[ci], options[ti]

        opt_json = {letters[i]: options[i] for i in range(4)}
        content = (
            f"<p>{STEM_BY_SUB[it['sub']]}：</p>"
            f'<img style="max-width:50%" src="{it["url"]}" alt="image" />'
        )
        questions.append({
            "type": "single",
            "content": content,
            "options": json.dumps(opt_json, ensure_ascii=False),
            "answer": target,
            "analysis": "",
            "category": CATEGORY_BY_SUB[it["sub"]],
            "_rel": it["rel"],
            "_answer": answer,
            "_conf_n": conf_n,
        })
    return questions


def build_fill_questions(items):
    """同一批图片再生成一套填空题：没有选项，答案是形态名称文本。"""
    questions = []
    for it in items:
        answer = it["answer"]
        content = (
            f"<p>{STEM_BY_SUB[it['sub']].replace('请选择下图所示的', '请填写下图所示的')}：</p>"
            f'<img style="max-width:50%" src="{it["url"]}" alt="image" />'
        )
        questions.append({
            "type": "fill",
            "content": content,
            "options": "{}",
            "answer": fill_answer_for(answer),
            "analysis": "",
            "category": CATEGORY_BY_SUB[it["sub"]],
            "_rel": it["rel"],
            "_answer": answer,
        })
    return questions


def prepare_images(items, workers=8):
    """压缩到本地缓存目录，返回 (本地路径, blob 上传名) 列表"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    prepared = []
    for it in items:
        name = hashlib.sha1(it["rel"].encode("utf-8")).hexdigest()[:10]
        tag = hashlib.sha1(it["filename"].encode("utf-8")).hexdigest()[:6]
        out_name = f"{name}_{tag}.jpg"
        out_path = WORK_DIR / out_name
        if not out_path.exists():
            from PIL import Image
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
        it["blob_name"] = out_name
        it["local_path"] = out_path
        prepared.append(it)
    return prepared


def legacy_blob_name(item):
    """旧版本用的中文名 Blob（第一次跑传上去的），需要清理掉"""
    name = hashlib.sha1(item["rel"].encode("utf-8")).hexdigest()[:8]
    stem = os.path.splitext(item["filename"])[0]
    safe = re.sub(r'[\\/:*?"<>|]+', "_", stem)[:60]
    return f"{name}_{safe}.jpg"


def cleanup_legacy_blobs(items, workers=8):
    """删掉早期用中文名上传的 Blob，避免仓库里留一堆孤儿文件"""
    from concurrent.futures import ThreadPoolExecutor
    try:
        from vercel.blob import sync as blob
    except Exception:
        return
    names = []
    for it in items:
        legacy = legacy_blob_name(it)
        if legacy != it["blob_name"]:
            names.append(legacy)
    if not names:
        return

    def one(name):
        try:
            getattr(blob, "del")(f"{BLOB_PREFIX}/{name}")
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        removed = sum(1 for ok in ex.map(one, names) if ok)
    print(f"  清理旧中文名 Blob: {removed}/{len(names)}")


def upload_to_blob(items, workers=8):
    """上传到 Vercel Blob，写回 url"""
    from concurrent.futures import ThreadPoolExecutor
    from app.storage import upload_bytes

    done = {"n": 0}
    total = len(items)
    map_path = WORK_DIR / "_blob_map.json"
    cached = {}
    if map_path.exists():
        cached = json.loads(map_path.read_text(encoding="utf-8"))
    todo = [it for it in items if it["blob_name"] not in cached]
    for it in todo:
        if it["blob_name"] in cached:
            it["url"] = cached[it["blob_name"]]

    # Blob 公开地址是确定的: {BASE}/images/morph/{文件名}。先 HEAD 抽样验证，
    # 通了就直接用，不必重传。
    from app.storage import storage_public_base
    base = storage_public_base()
    if todo:
        import random as _r
        import urllib.request
        sample = _r.Random(1).sample(todo, min(8, len(todo)))
        ok = True
        for it in sample:
            url = f"{base}/{BLOB_PREFIX}/{it['blob_name']}"
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status != 200:
                        ok = False
            except Exception as exc:
                print(f"  探测失败 {url}: {exc}", flush=True)
                ok = False
        if ok:
            print(f"  抽样验证通过，{len(todo)} 张直接复用已有 Blob 地址", flush=True)
            for it in todo:
                it["url"] = f"{base}/{BLOB_PREFIX}/{it['blob_name']}"
                cached[it["blob_name"]] = it["url"]
            map_path.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  上传完成 0 张，映射库共 {len(cached)} 条")
            return
        print(f"  复用已上传 {total - len(todo)} 张，本次需上传 {len(todo)} 张", flush=True)

    def one(it):
        data = open(it["local_path"], "rb").read()
        last = None
        for _ in range(3):
            try:
                return it, upload_bytes(f"{BLOB_PREFIX}/{it['blob_name']}", data)
            except Exception as exc:
                last = exc
                time.sleep(1.5)
        raise RuntimeError(f"上传失败 {it['rel']}: {last}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for it, url in ex.map(one, todo):
            it["url"] = url
            cached[it["blob_name"]] = url
            done["n"] += 1
            if done["n"] % 50 == 0:
                print(f"  已上传 {done['n']}/{len(todo)}", flush=True)
                map_path.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    map_path.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    for it in items:
        it.setdefault("url", cached.get(it["blob_name"], ""))
    print(f"  上传完成 {len(todo)} 张，映射库共 {len(cached)} 条")
    cleanup_legacy_blobs(items)

BACKUP_TABLES = ["questions", "exams", "exam_question", "exam_records",
                 "exam_attempts", "exam_distributions"]


def make_engine(target):
    from sqlalchemy import create_engine
    if target == "local":
        return create_engine(f"sqlite:///{LOCAL_DB}")
    from db import load_dotenv_local
    load_dotenv_local()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("未找到 DATABASE_URL（检查 .env.local）")
    return create_engine(url.replace("postgres://", "postgresql://"))


def dump_backup(engine, path):
    from sqlalchemy import text
    data = {"created_at": datetime.now().isoformat(), "target": str(engine.url), "tables": {}}
    with engine.connect() as conn:
        for table in BACKUP_TABLES:
            rows = conn.execute(text(f"select * from {table}")).mappings().all()
            data["tables"][table] = [dict(r) for r in rows]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"  已备份 -> {path}")
    for table, rows in data["tables"].items():
        print(f"    {table}: {len(rows)} 行")


def restore_backup(engine, path):
    from sqlalchemy import text
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    with engine.connect() as conn:
        for table in BACKUP_TABLES:
            rows = data["tables"].get(table, [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            for row in rows:
                placeholders = ", ".join(f":{c}" for c in cols)
                conn.execute(text(f"insert into {table} ({', '.join(cols)}) values ({placeholders})"), row)
            print(f"  已恢复 {table}: {len(rows)} 行")
        if engine.dialect.name == "postgresql":
            for table in BACKUP_TABLES:
                conn.execute(text(
                    f"select setval(pg_get_serial_sequence('{table}','id'), "
                    f"coalesce((select max(id) from {table}), 1))"))
        conn.commit()
    print("  恢复完成")


def replace_bank(engine, questions):
    """清掉旧考试/成绩/形态学题，并插入新题"""
    from sqlalchemy import text
    with engine.connect() as conn:
        print("  删除旧考试、成绩、组卷关联...")
        for table in ("exam_distributions", "exam_records", "exam_attempts", "exam_question"):
            conn.execute(text(f"delete from {table}"))
        conn.execute(text("delete from exams"))

        removed = conn.execute(text("delete from questions where category like '形态学/%'")).rowcount
        print(f"  已删除形态学题: {removed} 道")

        print(f"  插入新题: {len(questions)} 道...")
        payload = [{
            "type": q["type"], "content": q["content"], "options": q["options"],
            "answer": q["answer"], "analysis": q["analysis"], "category": q["category"],
        } for q in questions]
        conn.execute(text(
            "insert into questions (type, content, options, answer, analysis, category, created_at) "
            "values (:type, :content, :options, :answer, :analysis, :category, CURRENT_TIMESTAMP)"), payload)
        conn.commit()
    print("  新题已写入")


def create_exam(engine, title, quota, seed=RANDOM_SEED, qtype="single"):
    """按分类配额抽题建考试（qtype 区分单选卷/填空卷）"""
    from sqlalchemy import text
    rng = random.Random(seed + 7)
    picked = []
    with engine.connect() as conn:
        for category, count in quota.items():
            rows = conn.execute(text(
                "select id from questions where category = :c and type = :t order by random()"),
                {"c": category, "t": qtype}).fetchall()
            ids = [r[0] for r in rows]
            if len(ids) < count:
                raise SystemExit(f"{category} 只有 {len(ids)} 题，不足 {count} 题")
            picked += ids[:count]
        rng.shuffle(picked)
        res = conn.execute(text(
            "insert into exams (title, duration, start_time, end_time, pass_score, single_score, "
            "multiple_score, judgment_score, retake_limit, total_score, created_by, created_at) "
            "values (:title, :duration, NULL, NULL, :pass_score, :single_score, :multiple_score, "
            ":judgment_score, :retake_limit, :total_score, NULL, CURRENT_TIMESTAMP) returning id"),
            {"title": title, "duration": 60, "pass_score": 60, "single_score": 1,
             "multiple_score": 20, "judgment_score": 5, "retake_limit": 0,
             "total_score": len(picked)})
        exam_id = res.scalar()
        conn.execute(text("insert into exam_question (exam_id, question_id) values (:e, :q)"),
                     [{"e": exam_id, "q": qid} for qid in picked])
        conn.commit()
    print(f"  考试已创建 id={exam_id}：《{title}》 {len(picked)} 题 / 60 分 / 60 分钟")
    return exam_id, picked


def verify(engine, expected_count, quota):
    from sqlalchemy import text
    with engine.connect() as conn:
        total = conn.execute(text("select count(*) from questions")).scalar()
        morph = conn.execute(text(
            "select count(*) from questions where category like '形态学/%'")).scalar()
        others = conn.execute(text(
            "select count(*) from questions where category not like '形态学/%'")).scalar()
        print(f"  题目总数 {total}（形态学 {morph} + 其他 {others}）")
        for cat in sorted(quota.keys()):
            n = conn.execute(text("select count(*) from questions where category=:c"), {"c": cat}).scalar()
            print(f"    {cat}: {n} 道")
        types = conn.execute(text(
            "select type, count(*) from questions group by type")).fetchall()
        print("  题型分布:", {r[0]: r[1] for r in types})
        fill_bad = conn.execute(text(
            "select count(*) from questions where type = 'fill' "
            "and (answer is null or answer = '' or options <> '{}')")).scalar()
        print(f"  填空题答案/选项异常: {fill_bad}")
        dist = conn.execute(text(
            "select answer, count(*) from questions where category like '形态学/%' "
            "and type = 'single' group by answer")).fetchall()
        print("  单选答案分布:", {r[0]: r[1] for r in dist})
        exams = conn.execute(text("select id, title, duration, total_score, pass_score from exams")).fetchall()
        print("  考试:", [tuple(r) for r in exams])
        bad = conn.execute(text(
            "select count(*) from questions where category like '形态学/%' "
            "and (content not like '%<img%' or options is null or options = '')")).scalar()
        print(f"  缺图/缺选项的题: {bad}")
        return total, morph, others

# 填空题答案的等价写法：用 | 分隔，判分时任一命中即算对。
# 只收"确实指同一个东西"的写法，别把形态上能区分的亚型混进来。
FILL_ALTERNATIVES = {
    "红细胞": "正常红细胞",
    "真菌孢子": "酵母菌",
    "真菌菌丝": "菌丝",
    "疟原虫环状体": "环状体",
    "疟原虫滋养体": "滋养体",
    "疟原虫裂殖体": "裂殖体",
    "疟原虫配子体": "配子体",
    "钩虫卵": "钩虫虫卵",
    "蛔虫卵": "蛔虫虫卵",
    "蛲虫卵": "蛲虫虫卵",
    "鞭虫卵": "鞭虫虫卵",
    "血吸虫卵": "血吸虫虫卵",
    "绦虫卵": "绦虫虫卵",
    "华支睾吸虫卵": "华支睾吸虫虫卵",
    "腺癌细胞": "腺癌",
    "恶性肿瘤细胞": "恶性细胞",
    "中性粒细胞": "中性分叶核粒细胞",
    "原始细胞": "原始粒细胞",
    "中幼红细胞": "中幼红",
    "晚幼红细胞": "晚幼红",
}


def fill_answer_for(label: str) -> str:
    """填空题的标准答案串：规范名 | 可接受写法"""
    alt = FILL_ALTERNATIVES.get(label)
    return f"{label}|{alt}" if alt else label


EXAM_TITLE = "科室形态学考核"
EXAM_QUOTA = {
    "形态学/血细胞形态学": 50,
    "形态学/寄生虫形态学": 20,
    "形态学/尿沉渣形态学": 20,
    "形态学/其他体液形态学": 10,
}


def main():
    ap = argparse.ArgumentParser(description="用 E 盘原始图片重建形态学题库")
    ap.add_argument("--dry-run", action="store_true", help="只扫描和统计，不改数据库、不上传")
    ap.add_argument("--target", default="prod", choices=["prod", "local"], help="prod=Neon 生产库，local=本地 exam.db")
    ap.add_argument("--restore-from", default="", help="从备份 JSON 恢复题库与考试")
    ap.add_argument("--skip-upload", action="store_true", help="复用本地已上传的图片映射")
    args = ap.parse_args()

    # 先加载 .env.local(BLOB_READ_WRITE_TOKEN / DATABASE_URL)，上传在连库之前就要用到
    from db import load_dotenv_local
    load_dotenv_local()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.restore_from:
        engine = make_engine(args.target)
        print("恢复中...")
        restore_backup(engine, Path(args.restore_from))
        return

    print("== 1. 扫描源目录 ==")
    items = scan_images()
    print(f"  找到图片 {len(items)} 张")

    print("== 2. 两级查重 ==")
    items, dedupe_log = dedupe(items, [])
    print(f"  去重后 {len(items)} 张")
    for entry in dedupe_log:
        if entry["kind"] == "label_conflict":
            print(f"  ! 同图不同标签(判为错标，两张都保留): {entry['labels']}")

    print("== 3. 标签归一 ==")
    manual = []
    for it in items:
        label = base_label(it["filename"], it["rel"])
        it["answer"] = label
        if label in MANUAL_LABELS or not it["sub"]:
            manual.append(it)
    items = [it for it in items if it not in manual]
    for it in manual:
        print(f"  - 人工复核，不出题: {it['rel']}")

    labels = collections.defaultdict(collections.Counter)
    for it in items:
        labels[it["sub"]][it["answer"]] += 1
    print(f"  规范标签 {sum(len(v) for v in labels.values())} 个")
    for sub in ("血细胞", "寄生虫", "尿沉渣", "其他体液"):
        print(f"    {sub}: {sum(labels[sub].values())} 张 / {len(labels[sub])} 个标签")

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source": str(SRC_ROOT),
        "image_count": len(items),
        "dedupe_log": dedupe_log,
        "manual_review": [it["rel"] for it in manual],
        "labels": {sub: dict(counter) for sub, counter in labels.items()},
        "items": [{"rel": it["rel"], "answer": it["answer"], "sub": it["sub"]} for it in items],
    }
    manifest_path = BACKUP_DIR / f"morph_manifest_{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  清单 -> {manifest_path}")

    if args.dry_run:
        print("\n[dry-run] 未上传、未修改数据库。")
        return

    print("== 4. 压缩图片 ==")
    prepare_images(items)
    print(f"  本地缓存 -> {WORK_DIR}")

    print("== 5. 上传 Vercel Blob ==")
    upload_to_blob(items)

    print("== 6. 生成题目 ==")
    questions = build_questions(items)
    fill_questions = build_fill_questions(items)
    print(f"  另生成填空题 {len(fill_questions)} 道")
    print(f"  生成 {len(questions)} 道单选题")
    dist = collections.Counter(q["answer"] for q in questions)
    print(f"  答案分布 {dict(sorted(dist.items()))}")
    conf_stat = collections.Counter(q["_conf_n"] for q in questions)
    with_conf = sum(v for k, v in conf_stat.items() if k > 0)
    print(f"  含形态易混淆干扰项: {with_conf}/{len(questions)} 道 "
          f"({conf_stat[3]} 道用满 3 个)")
    no_conf = sorted({q["_answer"] for q in questions if q["_conf_n"] == 0})
    if no_conf:
        print(f"  无易混淆表、回退随机的标签({len(no_conf)}): {'、'.join(no_conf)}")

    print("== 7. 备份现有数据 ==")
    engine = make_engine(args.target)
    backup_path = BACKUP_DIR / f"backup_{stamp}.json"
    dump_backup(engine, backup_path)

    print("== 8. 写入新题库 ==")
    replace_bank(engine, questions + fill_questions)

    print("== 9. 创建默认考试 ==")
    create_exam(engine, EXAM_TITLE, EXAM_QUOTA, qtype="single")
    create_exam(engine, EXAM_TITLE + "(填空题)", EXAM_QUOTA, qtype="fill")

    print("== 10. 校验 ==")
    verify(engine, len(questions), EXAM_QUOTA)

    report = {
        "generated_at": datetime.now().isoformat(),
        "backup": str(backup_path),
        "manifest": str(manifest_path),
        "questions": len(questions),
        "fill_questions": len(fill_questions),
        "answer_dist": dict(dist),
        "labels": {sub: dict(counter) for sub, counter in labels.items()},
        "dedupe_log": dedupe_log,
        "manual_review": [it["rel"] for it in manual],
    }
    report_path = BACKUP_DIR / f"morph_bank_report_{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n报告 -> {report_path}")


if __name__ == "__main__":
    main()
