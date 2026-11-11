# -*- coding: utf-8 -*-
"""从 GitHub 开源题库仓库导入「医学检验」相关题目。

数据源：github.com/lengfeng650-star/medical-exam-question-bank-json
        （Apache License 2.0，data/subjects/ 下的分类 JSON）

只取和医学检验相关的分类（临床医学检验技术、输血技术、微生物检验技术、
理化检验技术等），别的科目（放射、口腔、超声…）不碰。

每个 JSON 的结构：
    { "title": "前列腺液检查",
      "questions": [ { "title": 题干, "options": ["A.文本", ...],
                       "analysis": 解析, "answer": "B" } ] }

题目类型按选项前缀判断：选项带 A/B/C 前缀的是单选；
不带前缀的是"备选答案共用"（配伍题），本题库里的这类题实际都是单选，
统一按 single 处理。

用法：
    cd backend && python scripts/import_open_question_bank.py --dry-run
    cd backend && python scripts/import_open_question_bank.py --apply

默认先下载 zip 到 backend/.cache/gh_qbank/，已下载过就复用。
导入前会先备份题库（scripts/backup_question_bank.py 的逻辑）。
"""
import argparse
import collections
import datetime
import html
import io
import json
import os
import pathlib
import re
import shutil
import sys
import urllib.request
import zipfile

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

CACHE_DIR = BACKEND / ".cache" / "gh_qbank"
ZIP_PATH = CACHE_DIR / "repo.zip"
DOWNLOAD_URL = ("https://codeload.github.com/"
                "lengfeng650-star/medical-exam-question-bank-json/zip/refs/heads/main")

# 只要这些分类。匹配"分类文件夹名"里含这些关键词的。
SUBJECT_KEYWORDS = [
    "检验", "卫生检验", "微生物检验", "输血技术", "理化检验",
    "检验医学科", "医学检验", "临床医学检验",
]
# 排除掉明显不是医学检验方向的
SUBJECT_EXCLUDE = ["影像", "口腔", "超声", "放射", "核医学", "康复"]

# 章节名里出现这些词的，是中级职称的"人文公共科目"（政治理论、行测常识），
# 不是医学检验知识，对检验科的考生没用，直接不要。
CHAPTER_EXCLUDE = [
    "马克思主义", "毛泽东思想", "中国特色社会主义", "公共科目",
    "常识判断", "人文历史", "哲学政治", "自然科技", "地理国情",
    "言语理解", "数量分析", "判断推理", "策略选择",
    "法律法规常识", "医药卫生常识",
]

OPTION_PREFIX_RE = re.compile(r"^\s*([A-Ea-e])\s*[.．、]\s*(.+)$", re.S)


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


