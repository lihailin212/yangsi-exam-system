# -*- coding: utf-8 -*-
"""修复题库里因为历年真题 OCR 丢字、丢下标而损坏的题目。

一、13 道「答案字母不存在」的题
   导入历年真题时，PDF 里的选项前缀有写成「E、」的，解析器只认「E.」，
   于是那个选项被整条丢掉——结果答案字母指向一个不存在的选项，
   考生怎么选都是错。下面按 OCR 原文（backend/.cache/ocr/ 里的页缓存）
   把丢掉的选项补回去。

二、一批错别字/术语错误
   OCR 和人工录入留下的重复字、错字（葡葡糖、胆胆红素、血清清蛋白……）。

脚本按「先打印改前改后，确认无误再写库」的方式跑，可以重复执行。
用法：
    cd backend && python scripts/repair_question_bank.py --dry-run
    cd backend && python scripts/repair_question_bank.py
"""
import argparse
import json
import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from db import load_dotenv_local

load_dotenv_local()

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

# ---- 一、丢失的选项 ----
# id -> {"content": 新的题干(可选), "options": 新的选项, "note": 来源}
MISSING_OPTIONS = {
    21781: {
        "content": "<p>肾小管蛋白尿是指</p>",
        "options": {
            "A": "原尿中蛋白质不能被肾小管重吸收",
            "B": "肾小球滤过膜的损伤",
            "C": "肾脏被动性充血L",
            "D": "肾血管痉挛出血",
            "E": "肾小球通透性增加",
        },
        "note": "A 选项被粘在题干里（“…是指A，原尿中蛋白质…”）",
    },
    21818: {
        "options": {
            "A": "检验先天性膜缺陷溶血性贫血",
            "B": "阳性表示红细胞渗透脆性增大，见于遗传性球形红细胞增",
            "C": "脆性大是指对低渗盐水适应性小",
            "D": "正常对照NaCI浓度相差0.4g/L即可判阳性",
            "E": "以上都是",
        },
        "note": "原 PDF 里 E 写成「E、以上都是」，解析器没认出来",
    },
    21897: {
        "content": "<p>心肌特异性肌钙蛋白通常是指（）</p>",
        "options": {
            "A": "cTnT和cTnI",
            "B": "CK",
            "C": "Mb",
            "D": "AST",
            "E": "TnC",
        },
        "note": "A 选项被粘在题干里",
    },
    21952: {
        "options": {
            "A": "个体微小",
            "B": "结构简单",
            "C": "繁殖迅速",
            "D": "分布广泛",
            "E": "专性寄生",
        },
        "note": "E 选项在 OCR 时丢失",
    },
    22041: {
        "content": "<p>漏出液以什么细胞为主</p>",
        "options": {
            "A": "淋巴细胞",
            "B": "单核细胞",
            "C": "嗜中性粒细胞",
            "D": "嗜酸性粒细胞",
            "E": "嗜碱性粒细胞",
        },
        "note": "A 选项被粘在题干里",
    },
    22105: {
        "options": {
            "A": "尿17-羟皮质类固醇",
            "B": "尿17-酮皮质类固醇",
            "C": "血清总皮质醇",
            "D": "血清游离皮质醇",
            "E": "血清总蛋白",
        },
        "note": "E 选项写成「E，血清总蛋白」，逗号没被识别",
    },
    22511: {
        "options": {
            "A": "50%溶血试验比100%溶血试验简单",
            "B": "以50%溶血作为终点较100%溶血作为终点更敏感",
            "C": "以50%溶血作为终点较100%溶血作为终点可节约时间",
            "D": "以上都不对",
            "E": "A+C.",
        },
        "note": "A、B 两个选项粘成了一条，B 选项整个丢失",
    },
    22586: {
        "options": {
            "A": "20",
            "B": "100",
            "C": "200",
            "D": "400",
            "E": "10",
        },
        "note": "B、C 两个选项粘成「100200」，C 选项整个丢失",
    },
    22745: {
        "options": {
            "A": "α2β2",
            "B": "α2γ2",
            "C": "a282",
            "D": "β22",
            "E": "822",
        },
        "note": "B 选项整个丢失（HbF = α2γ2）",
    },
    22854: {
        "options": {
            "A": "抗ssDNA抗体和ANA",
            "B": "抗dsDNA抗体和ANA",
            "C": "抗Sm抗体和抗dsDNA抗体",
            "D": "抗DNP抗体和ANA",
            "E": "抗SS-A抗体和抗核蛋白抗体",
        },
        "note": "B、C 两个选项粘成了一条，C 选项整个丢失",
    },
    23111: {
        "options": {
            "A": "-",
            "B": "+",
            "C": "++",
            "D": "+++",
            "E": "++++",
        },
        "note": "E 选项整个丢失",
    },
    26190: {
        "options": {
            "A": "胶体金既可用于透射电镜又可用于扫描电镜",
            "B": "其最大优点是可进行单重标记",
            "C": "不同的胶体金水溶胶因粒子大小不同，颜色相同",
            "D": "胶体金只可用于透射电镜",
            "E": "胶体金只可用于扫描电镜",
        },
        "note": "A 选项整个丢失",
    },
    26492: {
        "options": {
            "A": "223",
            "B": "12s",
            "C": "13s",
            "D": "41s",
            "E": "10s",
        },
        "note": "A、B 两个选项粘成「223B: 12s」，B 选项整个丢失",
    },
}

