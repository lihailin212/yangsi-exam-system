# -*- coding: utf-8 -*-
"""人工核对 PDF 高清渲染图后，逐题回填缺失的符号。

配合 scripts/fix_duplicate_options.py 用：
  那个脚本按规则（Ⅰ-Ⅴ 枚举、同题副本）批量修；
  这个脚本是我把 PDF 区域用 400dpi 渲染成图、逐题看过之后手工定的，
  箭头（↓↑）和源卷本身的印刷错误只有看得见才改得对。

用法：
    cd backend && python scripts/fix_duplicate_options_manual.py --dry-run
    cd backend && python scripts/fix_duplicate_options_manual.py
"""
import argparse
import json
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))
from db import connect  # noqa: E402

# id -> {选项字母: 正确文字}
MANUAL = {
    # 源卷把 D、E 印重了（E 应为嗜碱性粒细胞）
    21793: {"E": "嗜碱性粒细胞"},
    # 箭头被 OCR 吞了（PDF 上看得见 ↓），D 选项整条丢了
    22060: {"A": "RBC↓、Hb↓", "B": "RBC↓、↓Hb↓", "C": "RBC↓、Hb↓↓",
            "D": "RBC↓↓、Hb↓↓", "E": "RBC↓、Hb正常"},
    # 「VLDL LDL」中间漏了个顿号
    22324: {"C": "CM、VLDL、LDL、HDL"},
    # ×10¹⁰/L 的上标
    22381: {"D": "(100～300)×10¹⁰/L"},
    # FAB 分型下标
    22386: {"A": "AML~M1", "B": "AML~M2", "D": "AML~M4", "E": "AML~M5"},
    # HLA-DR4 / HLA-DR
    22422: {"D": "HLA～DR4", "E": "HLA～DR"},
    # 血小板因子 PF3 / PF4，血栓烷 TXA2
    22424: {"C": "PF3", "D": "PF4", "E": "TXA2"},
    # 酸碱失衡类型：缺「代偿型呼吸性碱中毒」
    22547: {"C": "代偿型呼吸性碱中毒"},
    # 渗透脆性：OCV < RCV
    22590: {"B": "OCV<RCV"},
    # 五型变态反应
    23052: {"A": "Ⅰ型变态反应", "B": "Ⅱ型变态反应", "C": "Ⅲ型变态反应",
            "D": "Ⅳ型变态反应", "E": "Ⅴ型变态反应"},
    # 阴道清洁度 Ⅰ-Ⅴ 度
    23063: {"A": "Ⅰ度", "B": "Ⅱ度", "C": "Ⅲ度", "D": "Ⅳ度", "E": "Ⅴ度"},
    # 「有核细胞」被截成了「有核红细胞」
    23081: {"E": "有核细胞"},
    # 五型超敏反应
    23131: {"A": "Ⅰ型变态反应", "B": "Ⅱ型变态反应", "C": "Ⅲ型变态反应",
            "D": "Ⅳ型变态反应", "E": "迟发型变态反应"},
    # 精子活动力 a~e 级（不是罗马数字）
    23680: {"C": "c级", "D": "d级"},
    # 寄生虫名
    23962: {"C": "钩虫", "D": "蛔虫"},
    # 孕激素
    24016: {"C": "孕激素"},
    # 镜检见大量吞噬细胞
    24121: {"C": "镜检见大量吞噬细胞"},
    # 核型 44,XX
    24383: {"D": "44,XX"},
    # HCG 的 α/β/γ/δ/ε 多肽链
    24391: {"D": "δ多肽链", "E": "ε多肽链"},
    # 蛔虫
    24420: {"E": "蛔虫"},
    # ---- 第二轮：把剩下的题按 PDF 逐条核对后补齐 ----
    26738: {"C": "Ⅲ型变态反应"},
    23962: {"C": "蛔虫", "D": "蛲虫"},
    25963: {"B": "钩虫", "D": "蛲虫"},
    23498: {"D": "因子Ⅷ"},
    22248: {"A": "FⅦ", "D": "FⅧ"},
    23986: {"A": "Ⅰ", "B": "Ⅱ"},
    25191: {"A": "Ⅰ", "B": "Ⅱ"},
    24074: {"B": "Ⅱa型", "C": "Ⅱb型", "D": "ⅡN型", "E": "Ⅲ型"},
    24075: {"B": "Ⅱa型", "C": "Ⅱb型", "D": "ⅡN型", "E": "Ⅲ型"},
    24628: {"A": "Ⅰ型和Ⅱ型", "C": "Ⅰ型和Ⅲ型"},
    25833: {"B": "Ⅰ型和Ⅳ型", "E": "Ⅲ型和Ⅳ型"},
    26594: {"B": "Ⅰ型和Ⅳ型", "D": "Ⅱ型和Ⅳ型"},
    24918: {"E": "从因子XI被激活到纤维蛋白形成"},
    25063: {"D": "Ⅳ型", "E": "Ⅴ型"},
    25814: {"E": "肺泡Ⅱ型细胞"},
    26512: {"A": "M₃", "B": "M₄", "C": "M₅", "D": "M₁", "E": "M₂"},
    26684: {"D": "c"},
    26800: {"A": "绦虫病", "B": "蛲虫病", "E": "蛔虫病"},
    26737: {"C": "Ⅲ型"},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()
    n = 0
    for qid, changes in MANUAL.items():
        cur.execute("select options, answer from questions where id=%s", (qid,))
        row = cur.fetchone()
        if not row:
            print(f"  id={qid} 不存在，跳过")
            continue
        options = json.loads(row[0] or "{}")
        before = dict(options)
        for k, v in changes.items():
            if k in options:
                options[k] = v
        if options == before:
            continue
        cur.execute("update questions set options=%s where id=%s",
                    (json.dumps(options, ensure_ascii=False), qid))
        n += 1
        print(f"  id={qid} answer={row[1]}")
        for k, v in changes.items():
            if before.get(k) != v:
                print(f"     {k}: {before.get(k)!r} → {v!r}")
    if args.dry_run:
        conn.rollback()
        print(f"（--dry-run，未写库；共 {n} 题）")
    else:
        conn.commit()
        print(f"已写入 {n} 题")
    conn.close()


if __name__ == "__main__":
    main()
