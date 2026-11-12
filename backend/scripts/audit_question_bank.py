# -*- coding: utf-8 -*-
"""题库文字与结构体检脚本。

查两类问题：
  1. 错别字——相邻重复的汉字、虚词重复、单个拉丁字母误插进中文词里
     （比如输入法切到英文多敲了一个字母："E常人"）
  2. 术语/结构错误——答案字母越界、选项内容重复、"以上都"类选项不在最后、
     题型和答案个数对不上、人工维护的常见术语错写对照表

只读脚本：只打印问题清单，不改数据。确认后用
scripts/fix_question_text.py 逐条改。

用法：
    cd backend && python scripts/audit_question_bank.py
    cd backend && python scripts/audit_question_bank.py --category 妇科普查
"""
import argparse
import json
import os
import pathlib
import re
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from db import connect

# 合法叠词：这些重复字是正常的，不算错别字
REDUP_OK = {
    "天天", "年年", "日日", "月月", "时时", "家家", "人人", "个个", "处处",
    "事事", "件件", "层层", "重重", "圆圆", "弯弯", "点点", "面面", "高高",
    "大大", "多多", "好好", "明明", "偏偏", "恰恰", "刚刚", "常常", "往往",
    "渐渐", "仅仅", "慢慢", "悄悄", "深深", "轻轻", "淡淡", "微微", "稍稍",
    "频频", "连连", "历历", "声声", "步步", "条条", "星星", "团团", "一一",
    "不不", "每每", "种种", "隐隐", "累累", "稍稍", "略略", "多多", "久久",
    "屡屡", "累累", "历历", "茫茫", "滔滔", "滚滚", "熊熊", "通红", "漆黑",
    # 医学语境里合法的叠词
    "病病", "瘤瘤", "瘤瘤", "疝疝", "疮疮", "癣癣", "痔痔", "疣疣",
    # 分光光度计、葡萄糖这类词本身就有重复字
    "光光", "萄萄", "脲脲", "溶溶", "六六", "徐徐", "远远", "多多",
    "乳乳", "痛痛", "腺腺", "津津", "稍稍", "脉脉", "痒痒",
    "微微", "略略", "频频", "连连", "往往", "渐渐", "仅仅",
}

# 这些字后面跟单个拉丁字母是正常的（抗原、抗体、维生素A、X型…）
LATIN_OK_PREFIX = set("抗维生素型亚第含或和及与的于及为对于用仅第")
LATIN_OK_SUFFIX = set("型线片剂素蛋白细胞抗原抗体感染肿瘤癌瘤综合征")

# 常见术语错写 → 正确写法（人工维护）
TERM_FIXES = {
    "促甲肾上腺素": "促肾上腺皮质激素",
    "甲旁腺": "甲状旁腺",
    "肠上皮细胞": "肠上皮细胞",
    "冠状动脉": "冠状动脉",
}

# 「以上都」类选项：应该放在最后一个
ALL_OF = ("以上都", "以上皆是", "以上均", "都正确", "以上选项", "以上说法", "上述都")


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def check_dup_chars(text: str):
    """相邻重复的汉字（排除合法叠词）。"""
    hits = []
    for m in re.finditer(r"([一-龥])\1", text):
        bigram = m.group(0)
        if bigram in REDUP_OK:
            continue
        hits.append((m.start(), bigram))
    return hits


def check_latin_single(text: str):
    """中文里夹了单个拉丁字母（连续 2 个以上字母不算）。"""
    hits = []
    for m in re.finditer(r"([一-龥])([A-Za-z])([一-龥])", text):
        prev, letter, nxt = m.group(1), m.group(2), m.group(3)
        if prev in LATIN_OK_PREFIX or nxt in LATIN_OK_SUFFIX:
            continue
        hits.append((m.start(), m.group(0)))
    return hits


