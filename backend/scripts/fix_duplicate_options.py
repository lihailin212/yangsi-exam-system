# -*- coding: utf-8 -*-
"""修复「选项里有重复」的题。

背景：这批题是 2010~2023 年真题扫描件 OCR 进来的。扫描件本身就没印清
下标数字和 ↑↓ 箭头，OCR 自然也认不出来，于是同一道题的选项变成
"G期""LD""M""I型超敏反应"这种一串一样的字，考生没法选（答案字母
指向的选项还在，但和别的选项长得一模一样，等于白送分）。

能救的来源：
  1. 固定枚举（Ⅰ~Ⅴ 型超敏反应、Ⅰ~Ⅴ 度、M1~M5、LD1~LD5、10⁹/L…），
     按选项顺序补——这类题每道都是同一套排列，锚点很好找；
  2. 同一道题在别的年份卷子里的副本（那份扫描清楚些，选项是完整的），
     只用来替换「正在重复」的那几个选项。

用法：
    cd backend && python scripts/fix_duplicate_options.py --dry-run
    cd backend && python scripts/fix_duplicate_options.py
"""
import argparse
import json
import os
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))
from db import connect  # noqa: E402

ALL_ROWS = []
LOADED = False


def norm(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"[\s，,。．.、：:；;？?！!（）()「」“”\"'【】\[\]～~]+", "", s)


def load_all(conn):
    global ALL_ROWS, LOADED
    if LOADED:
        return
    cur = conn.cursor()
    cur.execute("select id, content, options from questions")
    rows = []
    for qid, c, o in cur.fetchall():
        try:
            opts = json.loads(o or "{}")
        except (TypeError, ValueError):
            opts = {}
        rows.append((qid, norm(c), opts))
    ALL_ROWS = rows
    LOADED = True


def siblings(qid, content):
    """同一道题在题库里的其它副本。

    只认题干（去掉空白标点后）完全一样的。用前缀找会把
    「共���题干」的题串到一起，选项会张冠李戴。
    """
    key = norm(content)
    return [r for r in ALL_ROWS if r[0] != qid and r[1] == key]


