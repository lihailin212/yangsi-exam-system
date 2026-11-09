# -*- coding: utf-8 -*-
"""把《医学检验技师题库》Excel 里的题目导入线上题库（questions 表）。

Excel 的结构（每个科目一个 sheet）：
    第 1 行起  ：章节大纲（章节编号 / 章节名称 / 题目数量 / 备注）
    「练习题目」行之后：
                 题号 / 题型 / 题目内容 / 选项A-D / 正确答案 / 章节 / 备注

导入规则：
  - 分类 = 「科目/章节名」，例如「临床血液学检验/红细胞检验」。
    题库页的分类是按 "/" 分成两级级联选择器的，这个命名正好对上。
  - 题干写成 <p>…</p>，和其他导入进来的题一致（前端用 v-html 渲染）。
  - 选项按 A/B/C/D 存成 JSON；正确答案沿用 Excel 里的字母。
  - 归入普通题库（paper_id 为空），不挂到任何历年真题卷上。
  - 按题干判重：题库里已经有的题跳过，脚本可以重复跑。

用法：
    cd backend && python scripts/import_excel_question_bank.py --dry-run
    cd backend && python scripts/import_excel_question_bank.py
    cd backend && python scripts/import_excel_question_bank.py --file "D:\\path\\其他题库.xlsx"
"""
import argparse
import json
import pathlib
import re
import sys

import openpyxl

from db import connect

DEFAULT_XLSX = pathlib.Path(__file__).with_name("医学检验技师题库.xlsx")

# Excel 里的题型 → 题库 type
TYPE_MAP = {
    "单选题": "single", "单选": "single", "single": "single",
    "多选题": "multiple", "多选": "multiple", "multiple": "multiple",
    "判断题": "judgment", "判断": "judgment", "judgment": "judgment",
    "填空题": "fill", "填空": "fill", "fill": "fill",
}
OPTION_COLS = {"A": 4, "B": 5, "C": 6, "D": 7}   # 选项A-D 在第 4~7 列
ANSWER_COL = 8        # 正确答案
CHAPTER_COL = 9       # 章节
NOTE_COL = 10         # 备注


def norm_text(text: str) -> str:
    """去掉 HTML 标签和空白，用来判重。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", "", text)


def cell(ws, row, col):
    v = ws.cell(row, col).value
    return "" if v is None else str(v).strip()


def parse_sheet(ws):
    """从一个 sheet 里解析出 (章节大纲, 题目列表)。"""
    # ---- 1. 章节大纲 ----
    outline = {}
    outline_rows = []
    for r in range(1, ws.max_row + 1):
        a = cell(ws, r, 1)
        b = cell(ws, r, 2)
        if a == "章节编号":
            continue
        if re.fullmatch(r"第\d+章", a) and b:
            outline[a] = b
            outline_rows.append((a, b, cell(ws, r, 3), cell(ws, r, 4)))

    # ---- 2. 题目表头 ----
    header_row = None
    for r in range(1, ws.max_row + 1):
        if cell(ws, r, 1) == "题号":
            header_row = r
            break
    if header_row is None:
        return outline, outline_rows, []

    questions = []
    for r in range(header_row + 1, ws.max_row + 1):
        no = cell(ws, r, 1)
        if not no or not no.isdigit():
            continue
        stem = cell(ws, r, 3)
        if not stem:
            continue
        qtype = TYPE_MAP.get(cell(ws, r, 2), "single")
        options = {}
        for key, col in OPTION_COLS.items():
            val = cell(ws, r, col)
            if val:
                options[key] = val
        answer = cell(ws, r, ANSWER_COL).upper()
        chapter = cell(ws, r, CHAPTER_COL)
        note = cell(ws, r, NOTE_COL)
        questions.append({
            "no": int(no),
            "type": qtype,
            "stem": stem,
            "options": options,
            "answer": answer,
            "chapter": chapter,
            "note": note,
            "row": r,
        })
    return outline, outline_rows, questions


def main():
    ap = argparse.ArgumentParser(description="导入 Excel 题库到 questions 表")
    ap.add_argument("--file", default=str(DEFAULT_XLSX), help="Excel 路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要写入的题，不写库")
    ap.add_argument("--skip-summary", action="store_true", help="跳过「考试信息汇总」这类说明页")
    args = ap.parse_args()

    path = pathlib.Path(args.file)
    if not path.exists():
        raise SystemExit(f"文件不存在：{path}")

    wb = openpyxl.load_workbook(path, data_only=True)

    # 题库里已有的题干（判重用）
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT content FROM questions")
    seen = {norm_text(r[0]) for r in cur.fetchall()}
    print(f"题库现有题干 {len(seen)} 条，开始比对\n")

    created = skipped = 0
    per_subject = []
    for ws in wb.worksheets:
        outline, outline_rows, questions = parse_sheet(ws)
        if not questions:
            if outline_rows and not args.skip_summary:
                per_subject.append((ws.title, outline_rows, 0, 0))
            continue

        subject = ws.title
        added = 0
        for q in questions:
            key = norm_text(q["stem"])
            if key in seen:
                print(f"[跳过] [{subject}] 第{q['no']}题 题干已存在：{q['stem'][:32]}")
                skipped += 1
                continue

            chapter_name = outline.get(q["chapter"], q["chapter"] or "未分章")
            category = f"{subject}/{chapter_name}"
            content = f"<p>{q['stem']}</p>"
            options_json = json.dumps(q["options"], ensure_ascii=False)

            extra = f"  # {q['note']}" if q["note"] else ""
            print(f"[新增] [{subject}] 第{q['no']}题 {category}  答案={q['answer']}  {q['stem'][:28]}{extra}")

            if not args.dry_run:
                cur.execute(
                    "INSERT INTO questions (type, content, options, answer, analysis, category, "
                    "paper_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, NULL, NOW())",
                    (q["type"], content, options_json, q["answer"], "", category),
                )
            seen.add(key)
            created += 1
            added += 1

        per_subject.append((subject, outline_rows, len(questions), added))

        # 顺手把这一科的章节大纲打印出来，方便对照
        if outline_rows:
            print(f"       {subject} 共 {len(outline_rows)} 章："
                  + "、".join(f"{a}{b}" for a, b, _, _ in outline_rows))
            print()

    if not args.dry_run:
        conn.commit()
    else:
        conn.rollback()
    conn.close()

    tag = "[试运行]" if args.dry_run else "[完成]"
    print(f"{tag} 新增 {created} 题，跳过（已存在）{skipped} 题")
    print("\n=== 分科统计 ===")
    for subject, outline_rows, total, added in per_subject:
        if total:
            print(f"  {subject}: Excel {total} 题，新增 {added} 题，章节 {len(outline_rows)} 个")
        else:
            print(f"  {subject}: 章节大纲 {len(outline_rows)} 个（无题目）")


if __name__ == "__main__":
    main()
