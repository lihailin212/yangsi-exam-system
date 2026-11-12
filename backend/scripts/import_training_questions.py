# -*- coding: utf-8 -*-
"""导入 2026 年 11 月新增的两组培训题目。

来源：
  1. 妇科普查  —— 2026 年妇科超声/宫颈癌防治普查问卷（问卷星）截图，10 题
  2. 护理培训  —— 《不合格标本统计、分析与标本采集注意事项》测试题（docx），10 题

截图里题干是屏幕翻拍/OCR 过来的，有几处明显是识别错误，导入时已按
医学常识改正，并在下面的 CORRECTIONS 里记了改动，方便复核：
  - 第 6 题 E 选项「宫颈纳囊」→ 宫颈纳氏囊肿
  - 第 8 题 E 选项「星立速低阻频谱」→ 呈低速低阻频谱
  - 第 9 题 B 选项「占位内部欧洲周边」→ 占位内部及周边

原文件都没有解析，这里的解析是按题干内容写的，需要按科室口径复核。
解析原文见脚本顶部的 CORRECTIONS。

用法：
    cd backend && python scripts/import_training_questions.py --dry-run
    cd backend && python scripts/import_training_questions.py
"""
import argparse
import json
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from db import load_dotenv_local

load_dotenv_local()   # app.database 在 import 时就要读 DATABASE_URL

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

# 截图/文档里识别或抄写有误的地方，导入时按正确写法落地
CORRECTIONS = [
    ("妇科普查 第6题 E", "宫颈纳囊", "宫颈纳氏囊肿"),
    ("妇科普查 第8题 E", "星立速低阻频谱", "呈低速低阻频谱"),
    ("妇科普查 第9题 B", "占位内部欧洲周边", "占位内部及周边"),
]