# ---- 枚举规则 ----
# 每条：(选项文字的正则, 依次填进去的尾巴, 名字)
ENUM_RULES = [
    # Ⅰ~Ⅴ 型超敏反应 / 变态反应
    (r"^([IVXivxⅠⅡⅢⅣⅤ]*)型(超敏|变态)反应$", ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"], "五型超敏"),
    # Ⅰ~Ⅴ 度（阴道清洁度）
    (r"^([IVXivxⅠⅡⅢⅣⅤ]*)度$", ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"], "清洁度"),
    # Ⅰ~Ⅴ 级
    (r"^([IVXivxⅠⅡⅢⅣⅤ]*)级$", ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"], "分级"),
    # AML-M1~M5
    (r"^AML~?M([0-9I]*)$", ["1", "2", "3", "4", "5"], "AML-M"),
    # M1~M5（FAB 分型）
    (r"^M([0-9]*)$", ["1", "2", "3", "4", "5"], "FAB"),
    # LD1~LD5
    (r"^LD([0-9]*)$", ["1", "2", "3", "4", "5"], "LD同工酶"),
    # 血小板因子 PF3 / PF4
    (r"^PF$", ["3", "4", "", "", ""], "血小板因子"),
    # Ⅰ~Ⅴ 型高脂蛋白血症
    (r"^([IVXivxⅠⅡⅢⅣⅤ]*)型高脂蛋白血症$", ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"], "高脂蛋白"),
    # Ⅰ~Ⅴ 型超敏反应（另一种写法）
    (r"^([IVXivxⅠⅡⅢⅣⅤ]*)超敏反应$", ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"], "超敏"),
]


def enum_fill(options, dup_keys):
    """按枚举规则补全：只在「正在重复」的选项里改。"""
    out = {}
    keys = list(options.keys())
    for pattern, tails, name in ENUM_RULES:
        hit = {}
        for k in keys:
            m = re.fullmatch(pattern, (options.get(k) or "").strip())
            if m:
                hit[k] = m.group(1) if m.lastindex else ""
        if len(hit) < 2:
            continue
        # 找锚点：已经认出来的那个（带数字/罗马数字）
        anchor = None
        for k in keys:
            if k in hit and hit[k]:
                anchor = k
                break
        if anchor is None:
            continue
        # 锚点对应的序号
        a_txt = hit[anchor]
        # 锚点的序号 = 它在 tails 里的位置（M2 -> 1，M 是第 2 个）
        ascii_roman = {"I": "Ⅰ", "II": "Ⅱ", "III": "Ⅲ", "IV": "Ⅳ", "V": "Ⅴ",
                       "II": "Ⅱ", "VI": "Ⅵ", "IX": "Ⅸ", "X": "Ⅹ"}
        a_key = a_txt.strip().upper()
        a_key = ascii_roman.get(a_key, a_key)
        a_num = None
        for i, t in enumerate(tails):
            if t.upper() == a_key or t == a_key:
                a_num = i
                break
        if a_num is None:
            continue
        # 整题按序对齐（不只改正在重复的那两个）：
        # 否则 A、B 改开了，又跟 C 撞上，白改。
        for k in keys:
            if k == anchor or k not in hit:
                continue
            pos = keys.index(k)
            rel = pos - keys.index(anchor)
            ti = a_num + rel
            if 0 <= ti < len(tails) and tails[ti]:
                m = re.fullmatch(pattern, (options.get(k) or "").strip())
                if m.lastindex and m.group(1):
                    out[k] = m.group(0).replace(m.group(1), tails[ti], 1)
                else:
                    # 数字整个丢了（「M」→「M1」），补在词尾
                    base = m.group(0) if m else ""
                    out[k] = base + tails[ti]
        if out:
            return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="只处理这些题号")
    args = ap.parse_args()

    report = BACKEND / "scripts" / "audit_report.txt"
    ids = []
    for line in report.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\[选项重复\] id=(\d+)", line)
        if m and int(m.group(1)) not in ids:
            ids.append(int(m.group(1)))
    if args.only:
        want = {int(x) for x in args.only.split(",")}
        ids = [i for i in ids if i in want]

    conn = connect()
    load_all(conn)
    cur = conn.cursor()
    fixes = {}
    for qid in ids:
        cur.execute("select content, options, answer, category from questions where id=%s", (qid,))
        row = cur.fetchone()
        if not row:
            continue
        content, options_raw, answer, category = row
        options = json.loads(options_raw or "{}")

        # 1) 哪些选项在重复
        groups = {}
        for k, v in options.items():
            groups.setdefault(norm(v), []).append(k)
        dup_keys = [k for ks in groups.values() if len(ks) > 1 for k in ks]
        if not dup_keys:
            continue

        changes = {}
        # 2) 枚举规则
        for k, nv in enum_fill(options, dup_keys).items():
            changes[k] = (options.get(k, ""), nv)

        # 3) 同题副本兜底（只替换正在重复的选项）
        sibs = siblings(qid, content)
        best = None
        for sid, skey, sopts in sibs:
            if len(sopts) < len(options):
                continue
            size = sum(len(v) for v in sopts.values())
            if best is None or size > best[0]:
                best = (size, sopts)
        if best:
            for k in dup_keys:
                if k in changes:
                    continue
                sv = best[1].get(k)
                if not sv:
                    continue
                cur_t = options.get(k, "")
                if norm(sv) == norm(cur_t):
                    continue
                # 副本文字要和当前文字像同一个词：要么前 4 个字一样，
                # 要么当前文字短（本来就是「虫」「M」这种残片），副本也短。
                # 否则说明副本是「共用备选答案」的题串错了，不能用。
                nc, ns = norm(cur_t), norm(sv)
                common = 0
                for a, b in zip(nc, ns):
                    if a != b:
                        break
                    common += 1
                if not (common >= 4 or (len(nc) <= 3 and len(ns) <= 12)):
                    continue
                extra = "".join(ch for ch in ns if ch not in nc)
                if any("一" <= ch <= "鿿" for ch in extra):
                    # 副本补的是汉字：只在副本就是「当前残片 + 最多 2 个字」时认
                    if not (len(nc) <= 3 and ns.startswith(nc) and len(ns) - len(nc) <= 2):
                        continue
                changes[k] = (cur_t, sv)

        # 4) 校验：改完之后，原来重复的那几组必须真的分开了
        new = dict(options)
        for k, (old, nv) in changes.items():
            new[k] = nv
        still = False
        for ks in groups.values():
            if len(ks) < 2:
                continue
            vals = [norm(new.get(k, "")) for k in ks]
            if len(set(vals)) != len(vals):
                still = True
                break
        # 枚举题改完可能带出新的重复组，再查一遍整题
        if still:
            vals_all = [norm(v) for v in new.values()]
            still = len(set(vals_all)) != len(vals_all)
        if still:
            continue
        answers = [a.strip() for a in (answer or "").split(",") if a.strip()]
        if any(a not in new for a in answers):
            continue
        if changes:
            fixes[qid] = {"category": category, "answer": answer, "changes": changes}

    conn.close()
    json.dump(fixes, open(BACKEND / "scripts" / "_dup_option_fixes.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"共 {len(fixes)} 题可修复（共 {len(ids)} 道候选）")
    for qid, v in fixes.items():
        print(f"  id={qid} answer={v['answer']}")
        for k, (old, new) in v["changes"].items():
            print(f"     {k}: {old!r} → {new!r}")

    if args.dry_run:
        print("（--dry-run，未写库）")
        return

    conn = connect()
    cur = conn.cursor()
    for qid, v in fixes.items():
        cur.execute("select options from questions where id=%s", (qid,))
        options = json.loads(cur.fetchone()[0] or "{}")
        for k, (old, new) in v["changes"].items():
            options[k] = new
        cur.execute("update questions set options=%s where id=%s",
                    (json.dumps(options, ensure_ascii=False), qid))
    conn.commit()
    conn.close()
    print(f"已写入 {len(fixes)} 题")


if __name__ == "__main__":
    main()