def ensure_zip(force=False):
    """确保 zip 存在；不在了就下一份（整个仓库约 15MB，一次下载即可）。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists() and not force:
        print(f"[import] 复用已下载的数据包 {ZIP_PATH}")
        return ZIP_PATH
    print("[import] 下载开源题库数据包（约 15MB）...")
    req = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "codex"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = resp.read()
    ZIP_PATH.write_bytes(data)
    print(f"[import] 已保存 {ZIP_PATH}（{len(data) // 1024} KB）")
    return ZIP_PATH


def relevant_subjects(subs):
    out = {}
    for name, files in subs.items():
        if any(w in name for w in SUBJECT_EXCLUDE):
            continue
        if any(w in name for w in SUBJECT_KEYWORDS):
            out[name] = files
    return out


def collect_subjects(z):
    subs = collections.defaultdict(list)
    for n in z.namelist():
        parts = n.split("/")
        # data/subjects/<分类>/<文件>.json
        if len(parts) > 3 and parts[2] == "subjects" and parts[-1].endswith(".json"):
            subs[parts[3]].append(n)
    return subs


def clean_text(s):
    """去掉 HTML 标签、空白，压成一行。"""
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html.unescape(s)
    s = re.sub(r"[\s\u3000]+", " ", s)
    return s.strip()


def norm_key(s):
    """判重用的键：去掉所有非字词字符。"""
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"[\s\W_]+", "", s)


def parse_file(z, name, subj):
    """一个 JSON 文件 -> 题目列表。"""
    try:
        data = json.loads(z.read(name).decode("utf-8"))
    except Exception as e:
        print(f"  跳过（读不出来）{name}: {e}")
        return []
    chapter = clean_text(data.get("title") or "")
    if any(w in chapter for w in CHAPTER_EXCLUDE):
        return []
    out = []
    for q in data.get("questions") or []:
        stem = clean_text(q.get("title") or "")
        if not stem:
            continue
        raw_opts = q.get("options") or []
        options = {}
        for i, opt in enumerate(raw_opts):
            opt = clean_text(str(opt))
            if not opt:
                continue
            m = OPTION_PREFIX_RE.match(opt)
            if m:
                key, text = m.group(1).upper(), m.group(2).strip()
            else:
                # 没写字母的按顺序补 A/B/C…（配伍题的共用备选答案）
                key, text = chr(ord("A") + i), opt
            if not text or key in options:
                continue
            options[key] = text
        answer = clean_text(str(q.get("answer") or "")).upper()
        if answer not in options:
            continue
        if len(options) < 2:
            continue
        analysis = clean_text(q.get("analysis") or "")
        out.append({
            "type": "single",
            "stem": stem,
            "options": options,
            "answer": answer,
            "analysis": analysis,
            # 分类用「科目/章节」两级，和 Excel 题库导入的命名一致
            # （题库页的级联选择器正好按 "/" 分两级，超过两级就选不到了）。
            "category": f"{subj}/{chapter}" if chapter else subj,
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="导入 GitHub 开源医学检验题库")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库（默认行为）")
    ap.add_argument("--apply", action="store_true", help="真的写库")
    ap.add_argument("--redownload", action="store_true", help="强制重新下载数据包")
    args = ap.parse_args()
    if args.apply and args.dry_run:
        sys.exit("--dry-run 和 --apply 不能同时用")

    zip_path = ensure_zip(force=args.redownload)
    z = zipfile.ZipFile(zip_path)
    subs = collect_subjects(z)
    rel = relevant_subjects(subs)
    print(f"[import] 分类目录 {len(subs)} 个，其中医学检验相关 {len(rel)} 个")

    questions = []
    for subj in sorted(rel):
        got = []
        for name in rel[subj]:
            got.extend(parse_file(z, name, subj))
        if got:
            print(f"  {subj}: {len(got)} 题")
            questions.extend(got)
    print(f"[import] 共解析出 {len(questions)} 道题")

    # 内部去重（同一个题干在多个文件里重复出现）
    seen = set()
    uniq = []
    for q in questions:
        k = norm_key(q["stem"])
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(q)
    print(f"[import] 去掉内部重复后 {len(uniq)} 道")

    if not args.apply:
        print("[import] --dry-run，未写库（加 --apply 才会真正导入）")
        _print_preview(uniq)
        return

    load_dotenv_local()
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("未找到 DATABASE_URL")
    conn = psycopg2.connect(url.replace("postgres://", "postgresql://"))
    try:
        cur = conn.cursor()
        # 库里已有的题干，用来跳过重复
        cur.execute("SELECT content FROM questions")
        existing = {norm_key(r[0]) for r in cur.fetchall()}
        print(f"[import] 库里已有 {len(existing)} 个不重复题干")

        rows = []
        skipped = 0
        for q in uniq:
            k = norm_key(q["stem"])
            if k in existing:
                skipped += 1
                continue
            existing.add(k)
            rows.append((
                q["type"],
                f"<p>{q['stem']}</p>",
                json.dumps(q["options"], ensure_ascii=False),
                q["answer"],
                q["analysis"],
                q["category"],
            ))
        print(f"[import] 新增 {len(rows)} 道，跳过已存在 {skipped} 道")

        if not rows:
            print("[import] 没有新题，不用写")
            return
        from psycopg2.extras import execute_values
        # created_at 必须显式写：Column(default=...) 是 SQLAlchemy 的 Python 侧默认值，
        # 裸 SQL 走不到 ORM，不写就是 NULL，而 QuestionOut.created_at 要求 datetime，
        # 会让所有取到这道题的接口 500。
        execute_values(cur, """
            INSERT INTO questions (type, content, options, answer, analysis, category, created_at)
            VALUES %s
        """, [(r[0], r[1], r[2], r[3], r[4], r[5], datetime.utcnow()) for r in rows],
            page_size=200)
        conn.commit()
        print(f"[import] 已写入 {len(rows)} 道题")

        cur.execute("SELECT category, count(*) FROM questions WHERE category IN %s GROUP BY category ORDER BY 2 DESC",
                    (tuple(sorted({r[5] for r in rows})),))
        print("[import] 导入后的分类分布：")
        for c, n in cur.fetchall():
            print(f"    {n:5d}  {c}")
    finally:
        conn.close()


def _print_preview(uniq):
    print("\n[import] 样例：")
    for q in uniq[:5]:
        print(f"  题干：{q['stem'][:60]}")
        print(f"  选项：{q['options']}")
        print(f"  答案：{q['answer']}   分类：{q['category']}")
        print()


if __name__ == "__main__":
    main()
