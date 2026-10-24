"""缺图题目体检：找出题库/考试中引用了图片但图片实际不存在的题目。

背景：形态学考核的题目几乎都带图，一旦图片在对象存储里丢失，考生看到的
就是一道空白题。这个脚本把"图还在不在"变成可以随时跑的体检报告。

检查来源：
    1. 本地磁盘：backend/uploads/images、仓库根 uploads/images、
       以及 RAILWAY_VOLUME_MOUNT_PATH/uploads/images（线上挂载盘）
    2. 对象存储：Vercel Blob 公共地址（HEAD 请求），即生产环境真正对外的地址

用法：
    cd backend && python scripts/audit_missing_images.py                 # 全量体检
    cd backend && python scripts/audit_missing_images.py --exam-id 7     # 只查某场考试
    cd backend && python scripts/audit_missing_images.py --mode local    # 只查本地磁盘
    cd backend && python scripts/audit_missing_images.py --mode blob     # 只查对象存储
    cd backend && python scripts/audit_missing_images.py --json out.json # 导出 JSON 报告

退出码：0=全部正常，1=存在缺图题目，2=检查过程有网络失败（需重跑确认）。
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from db import REPO_DIR, connect, load_dotenv_local

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent

IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)
MARKDOWN_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")

DEFAULT_BLOB_BASE = "https://u2wff8olceezsvlg.public.blob.vercel-storage.com"


def local_dirs():
    """本地可能存放图片的目录（按优先级排列）。"""
    dirs = []
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        dirs.append(pathlib.Path(volume) / "uploads" / "images")
    dirs.append(BACKEND_DIR / "uploads" / "images")
    dirs.append(REPO_DIR / "uploads" / "images")
    return [d for d in dirs if d.is_dir()]


def blob_base_url():
    base = os.environ.get("BLOB_BASE_URL", "").strip() or DEFAULT_BLOB_BASE
    return base.rstrip("/")


def extract_sources(text):
    """从题目富文本里抽出所有图片引用（<img src> 与 markdown 语法）。"""
    if not text:
        return []
    sources = []
    for src in IMG_SRC_RE.findall(text):
        sources.append(src.strip())
    for src in MARKDOWN_IMG_RE.findall(text):
        sources.append(src.strip())
    seen = set()
    ordered = []
    for src in sources:
        if src and src not in seen:
            seen.add(src)
            ordered.append(src)
    return ordered


def normalize(src):
    """把图片引用归一化成一个可检查的键。

    返回 (kind, value)：
        kind == "url"    -> value 是完整外链，直接 HEAD
        kind == "path"   -> value 是 /uploads/images/xxx 之类的站内路径
        kind == "name"   -> value 只是文件名
        kind == "other"  -> 无法识别的引用（如 data: URI）
    """
    raw = src.strip()
    if raw.lower().startswith("data:"):
        return "other", raw[:40]
    if raw.startswith(("http://", "https://", "//")):
        if raw.startswith("//"):
            raw = "https:" + raw
        return "url", raw
    if raw.startswith("/"):
        return "path", raw
    return "name", raw


def filename_of(value):
    """从路径/文件名里取 basename，并去掉查询串与片段。"""
    value = value.split("?")[0].split("#")[0]
    return unquote(os.path.basename(value))


def blob_candidates(kind, value):
    """给出一份该图片在对象存储中可能存在的候选地址。"""
    if kind == "url":
        return [value]
    name = filename_of(value)
    if not name:
        return []
    return [f"{blob_base_url()}/images/{name}"]


def http_check(url, timeout=10, retries=2):
    """对公网地址做一次轻量存在性检查。

    返回 (状态, 说明)，状态为 ok / missing / error。
    只有明确的 404/410 才算 missing；网络抖动等异常归为 error，避免误报缺图。
    """
    last_err = None
    for attempt in range(retries + 1):
        req = Request(url, method="HEAD", headers={"User-Agent": "yangsi-exam-audit/1.0"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                if 200 <= resp.status < 400:
                    return "ok", f"HTTP {resp.status}"
                return "missing", f"HTTP {resp.status}"
        except HTTPError as exc:
            if exc.code in (404, 410):
                return "missing", f"HTTP {exc.code}"
            # 403/401 等说明对象存在，只是不可读
            return "ok", f"HTTP {exc.code}（对象存在但不可读）"
        except (URLError, OSError, ValueError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    return "error", f"请求失败：{last_err}"


def check_image(src, mode, dirs, timeout):
    """检查单个图片引用，返回 (状态, 说明)。状态为 ok / missing / error / skipped。"""
    kind, value = normalize(src)
    if kind == "other":
        return "skipped", "内联/无法识别的引用"

    if mode in ("local", "both"):
        name = filename_of(value if kind != "url" else urlparse(value).path)
        for d in dirs:
            if name and (d / name).exists():
                return "ok", f"本地存在：{d / name}"

    if mode in ("blob", "both"):
        states = []
        for url in blob_candidates(kind, value):
            state, detail = http_check(url, timeout=timeout)
            states.append((state, detail, url))
            if state == "ok":
                return "ok", f"对象存储存在：{url}"
        if states and all(s[0] == "missing" for s in states):
            return "missing", "本地与对象存储均未找到"
        if states:
            return "error", "；".join(f"{s[2]} -> {s[1]}" for s in states)
        return "missing", "无法解析出可检查的地址"

    return "missing", "本地未找到"


def fetch_questions(cur, exam_id=None):
    """取题目及其所属考试（exam_id 为 None 时取全库）。"""
    if exam_id is None:
        cur.execute(
            """
            SELECT q.id, q.type, q.category, q.content,
                   COALESCE(string_agg(e.id::text || ':' || e.title, ' | '), '')
            FROM questions q
            LEFT JOIN exam_question eq ON eq.question_id = q.id
            LEFT JOIN exams e ON e.id = eq.exam_id
            GROUP BY q.id
            ORDER BY q.id
            """
        )
    else:
        cur.execute(
            """
            SELECT q.id, q.type, q.category, q.content,
                   COALESCE(string_agg(e.id::text || ':' || e.title, ' | '), '')
            FROM questions q
            LEFT JOIN exam_question eq ON eq.question_id = q.id
            LEFT JOIN exams e ON e.id = eq.exam_id
            WHERE q.id IN (SELECT question_id FROM exam_question WHERE exam_id = %s)
            GROUP BY q.id
            ORDER BY q.id
            """,
            (exam_id,),
        )
    return cur.fetchall()


def main():
    ap = argparse.ArgumentParser(description="缺图题目体检")
    ap.add_argument("--mode", choices=["both", "local", "blob"], default="both",
                    help="检查范围：both=本地+对象存储（默认），local=只查磁盘，blob=只查对象存储")
    ap.add_argument("--exam-id", type=int, default=None, help="只体检某场考试用到的题目")
    ap.add_argument("--json", dest="json_out", default=None, help="把结果写入 JSON 文件")
    ap.add_argument("--timeout", type=int, default=10, help="单个 URL 超时秒数，默认 10")
    args = ap.parse_args()

    load_dotenv_local()
    dirs = local_dirs()
    print(f"检查模式：{args.mode}")
    print(f"本地图片目录：{', '.join(str(d) for d in dirs) if dirs else '（无）'}")
    print(f"对象存储地址：{blob_base_url()}")

    conn = connect()
    try:
        with conn.cursor() as cur:
            rows = fetch_questions(cur, args.exam_id)
    finally:
        conn.close()

    if not rows:
        print("没有找到题目。")
        return 0

    srcs = []
    for qid, qtype, category, content, exams in rows:
        for src in extract_sources(content):
            srcs.append((qid, src))
    unique_srcs = sorted({src for _, src in srcs})

    print(f"题目数：{len(rows)}，图片引用：{len(srcs)} 处，去重后 {len(unique_srcs)} 个文件\n")

    if args.mode in ("blob", "both") and unique_srcs:
        print("正在检查对象存储...")
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(
                lambda s: (s, check_image(s, args.mode, dirs, args.timeout)),
                unique_srcs,
            ))
    else:
        results = [(s, check_image(s, args.mode, dirs, args.timeout)) for s in unique_srcs]

    status_map = dict(results)

    report = []
    error_report = []
    missing_files = set()
    for qid, qtype, category, content, exams in rows:
        bad = []
        failed = []
        for src in extract_sources(content):
            status, detail = status_map.get(src, ("error", "未检查"))
            if status == "missing":
                bad.append((src, detail))
                missing_files.add(filename_of(src))
            elif status == "error":
                failed.append((src, detail))
        if bad:
            report.append({
                "question_id": qid,
                "type": qtype,
                "category": category,
                "exams": exams,
                "missing": [{"src": s, "file": filename_of(s), "detail": d} for s, d in bad],
            })
        if failed:
            error_report.append({
                "question_id": qid,
                "type": qtype,
                "category": category,
                "exams": exams,
                "failed": [{"src": s, "file": filename_of(s), "detail": d} for s, d in failed],
            })

    print("=" * 72)
    if report:
        print(f"发现 {len(report)} 道缺图题目，涉及 {len(missing_files)} 个图片文件：\n")
        for item in report:
            files = ", ".join(m["file"] for m in item["missing"])
            print(f"  [题 {item['question_id']}] {item['category'] or '(无分类)'} | 缺图: {files}")
            print(f"      使用于考试: {item['exams'] or '（未被任何考试引用）'}")
    else:
        print("未发现缺图题目，所有图片引用均可访问。")
    if error_report:
        print(f"\n另有 {len(error_report)} 道题目检查失败（网络/服务异常，非缺图），建议稍后重试：")
        for item in error_report:
            files = ", ".join(f"{m['file']}" for m in item["failed"])
            print(f"  [题 {item['question_id']}] {item['category'] or '(无分类)'} | 检查失败: {files}")
    print("=" * 72)

    if args.json_out:
        payload = {
            "mode": args.mode,
            "exam_id": args.exam_id,
            "question_count": len(rows),
            "image_ref_count": len(srcs),
            "unique_image_count": len(unique_srcs),
            "missing_question_count": len(report),
            "failed_question_count": len(error_report),
            "missing_files": sorted(missing_files),
            "questions": report,
            "failed_questions": error_report,
        }
        pathlib.Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON 报告已写入 {args.json_out}")

    if report:
        return 1
    if error_report:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