# ---- 二、错别字 / 术语 ----
# (题号, 字段, 原文, 改后)
TEXT_FIXES = [
    (21682, "analysis", "葡葡糖检测的抗凝剂", "葡萄糖检测的抗凝剂"),
    (21769, "analysis", "蔗糖溶溶血试验", "蔗糖溶血试验"),
    (22017, "analysis", "所以以50%溶血作为终点", "所以，以50%溶血作为终点"),
    (22190, "analysis", "红色为抗酸阳性性", "红色为抗酸阳性"),
    (22601, "analysis", "IMVIC试验十十一一是其主要的生化特征", "IMVIC试验++---是其主要的生化特征"),
    (22953, "analysis", "IgM类类风湿因子", "IgM类风湿因子"),
    (23003, "analysis", "即反应达顶峰峰值", "即反应达峰值"),
    (23125, "analysis", "蛋白尿或或尿胆原", "蛋白尿或尿胆原"),
    (23300, "analysis", "再加入入10%二甲基亚矾", "再加入10%二甲基亚砜"),
    (25255, "content", "为了防止伺楼病", "为了防止佝偻病"),
    (25405, "analysis", "β-内洗胺酶", "β-内酰胺酶"),
    (25405, "analysis", "④-内洗胺酶", "④-内酰胺酶"),
    (25405, "analysis", "萄萄球菌", "葡萄球菌"),
    (25405, "analysis", "对青零素", "对青霉素"),
    (25405, "analysis", "对青素和", "对青霉素和"),
    (25405, "analysis", "乙洗基青零素", "乙氧基青霉素"),
    (25405, "analysis", "脲基青雪素", "脲基青霉素"),
    (25432, "analysis", "内酮酸经三羧酸", "丙酮酸经三羧酸"),
    (25615, "analysis", "反映胎儿肺的成熟度度", "反映胎儿肺的成熟度"),
    (25615, "analysis", "肌酐测定反映反映胎儿肾", "肌酐测定反映胎儿肾"),
    (25746, "analysis", "几乎都可以用用该方法", "几乎都可以用该方法"),
    (26144, "analysis", "原始粒细胞占占30%-89%", "原始粒细胞占30%-89%"),
    (26295, "analysis", "试带法Ehrich检测尿胆原原理", "试带法Ehrlich检测尿胆原原理"),
    (26295, "content", "基于Ehrich法检测原理", "基于Ehrlich法检测原理"),
    (26590, "analysis", "是指幼红红细胞胞质内蓝色颗粒", "是指幼红细胞胞质内蓝色颗粒"),
    (26633, "analysis", "的症状可可推断为弓形虫感染", "的症状可以推断为弓形虫感染"),
    (27243, "content", "RIA被替代是由于于（）", "RIA被替代是由于（）"),
    (27900, "content", "口服葡糖糖后多长时间", "口服葡萄糖后多长时间"),
    (28902, "analysis", "胆胆红素却进行性升高", "胆红素却进行性升高"),
    (28905, "analysis", "减去血清清蛋白测定值计算", "减去血清蛋白测定值计算"),
    (28922, "analysis", "革兰阴性杆菌菌落计数", "革兰阴性杆菌落计数"),
    (29378, "analysis", "粒细胞胞内容物的异常", "粒细胞内容物的异常"),
    (22854, "content", "可作为SLE特异筒标志的自身抗体是", "可作为SLE特异性标志的自身抗体是"),
]


def main():
    ap = argparse.ArgumentParser(description="修复题库里的坏题和错别字")
    ap.add_argument("--dry-run", action="store_true", help="只打印改动，不写库")
    args = ap.parse_args()

    db = SessionLocal()
    changed = 0
    try:
        print("=== 一、补回丢失的选项 ===")
        for qid, fix in MISSING_OPTIONS.items():
            q = db.query(models.Question).filter(models.Question.id == qid).first()
            if not q:
                print(f"  id={qid} 题不存在，跳过")
                continue
            old_options = q.options
            old_content = q.content
            if fix.get("content"):
                q.content = fix["content"]
            q.options = json.dumps(fix["options"], ensure_ascii=False)
            # 答案必须落在选项里
            answers = [a.strip() for a in (q.answer or "").split(",") if a.strip()]
            missing = [a for a in answers if a not in fix["options"]]
            if missing:
                raise SystemExit(f"id={qid} 答案 {missing} 仍不在选项里，先别写库")
            print(f"  id={qid} {fix['note']}")
            print(f"    改前选项: {old_options}")
            print(f"    改后选项: {q.options}")
            if fix.get("content"):
                print(f"    题干: {old_content} -> {q.content}")
            changed += 1

        print("\n=== 二、改错别字 / 术语 ===")
        for qid, field, old, new in TEXT_FIXES:
            q = db.query(models.Question).filter(models.Question.id == qid).first()
            if not q:
                print(f"  id={qid} 题不存在，跳过")
                continue
            text = getattr(q, field) or ""
            if old not in text:
                print(f"  id={qid} {field} 里没有 {old!r}，跳过")
                continue
            setattr(q, field, text.replace(old, new))
            print(f"  id={qid} {field}: {old} → {new}")
            changed += 1

        if args.dry_run:
            db.rollback()
            print(f"\n（--dry-run，未写库；共 {changed} 处改动）")
        else:
            db.commit()
            print(f"\n已写入，共 {changed} 处改动")
    finally:
        db.close()


if __name__ == "__main__":
    main()