def main():
    ap = argparse.ArgumentParser(description="题库文字与结构体检")
    ap.add_argument("--category", help="只查某个分类")
    ap.add_argument("--limit", type=int, default=60, help="每类问题最多打印几条")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()
    # 传了参数，SQL 里的 % 要写成 %%（psycopg2 会把 % 当占位符）
    sql = ("select id, type, category, content, options, answer, analysis "
           "from questions where content not like '<p>[SYSTEM_CATEGORY]%%'")
    params = []
    if args.category:
        sql += " and category = %s"
        params.append(args.category)
    cur.execute(sql, params)
    rows = cur.fetchall()
    print(f"共检查 {len(rows)} 道题\n")

    findings = []   # (类别, 题号, 分类, 说明)

    for qid, qtype, category, content, options_raw, answer, analysis in rows:
        content_txt = strip_html(content)
        full = content_txt + " " + strip_html(analysis)
        try:
            options = json.loads(options_raw or "{}")
        except (TypeError, ValueError):
            options = {}

        # --- 结构问题 ---
        # 填空题的答案是文字、选项为空，判断题的答案是「正确/错误」，
        # 这两类本来就不是 A/B/C/D，按字母查会全是误报。
        is_fill = qtype == "fill"
        is_judgment = qtype == "judgment"
        ans = [a.strip() for a in (answer or "").split(",") if a.strip()]
        letter_answers = [a for a in ans if len(a) == 1 and a.isalpha()]

        if not norm(content_txt):
            findings.append(("空题干", qid, category, "题干是空的"))
        if not options and not is_fill:
            findings.append(("无选项", qid, category, "选项为空"))
        if options and letter_answers:
            for a in letter_answers:
                if a not in options:
                    findings.append(("答案越界", qid, category,
                                     f"答案 {a} 不在选项 {'/'.join(sorted(options))} 里"))
        if qtype == "multiple" and len(letter_answers) == 1 and options:
            findings.append(("题型答案不符", qid, category,
                             f"多选题只有一个答案 {letter_answers[0]}"))
        if qtype == "single" and len(letter_answers) > 1:
            findings.append(("题型答案不符", qid, category,
                             f"单选题却有多个答案 {','.join(letter_answers)}"))
        # 选项内容重复（A3 型题是共用选项，属于正常）
        if options and "A3" not in (category or ""):
            seen = {}
            for key, val in options.items():
                k = norm(val).rstrip("。．.")
                if k and k in seen:
                    findings.append(("选项重复", qid, category,
                                     f"选项 {seen[k]} 和 {key} 内容一样：{k[:24]}"))
                elif k:
                    seen[k] = key
        # 「以上都」类选项不在最后
        keys = list(options.keys())
        for i, key in enumerate(keys):
            if any(word in options[key] for word in ALL_OF) and i != len(keys) - 1:
                findings.append(("以上都不在最后", qid, category,
                                 f"选项 {key}「{options[key][:18]}」后面还有 {keys[i+1:]}"))

        # --- 文字问题 ---
        for pos, bigram in check_dup_chars(full):
            findings.append(("重复字", qid, category,
                             f"重复「{bigram}」→ …{full[max(0,pos-14):pos+14]}…"))
        for pos, frag in check_latin_single(full):
            findings.append(("字母误插", qid, category,
                             f"「{frag}」…{full[max(0,pos-12):pos+12]}…"))
        for wrong, right in TERM_FIXES.items():
            if wrong != right and wrong in full:
                findings.append(("术语错写", qid, category, f"「{wrong}」应为「{right}」"))

    conn.close()

    out = pathlib.Path(__file__).with_name("audit_report.txt")
    out.write_text("\n".join(
        f"[{kind}] id={qid} [{category}] {detail}" for kind, qid, category, detail in findings
    ), encoding="utf-8")
    print(f"明细已写入 {out}\n")

    groups = {}
    for kind, qid, category, detail in findings:
        groups.setdefault(kind, []).append((qid, category, detail))

    total = 0
    for kind, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        total += len(items)
        print(f"【{kind}】{len(items)} 处")
        for qid, category, detail in items[:args.limit]:
            print(f"   id={qid} [{category}] {detail}")
        if len(items) > args.limit:
            print(f"   …还有 {len(items) - args.limit} 处")
        print()
    print(f"合计 {total} 处")


if __name__ == "__main__":
    main()