WOMEN = [
    {
        "type": "single",
        "content": "WHO宫颈癌防治的新理念是什么？",
        "options": {
            "A": "治疗宫颈疾病",
            "B": "防治宫颈疾病风险",
            "C": "以防病代替治病",
            "D": "宫颈癌筛查方法发生变化",
        },
        "answer": "B",
        "analysis": "WHO提出的宫颈癌防治新理念是“防治宫颈疾病风险”，"
                    "即把防控关口前移，以人群为单位开展一级预防，"
                    "同时加强癌前病变的筛查与治疗，减少宫颈癌的发生。",
    },
    {
        "type": "single",
        "content": "高危型HPV感染意味着什么？",
        "options": {
            "A": "宫颈癌",
            "B": "宫颈癌前病变",
            "C": "宫颈炎症",
            "D": "宫颈处于高风险状态",
        },
        "answer": "D",
        "analysis": "高危型HPV感染并持续存在提示宫颈上皮内瘤变（CIN）风险升高，"
                    "此时宫颈处于高风险状态，需要按规范随访并复查。",
    },
    {
        "type": "single",
        "content": "WHO推荐的宫颈癌筛查方法首选哪种？",
        "options": {
            "A": "高危型HPV检测",
            "B": "低危型HPV检测",
            "C": "宫颈细胞学检查(TCT)",
            "D": "HPV+TCT联合筛查",
        },
        "answer": "A",
        "analysis": "WHO推荐以高危型HPV检测作为宫颈癌筛查的首选方法，"
                    "敏感度较高、可减少细胞学检查次数并提高筛查覆盖率。",
    },
    {
        "type": "single",
        "content": "持续高危型HPV感染的时长是多久？",
        "options": {
            "A": "1年",
            "B": "2年",
            "C": "3年",
            "D": "5年",
        },
        "answer": "B",
        "analysis": "高危型HPV持续感染约2年以上，发生宫颈上皮内瘤变（CIN）的"
                    "风险明显升高，因此感染后需按规范随访复查。",
    },
    {
        "type": "single",
        "content": "WHO推荐HPV疫苗接种的重点人群为？",
        "options": {
            "A": "9-45岁女性",
            "B": "16-26岁女性",
            "C": "9-14岁女性",
            "D": "16-45岁女性",
        },
        "answer": "C",
        "analysis": "WHO推荐9～14岁女孩优先接种HPV疫苗：该年龄接种免疫原性最好、"
                    "所需剂次少、获益最大；15～45岁女性接种同样可以获益。",
    },
    {
        "type": "single",
        "content": "下面哪一项与子宫内膜癌超声鉴别诊断无关？",
        "options": {
            "A": "子宫肌瘤变形",
            "B": "多发子宫肌瘤",
            "C": "脉管内平滑肌瘤病",
            "D": "子宫平滑肌肉瘤",
            "E": "宫颈纳氏囊肿",
        },
        "answer": "E",
        "analysis": "子宫肌瘤变形、多发子宫肌瘤、脉管内平滑肌瘤病、"
                    "子宫平滑肌肉瘤均需与子宫内膜癌作超声鉴别；"
                    "宫颈纳氏囊肿属于宫颈病变，与子宫内膜癌鉴别诊断无关。",
    },
    {
        "type": "single",
        "content": "子宫腺肌症描述不正确的是",
        "options": {
            "A": "子宫腺肌症为子宫内膜出现和生长在子宫肌层内表现",
            "B": "子宫内膜组织侵入局部使周围肌肉组织增生形成多个子宫肌瘤",
            "C": "子宫圆钝饱满增大",
            "D": "彩色多普勒血流无特异性",
            "E": "易发生在30～50岁产妇",
        },
        "answer": "B",
        "analysis": "子宫腺肌症是子宫内膜异位到子宫肌层并引起肌层增生，"
                    "表现为肌壁增厚、子宫圆钝饱满增大、彩色多普勒血流无特异性，"
                    "多见于30～50岁经产妇；"
                    "“形成多个子宫肌瘤”是子宫肌瘤的表现，不是子宫腺肌症。",
    },
    {
        "type": "single",
        "content": "卵巢良性肿瘤的声像图特点是",
        "options": {
            "A": "肿块不规则边界不整，实性部分回声不均匀",
            "B": "肿块多为囊性，内部回声均匀，壁薄而规则",
            "C": "多伴腹水",
            "D": "CDFI：肿块内部及周边血供丰富",
            "E": "呈低速低阻频谱，RI＜0.4",
        },
        "answer": "B",
        "analysis": "卵巢良性肿瘤多为囊性，内部回声均匀、壁薄而规则，"
                    "血流稀少，呈低速低阻频谱、RI＜0.4；"
                    "边界不规则、实性回声不均匀、血供丰富、常伴腹水多提示恶性。",
    },
    {
        "type": "single",
        "content": "以下哪些是乳腺超声检查需要注意的？",
        "options": {
            "A": "观察乳腺内的占位位置、大小、纵横比、内部回声、"
                 "是否有微小钙化灶，边缘是否清楚，形态规则与否，后方回声衰减或者增强",
            "B": "多普勒：占位内部及周边有无血流信号，血流流速和阻力指数",
            "C": "乳腺导管有无扩张",
            "D": "乳腺淋巴引流区有无肿大淋巴结",
            "E": "以上都是",
        },
        "answer": "E",
        "analysis": "乳腺超声检查应系统观察：病灶的位置、大小、纵横比、内部回声、"
                    "微小钙化、边缘与形态、后方回声；用多普勒评价血流及阻力指数；"
                    "同时观察乳腺导管有无扩张、淋巴引流区有无肿大淋巴结。以上各项都要看。",
    },
    {
        "type": "multiple",
        "content": "以下哪些是乳腺占位良恶性诊断要点？",
        "options": {
            "A": "肿块的形态，良性椭圆形，恶性不规则形态或者圆形",
            "B": "肿块的方位，良性为平行的，恶性为不平行的",
            "C": "肿块边缘，良性：边缘完整、清晰、规则，"
                 "恶性：边缘模糊、毛刺、成角、分叶状等",
            "D": "内部回声，良性多为等回声低回声，恶性低回声不均匀",
            "E": "肿块内部有无钙化，良性少见，有时有粗大钙化灶，"
                 "恶性多见，表现为微小钙化",
        },
        "answer": "A,B,C,D,E",
        "analysis": "乳腺占位良恶性鉴别要点包括：肿块形态、方位（平行/不平行）、"
                    "边缘、内部回声以及内部钙化特征，"
                    "其中边缘毛刺、成角、分叶状和微小钙化是恶性的重要征象。",
    },
]

NURSING = [
    {
        "type": "single",
        "content": "检验全过程（分析前、分析中、分析后）中，差错所占比例最高的阶段是",
        "options": {
            "A": "分析中",
            "B": "分析后",
            "C": "分析前",
            "D": "各阶段基本相同",
        },
        "answer": "C",
        "analysis": "检验差错主要集中在分析前阶段（标本采集、标识、运送等），"
                    "约占全部差错的三分之二，因此分析前质量控制是全程管理的重点。",
    },
    {
        "type": "single",
        "content": "2025年全院不合格标本中，例数最多的不合格类型是",
        "options": {
            "A": "标本溶血",
            "B": "标本容器错误",
            "C": "无标识标本",
            "D": "抗凝标本凝集",
        },
        "answer": "D",
        "analysis": "抗凝标本凝集多因采集后未及时、充分混匀所致，"
                    "在不合格标本中例数最多；采集环节的规范操作可直接减少该类不合格。",
    },
    {
        "type": "single",
        "content": "溶血标本对检验结果的影响，下列说法正确的是",
        "options": {
            "A": "使血钾大幅度降低",
            "B": "使血钾大幅度升高",
            "C": "使血氨浓度降低",
            "D": "使转氨酶降低",
        },
        "answer": "B",
        "analysis": "红细胞破裂后释放钾离子，使血钾结果假性升高，"
                    "同时可干扰其他项目的测定，属分析前因素引起的错误结果。",
    },
    {
        "type": "single",
        "content": "抗凝标本凝固的最常见原因是",
        "options": {
            "A": "采集后未立即充分混匀，超过30秒凝血即开始",
            "B": "采血量过少所致",
            "C": "采血后立即冷藏保存，可有效防止凝固",
            "D": "止血带时间过长所致",
        },
        "answer": "A",
        "analysis": "抗凝管要求采集后立即颠倒轻混5～8次；"
                    "混匀不及时或动作过重均可致抗凝不充分而发生凝固。"
                    "冷藏并不能防止凝固，止血带过长主要影响血液流速和部分项目结果。",
    },
    {
        "type": "single",
        "content": "抗凝标本采集后正确的混匀方法是",
        "options": {
            "A": "采完后颠倒轻混5~8次",
            "B": "来回剧烈摇晃混匀",
            "C": "随意晃动两三下即可",
            "D": "无需混匀，静置送检",
        },
        "answer": "A",
        "analysis": "正确的做法是采完立即颠倒轻混5～8次；"
                    "剧烈来回摇晃会造成红细胞破裂（溶血），"
                    "晃动过少则抗凝不充分，均不可取。",
    },
    {
        "type": "single",
        "content": "痰液标本正确的采集方法是",
        "options": {
            "A": "随意咳几口唾液留取",
            "B": "清晨用力咳出第一口痰送检",
            "C": "晨起清水漱口后深咳，弃去第一口留取第二口痰",
            "D": "将鼻涕混入痰标本中",
        },
        "answer": "C",
        "analysis": "痰液应于晨起清水漱口后深咳，弃去第一口（口腔内容物），"
                    "留取第二口痰送检；混入唾液或鼻涕会造成标本污染和细胞学误判。",
    },
    {
        "type": "single",
        "content": "关于紫色（EDTA-K2）采血管，下列说法正确的是",
        "options": {
            "A": "适用于血钾检测",
            "B": "适用于血钙检测",
            "C": "用于血常规、血型检测，严禁用于血钾、血钙检测",
            "D": "用于凝血功能检测",
        },
        "answer": "C",
        "analysis": "EDTA-K2通过螯合钙、镁离子抗凝，用于血常规和血型检测；"
                    "它同时螯合钾和钙，会使血钾、血钙结果假性降低，"
                    "故严禁用于血钾、血钙检测；凝血功能检测用枸橼酸钠（蓝管）。",
    },
    {
        "type": "single",
        "content": "真空采血管正确的采集顺序是",
        "options": {
            "A": "红黄→黑→蓝→绿→紫→灰",
            "B": "血培养（需氧→厌氧）→黑→蓝→红黄→绿→紫→灰",
            "C": "血培养（需氧→厌氧）→紫→绿→红黄→蓝→黑",
            "D": "黑→蓝→紫→绿→灰→红黄",
        },
        "answer": "B",
        "analysis": "正确顺序为血培养瓶（需氧→厌氧）→黑→蓝→红黄→绿→紫→灰。"
                    "顺序错误会因前一管的添加剂污染后一管而影响结果。",
    },
    {
        "type": "single",
        "content": "关于尿液标本采集，下列说法正确的是",
        "options": {
            "A": "可从便盆、尿布中采集",
            "B": "24小时尿从清晨第一次排尿起全部留取，不必弃去",
            "C": "尿培养应清洗外阴后弃去前段尿，留取中段尿",
            "D": "采集后6小时内送检即可",
        },
        "answer": "C",
        "analysis": "尿培养要求清洁外阴后弃去前段尿、留取中段尿，"
                    "避免尿道口细菌污染；便盆、尿布采集易被污染；"
                    "尿液标本一般要求2小时内送检，标本久置易滋生细菌、细胞分解。",
    },
    {
        "type": "single",
        "content": "关于血培养标本采集，下列说法正确的是",
        "options": {
            "A": "任何发热时均可随时采集",
            "B": "成人每瓶采血2~5mL",
            "C": "每套应先采厌氧瓶、后采需氧瓶",
            "D": "宜在抗菌药物使用前、寒战高热时采集，成人每瓶8~10mL",
        },
        "answer": "D",
        "analysis": "血培养宜在寒战高热高峰或使用抗菌药物之前采集，"
                    "成人每瓶8～10mL可提高阳性率；"
                    "先采需氧瓶再采厌氧瓶，培养基按需氧→厌氧顺序不可颠倒。",
    },
]

GROUPS = [
    ("妇科普查", WOMEN),
    ("护理培训", NURSING),
]


def norm(text: str) -> str:
    """去掉 HTML 标签和空白，用来判重。"""
    import re
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", "", text)


def main():
    ap = argparse.ArgumentParser(description="导入 2026.11 培训题目")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        total_new = 0
        for category, items in GROUPS:
            print(f"\n=== {category}（{len(items)} 题）===")
            for item in items:
                content = f"<p>{item['content']}</p>"
                key = norm(content)
                exists = (db.query(models.Question)
                          .filter(models.Question.content == content).first())
                if exists:
                    print(f"  跳过（已存在 id={exists.id}）：{item['content'][:28]}")
                    continue
                q = models.Question(
                    type=item["type"],
                    content=content,
                    options=json.dumps(item["options"], ensure_ascii=False),
                    answer=item["answer"],
                    analysis=item.get("analysis", ""),
                    category=category,
                )
                db.add(q)
                db.flush()
                total_new += 1
                print(f"  新增 id={q.id} [{item['type']}] 答案={item['answer']} "
                      f"{item['content'][:28]}")

        if args.dry_run:
            db.rollback()
            print(f"\n（--dry-run，未写库；共 {total_new} 题待导入）")
        else:
            db.commit()
            print(f"\n已写入，共新增 {total_new} 题")
    finally:
        db.close()


if __name__ == "__main__":
    main()
