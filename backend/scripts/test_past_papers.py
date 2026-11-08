# -*- coding: utf-8 -*-
"""历年真题解析器的单元测试。

跑法（在仓库根目录）：
    python backend/scripts/test_past_papers.py

用构造的 OCR 文本喂给解析器，断言结果。全部离线，不碰数据库。
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

import past_papers_lib as L  # noqa: E402

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print(f"  [OK] {name}")
    else:
        FAILED.append(f"{name} {detail}")
        print(f"  [FAIL] {name} {detail}")


def box(x, y, t, c=0.95, w=200):
    return {"x": x, "y": y, "x2": x + w, "y2": y + 28, "t": t, "c": c}


def test_merge_same_row():
    print("== 同行框合并 ==")
    # OCR 把「91.」和「淀粉酶是（）」拆成两个框，y 相同
    boxes = [box(87, 785, "91.", w=30), box(132, 787, "淀粉酶是（）", w=120),
             box(84, 822, "92.胆碱酯酶是（）", w=180)]
    rows = L.merge_same_row(boxes)
    check("同行两框合并成一行", len(rows) == 2, [r["t"] for r in rows])
    check("合并后内容拼接", rows[0]["t"] == "91.淀粉酶是（）", rows[0]["t"])
    check("不同行不合并", rows[1]["t"].startswith("92."), rows[1]["t"])


def test_split_columns():
    print("== 动态分栏 ==")
    # 左栏 x=121，右栏 x=796（模拟 2010 卷第 8 页）
    lines = [box(121, 200 + i * 40, f"左{i}") for i in range(8)]
    lines += [box(796, 200 + i * 40, f"右{i}") for i in range(8)]
    left, centered, right = L.split_columns(lines)
    check("左栏 8 行", len(left) == 8, len(left))
    check("右栏 8 行", len(right) == 8, len(right))
    check("无居中块", len(centered) == 0, len(centered))

    # 换一批偏移（答案页：左栏 x=273，右栏 x=845）
    lines2 = [box(273, 200 + i * 40, f"左{i}") for i in range(6)]
    lines2 += [box(845, 200 + i * 40, f"右{i}") for i in range(6)]
    left2, _c2, right2 = L.split_columns(lines2)
    check("偏移变化后仍能分栏", len(left2) == 6 and len(right2) == 6,
          (len(left2), len(right2)))


def test_noise_filter():
    print("== 广告水印过滤 ==")
    check("微信广告被过滤", L.is_noise("需要检验历年真题联系微信13888325624"))
    check("页码被过滤", L.is_noise("第 8 页"))
    check("正常题干不被过滤", not L.is_noise("7.患者男，20岁，自幼不明显原因自发出血史"))


def test_parse_questions_basic():
    print("== A 型单选解析 ==")
    lines = [
        box(120, 100, "一、以下每一道考题下面有A、B、C、D、E五个备选答案。"),
        box(120, 140, "请从中选择一个最佳答案。并在答题卡上将相应题号的相应"),
        box(120, 180, "字母所属的方框涂黑。"),
        box(120, 220, "1.我国输血后肝炎主要是（ ）"),
        box(120, 260, "A.甲肝炎"),
        box(120, 300, "B.乙肝炎"),
        box(120, 340, "C.丙肝炎"),
        box(120, 380, "D.丁肝炎"),
        box(120, 420, "E.戊肝炎"),
        box(120, 460, "2.前列腺液检查发现卵磷脂小体数量很少，常提示（ ）"),
        box(120, 500, "A.精囊炎"),
        box(120, 540, "B.前列腺癌"),
        box(120, 580, "C.前列腺结石"),
        box(120, 620, "D.前列腺肥"),
        box(120, 660, "E.前列腺炎"),
    ]
    qs = L.parse_questions(lines, paper_name="基础知识", year=2010)
    check("解析出 2 道题", len(qs) == 2, len(qs))
    check("题号正确", [q["num"] for q in qs] == [1, 2], [q["num"] for q in qs])
    check("题干正确", qs[0]["stem"].startswith("我国输血后肝炎"), qs[0]["stem"])
    check("选项齐全", len(qs[0]["options"]) == 5, qs[0]["options"])
    check("选项内容对", qs[0]["options"]["C"] == "丙肝炎", qs[0]["options"])
    check("说明段没混进题干", "以下每一道" not in qs[0]["stem"], qs[0]["stem"])
    check("第二题题干对", "前列腺液检查" in qs[1]["stem"], qs[1]["stem"])


def test_shared_options():
    print("== 配伍题共享备选答案 ==")
    lines = [
        box(120, 100, "95.抗碱血红蛋白的简写是（ ）"),
        box(120, 140, "A.抗碱血红蛋白"),
        box(120, 160, "B.高铁血红蛋白"),
        box(120, 180, "C.碳氧血红蛋白"),
        box(120, 200, "D.血红蛋白"),
        box(120, 220, "E.肌红蛋白"),
        box(120, 240, "（96～98题共用备选答案）"),
        box(120, 280, "A.肾小球"),
        box(120, 320, "B.近曲小管"),
        box(120, 360, "C.髓袢"),
        box(120, 400, "D.远曲小管"),
        box(120, 440, "E.集合管"),
        box(120, 480, "96.对葡萄糖重吸收的部位是（ ）"),
        box(120, 520, "97.对蛋白选择性滤过的部位是（ ）"),
        box(120, 560, "98.对钠重吸收的主要部位是（ ）"),
        # 第二个标记的题号被 OCR 读错（应是 99～100，读成了 96～98）
        box(120, 600, "（96～98题共用备选答案）"),
        box(120, 640, "A.二分裂繁殖"),
        box(120, 680, "B.多分裂繁殖"),
        box(120, 720, "C.出芽繁殖"),
        box(120, 760, "D.结合繁殖"),
        box(120, 800, "E.配子繁殖"),
        box(120, 840, "99.阴道毛滴虫滋养体的增殖方式是（ ）"),
        box(120, 880, "100.间日疟原虫裂殖体的增殖方式是（ ）"),
    ]
    qs = L.parse_questions(lines, paper_name="基础知识", year=2010)
    bynum = {q["num"]: q for q in qs}
    check("6 道题都在（95 + 96/97/98 + 99/100）", len(qs) == 6, sorted(bynum))
    check("95 题用自己的选项",
          bynum[95]["options"].get("A") == "抗碱血红蛋白", bynum[95]["options"])
    check("96 题用共享选项", bynum[96]["options"].get("A") == "肾小球",
          bynum[96]["options"])
    check("97 题用共享选项", bynum[97]["options"].get("E") == "集合管",
          bynum[97]["options"])
    # 第二个标记题号读错，但共享范围仍要正确切到新块
    check("99 题切到新的共享块",
          bynum[99]["options"].get("A") == "二分裂繁殖", bynum[99]["options"])
    check("100 题切到新的共享块",
          bynum[100]["options"].get("E") == "配子繁殖", bynum[100]["options"])
    check("共享题题干带提示", "共用备选答案" in bynum[96]["stem"], bynum[96]["stem"])


def test_shared_across_pages():
    print("== 共享选项跨页延续 ==")
    page1 = [
        box(120, 1800, "（95～97题共用备选答案）"),
    ]
    page2 = [
        box(180, 200, "A.菌体一端或两端膨大，有异染颗粒"),
        box(180, 240, "B.25℃有动力，37℃无动力"),
        box(180, 280, "C.粗糙菌落涂片，菌体形态似放线菌"),
        box(180, 320, "D.革兰染色阴性或阳性，着色不均"),
        box(180, 360, "E.革兰阳性大杆菌，竹节状排列"),
        box(180, 400, "95.加特纳菌属的特点是"),
        box(180, 440, "96.白喉杆菌的特点是"),
        box(180, 480, "97.炭疽芽孢杆菌的特点是"),
    ]
    qs = L.parse_questions(page1 + page2, paper_name="专业知识", year=2013)
    bynum = {q["num"]: q for q in qs}
    check("跨页后仍解析出 3 道题", len(qs) == 3, sorted(bynum))
    check("跨页共享选项正确",
          bynum[96]["options"].get("B") == "25℃有动力，37℃无动力",
          bynum[96]["options"])


def test_parse_answers():
    print("== 答案与解析提取 ==")
    lines = [
        box(120, 100, "59.参考答案：D解析：肾盂肾炎-白细胞管，急性"),
        box(120, 140, "肾小球肾炎－红细胞管，慢性肾小球肾炎、肾实质"),
        box(120, 180, "病变－颗粒管。"),
        box(120, 220, "60.参考答案：D"),
        box(120, 260, "61.参考答案：E解析：渗出液积液LD与血清LD比值>0.5"),
    ]
    answers, order = L.parse_answers(lines)
    check("解析出 3 条答案", len(answers) == 3, sorted(answers))
    check("答案字母对", answers[59]["answer"] == "D", answers[59])
    check("解析跨行接续", "肾实质" in answers[59]["analysis"], answers[59]["analysis"])
    check("无解析的题解析为空", answers[60]["analysis"] == "", answers[60])
    check("同行答案+解析都取到", answers[61]["answer"] == "E"
          and "0.5" in answers[61]["analysis"], answers[61])


def test_paper_starts():
    print("== 分卷切分（说明段 + 题号归 1） ==")
    lines = [
        box(120, 100, "一、以下每一道考题下面有A、B、C、D、E五个备选答案。"),
        box(120, 140, "1.第一题"),
        box(120, 180, "2.第二题"),
        box(120, 900, "一、以下每一道考题下面有A、B、C、D、E五个备选答案。"),
        box(120, 940, "1.新卷第一题"),
        box(120, 980, "2.新卷第二题"),
    ]
    starts = L.detect_paper_starts(lines)
    check("找到 2 个卷首", len(starts) == 2, starts)
    check("第一个卷首在说明段", starts[0][0] == 0, starts)
    check("第二个卷首位置正确", starts[1][0] == 3, starts)

    # 题号没有归 1 的不算卷首
    lines2 = [
        box(120, 100, "一、以下每一道考题下面有A、B、C、D、E五个备选答案。"),
        box(120, 140, "5.第五题"),
    ]
    check("题号不归 1 不算卷首", len(L.detect_paper_starts(lines2)) == 0)


def test_align():
    print("== 题号对不齐时的顺序对齐 ==")
    pairs = L.align_by_order([1, 2, 3, 4], [1, 2, 3, 4])
    check("完全对得上时按题号配", pairs == [(1, 1), (2, 2), (3, 3), (4, 4)], pairs)
    # 题号被读错（4 读成 7）
    pairs2 = L.align_by_order([1, 2, 3, 7], [1, 2, 3, 4])
    check("错位时按顺序兜底", (7, 4) in pairs2, pairs2)
    check("对得上的仍按题号", (1, 1) in pairs2 and (3, 3) in pairs2, pairs2)


def test_column_split_boxes():
    print("== 双栏分栏（OCR 原始框） ==")
    # 模拟一页双栏答案：左栏 x=120 起，右栏 x=800 起，y 几乎一样
    boxes = []
    for i in range(10):
        boxes.append(box(120, 200 + i * 40, f"左{i}题解析"))
    for i in range(10):
        boxes.append(box(800, 200 + i * 40, f"右{i}参考答案"))
    left, centered, right = L.column_split_boxes(boxes, page_width=1400)
    check("左右栏分开", len(left) == 10 and len(right) == 10,
          (len(left), len(right), len(centered)))
    check("左栏都是左边的框", all(b["x"] == 120 for b in left))
    check("右栏都是右边的框", all(b["x"] == 800 for b in right))

    # 单栏页面不该被劈开
    single = [box(120, 200 + i * 40, f"第{i}行") for i in range(10)]
    left2, c2, right2 = L.column_split_boxes(single, page_width=1400)
    check("单栏页保持原样", len(left2) == 10 and not right2 and not c2,
          (len(left2), len(c2), len(right2)))

    # 通栏标题（横跨两栏）单独归一类
    mixed = list(boxes) + [box(300, 100, "2023年临床医学检验技术（师）答案及解析", w=1000)]
    left3, c3, right3 = L.column_split_boxes(mixed, page_width=1400)
    check("通栏标题归中间", len(c3) == 1, (len(c3), len(left3), len(right3)))
    check("通栏不影响左右栏", len(left3) == 10 and len(right3) == 10)


def test_group_lines_no_cross_merge():
    print("== 合并同一行但不跨栏合并 ==")
    boxes = []
    for i in range(4):
        boxes.append(box(120, 300 + i * 40, f"{i + 1}.第一题", w=300))
        boxes.append(box(800, 300 + i * 40, f"{i + 1}.参考答案：A", w=300))
    lines = L.group_lines(boxes, page_width=1400)
    check("行数正确（不跨栏合并）", len(lines) == 8, [l["t"] for l in lines])
    check("左栏行归 L", all(l["col"] == "L" for l in lines if l["x"] == 120),
          [l["col"] for l in lines])
    check("右栏行归 R", all(l["col"] == "R" for l in lines if l["x"] == 800),
          [l["col"] for l in lines])
    texts = [l["t"] for l in lines]
    check("内容没串行", "1.第一题" in texts and "1.参考答案：A" in texts, texts)


def test_answer_regex_variants():
    print("== 答案行各种写法 ==")
    for text, num, ans in [
        ("87.参考答案：B解析：α1-抗胰", 87, "B"),
        ("31.答案:D", 31, "D"),
        ("45、答案:D", 45, "D"),
        ("36．答案：E", 36, "E"),
        ("22．答案：B", 22, "B"),
    ]:
        m = L.ANS_RE.match(text)
        ok = bool(m) and int(m.group(1)) == num and m.group(2) == ans
        check(f"能认出 {text[:14]}", ok, m.groups() if m else None)
    m = L.ANS_RE_LOOSE.match("69.：B")
    check("答案二字被 OCR 吃掉也能认", bool(m) and m.group(2) == "B",
          m.groups() if m else None)


def test_gutter_scoring():
    print("== 装订线：不能把页边空白当成装订线 ==")
    # 右边的页边空白比中间的空隙还宽，选错缝就会把左右两栏粘成一行
    boxes = []
    for i in range(12):
        boxes.append(box(120, 200 + i * 40, f"左{i}参考答案", w=380))
    for i in range(12):
        boxes.append(box(760, 200 + i * 40, f"右{i}参考答案", w=380))
    # 页面宽 1400，右边 1140~1400 是空白的（比中间的缝 500~760 宽）
    g = L.detect_gutter(boxes, page_width=1400)
    check("装订线落在两栏之间", g is not None and g[0] >= 500 and g[1] <= 760, g)
    left, c, right = L.column_split_boxes(boxes, page_width=1400)
    check("左右各 12 个框", len(left) == 12 and len(right) == 12,
          (len(left), len(right), len(c)))
    check("没把右边空白当成装订线", all(b["x"] >= 760 for b in right))


def test_column_major_order():
    print("== 竖排阅读序（左竖条读完再右竖条） ==")
    boxes = []
    # 左竖条：上半是上一卷的尾巴 90~92，下半是下一卷的开头 1~3
    for i, t in enumerate(["90.参考答案：A", "91.参考答案：B", "92.参考答案：C"]):
        boxes.append(box(120, 200 + i * 40, t, w=300))
    for i, t in enumerate(["1.参考答案：D", "2.参考答案：E", "3.参考答案：A"]):
        boxes.append(box(120, 900 + i * 40, t, w=300))
    # 右竖条：7~9
    for i, t in enumerate(["7.参考答案：B", "8.参考答案：C", "9.参考答案：D",
                            "10.参考答案：E"]):
        boxes.append(box(760, 200 + i * 40, t, w=300))
    lines = L.group_lines(boxes, page_width=1400)
    order = L.column_major_order(lines)
    nums = [int(L.ANS_RE.match(l["t"]).group(1)) for l in order]
    check("竖排读出来是 90,91,92,1,2,3,7,8,9,10",
          nums == [90, 91, 92, 1, 2, 3, 7, 8, 9, 10], nums)


def test_truncated_num_repair():
    print("== 题号掉十位的补号 ==")
    # 扫描件把「36」印成了「6」：上一题 35，这题 6 -> 补回 36
    check("6 补成 36", L.repair_truncated_num(6, 35) == 36,
          L.repair_truncated_num(6, 35))
    # 上一题 62、这题印成 9：补出来是 69，不是 63，不该补
    # （2015 专业实践能力：「…血液分析仪显.09，H示血小板极度减低…」）
    check("9 不补成 69", L.repair_truncated_num(9, 62) == 9,
          L.repair_truncated_num(9, 62))
    # 上一题 62、这题印成 3：补出来正好是 63，要补
    check("3 补成 63", L.repair_truncated_num(3, 62) == 63,
          L.repair_truncated_num(3, 62))
    # 跨十位边界不猜
    check("跨十位不补", L.repair_truncated_num(1, 19) == 1,
          L.repair_truncated_num(1, 19))
    # 上一题就是 9 或没有上一题，都不补
    check("上一题小于 10 不补", L.repair_truncated_num(3, 9) == 3)
    check("没有上一题不补", L.repair_truncated_num(3, None) == 3)

    # 整段流程：.09 那一行不能被当成题号，q62/q63 都要保住
    lines = [
        box(120, 100, "61.将可溶性抗体先吸附于适当大小的颗粒"),
        box(120, 140, "A.直接凝集反应"),
        box(120, 180, "B.间接凝集反应"),
        box(120, 220, "C.正向间接凝集反应"),
        box(120, 260, "D.反向间接凝集反应"),
        box(120, 300, "E.直接库姆斯试验"),
        box(120, 340, "62.患者，男，45岁。有皮肤过敏史，多次检查"),
        box(120, 380, "严血血小板均正常,而本次检查血液分析仪显"),
        box(120, 420, ".09，H示血小板极度减低，报警提示有血小板聚"),
        box(120, 460, "额翊铂集，涂片镜检显示血小板少见，成簇分布"),
        box(120, 500, "A.可直接发出报告中"),
        box(120, 540, "B.相同的部位再行抽血检查"),
        box(120, 580, "C.换不同的部位再行抽血检测"),
        box(120, 620, "D.血液稀释后再上机检测"),
        box(120, 660, "E.改用其他抗凝剂或者不加抗凝剂抽血"),
        box(120, 700, "63.患儿,男，1岁。持续发热,手、足、口腔和"),
        box(120, 740, "A.疱疹病毒"),
        box(120, 780, "B.腺病毒"),
        box(120, 820, "C.柯萨奇病毒或艾可病毒"),
        box(120, 860, "D.EB病毒"),
        box(120, 900, "E.巨细胞病毒"),
    ]
    qs = L.parse_questions(lines, paper_name="专业实践能力", year=2015)
    nums = [q["num"] for q in qs]
    check("62、63 都没丢", 62 in nums and 63 in nums, nums)
    check("没有多出 69", 69 not in nums, nums)
    q62 = next((q for q in qs if q["num"] == 62), None)
    check("62 的题干对", q62 and q62["stem"].startswith("患者，男，45岁"),
          q62["stem"] if q62 else None)
    check("62 的选项齐", q62 and len(q62["options"]) == 5,
          q62["options"] if q62 else None)
    q63 = next((q for q in qs if q["num"] == 63), None)
    check("63 的题干对", q63 and q63["stem"].startswith("患儿,男，1岁"),
          q63["stem"] if q63 else None)
    check("63 的选项齐", q63 and len(q63["options"]) == 5,
          q63["options"] if q63 else None)


def test_phantom_jump_num():
    """正文里的数字被当成题号（「100.0」「12.6×10°/L」）。"""
    print("== 跳号的假题号 ==")

    # 2016 专业实践能力：第 15 题后面混进一行「100.0」（图表读数）。
    # 被当成第 100 题的话，后面 16~99 全成「往回跳」，整卷只剩 15 题。
    lines = [
        box(120, 100, "14.下列对尿液免疫球蛋白（Ig）定量的临床"),
        box(120, 140, "意义的叙述,错误的是（"),
        box(120, 180, "A.机体的免疫功能或反应的异常"),
        box(120, 220, "B.基底膜细胞间缝隙的孔径"),
        box(120, 260, "C.单纯性膜孔径增大时"),
        box(120, 300, "D.40% ± 50% 的 IgA 肾病患者"),
        box(120, 340, "E.尿液中幼粒轻链的检测"),
        box(120, 380, "15.血钙降低常见于（"),
        box(120, 420, "A.原发性甲状旁腺功能亢进"),
        box(120, 440, "100.0"),
        box(120, 480, "B.恶性肿瘤骨转移"),
        box(120, 520, "C.脱水"),
        box(120, 560, "D.急性肾功能不全"),
        box(120, 600, "E.维生素 D缺乏"),
        box(120, 640, "16.冷球蛋白的特点不包括（"),
        box(120, 680, "A.固定补体产生炎症反应"),
        box(120, 720, "B.4℃时不溶解并自发沉淀"),
        box(120, 760, "C.可分为单株型和混合型"),
        box(120, 800, "D.30℃溶解"),
        box(120, 840, "E.正常人血清中可含有冷球蛋白"),
    ]
    qs = L.parse_questions(lines, paper_name="专业实践能力", year=2016)
    nums = [q["num"] for q in qs]
    check("假题号 100 不能出现", 100 not in nums, nums)
    check("15、16 都在", 15 in nums and 16 in nums, nums)
    q15 = next((q for q in qs if q["num"] == 15), None)
    check("15 的题干没被 100.0 污染",
          q15 and "100.0" not in q15["stem"], q15["stem"] if q15 else None)
    check("15 的选项齐", q15 and len(q15["options"]) == 5,
          q15["options"] if q15 else None)

    # 2022 相关专业知识：第 9 题题干里的「12.6×10°/L」不能当成第 12 题。
    # 真跳号（中间漏了一道题）时后面的题号会更大，那时要认。
    lines = [
        box(120, 100, "9.患者男，32岁。红细胞沉降率35mm/h，WBC"),
        box(120, 140, "12.6×10°/L，其他检查正常，各种影响学检查"),
        box(120, 180, "正常。可引起红细胞沉降率加快的可能原因是"),
        box(120, 220, "A. 炎症"),
        box(120, 260, "B.组织坏死"),
        box(120, 300, "C. 良性肿瘤"),
        box(120, 340, "D.红细胞增多"),
        box(120, 380, "E.肝病"),
        box(120, 420, "10.血小板的寿命是（）"),
        box(120, 460, "A.120天"),
        box(120, 500, "B.10~15天"),
        box(120, 540, "C. 2~3天"),
        box(120, 580, "D.8~10 天"),
        box(120, 620, "E.7~14天"),
    ]
    qs = L.parse_questions(lines, paper_name="相关专业知识", year=2022)
    nums = [q["num"] for q in qs]
    check("题干里的 12.6 不是题号", 12 not in nums, nums)
    check("9、10 都在", 9 in nums and 10 in nums, nums)

    # 真跳号：上一题 3，这一行是第 5 题（漏了 4），后面接着 6 -> 认
    lines = [
        box(120, 100, "3.下列对细胞因子的叙述,错误的是("),
        box(120, 140, "A.细胞因子具有网络性"),
        box(120, 180, "B.细胞因子仅由免疫细胞产生"),
        box(120, 220, "C.细胞因子是蛋白质或小分子多肽"),
        box(120, 260, "5.SS 琼脂平板培养基是属于("),
        box(120, 300, "A.血平板"),
        box(120, 340, "B.伊红美蓝琼脂"),
        box(120, 380, "C.麦康凯琼脂"),
        box(120, 420, "D.营养琼脂"),
        box(120, 460, "E.低选择性琼脂"),
        box(120, 500, "6.下列对尿沉渣的叙述,正确的是("),
        box(120, 540, "A.红细胞"),
        box(120, 580, "B.白细胞"),
        box(120, 620, "C.上皮细胞"),
        box(120, 660, "D.管型"),
        box(120, 700, "E.结晶"),
    ]
    qs = L.parse_questions(lines, paper_name="专业实践能力", year=2015)
    nums = [q["num"] for q in qs]
    check("真跳号的第 5 题要认", 5 in nums, nums)
    q5 = next((q for q in qs if q["num"] == 5), None)
    check("第 5 题的题干对",
          q5 and q5["stem"].startswith("SS 琼脂平板培养基"), q5["stem"] if q5 else None)


def test_clean_rules():
    print("== 清洗规则（上标 / 单位 / 错别字） ==")
    import import_past_papers as M

    def cl(t):
        log = []
        return M.clean_text(t, log, None)

    # ---- 上标 ----
    check("×1012/L -> ×10\u00b9\u00b2/L", cl("RBC3.6×1012/L") == "RBC3.6×10\u00b9\u00b2/L",
          cl("RBC3.6×1012/L"))
    check("×109/L -> ×10\u2079/L", cl("白细胞46×109/L") == "白细胞46×10\u2079/L",
          cl("白细胞46×109/L"))
    check("×10\u00b0/L(白细胞) -> 10\u2079/L",
          cl("WBC20.6×10\u00b0/L") == "WBC20.6×10\u2079/L", cl("WBC20.6×10\u00b0/L"))
    check("×10/L(白细胞) -> 10\u2079/L",
          cl("PLT236×10/L") == "PLT236×10\u2079/L", cl("PLT236×10/L"))
    check("×10\u00b0/L(红细胞) -> 10\u00b9\u00b2/L",
          cl("RBC 3.83×10\u00b0/L") == "RBC 3.83×10\u00b9\u00b2/L",
          cl("RBC 3.83×10\u00b0/L"))
    check("×102/L(红细胞) -> 10\u00b9\u00b2/L",
          cl("RBC 5.0×102/L") == "RBC 5.0×10\u00b9\u00b2/L", cl("RBC 5.0×102/L"))
    check("×10l\u00b2/L -> 10\u00b9\u00b2/L",
          cl("RBC2.7×10l\u00b2/L") == "RBC2.7×10\u00b9\u00b2/L", cl("RBC2.7×10l\u00b2/L"))
    check("×100% 是百分比，不动", cl("阳性率×100%") == "阳性率×100%", cl("阳性率×100%"))
    check("X×100/(100+Y) 不动",
          cl("X×100/(100+Y)") == "X×100/(100+Y)", cl("X×100/(100+Y)"))
    check("已经是上标的不动", cl("×10\u00b9/L") == "×10\u00b9/L", cl("×10\u00b9/L"))
    check("×10\u00b08CFU/ml -> 10\u2078CFU/ml",
          cl("3×10\u00b08CFU/ml") == "3×10\u2078CFU/ml", cl("3×10\u00b08CFU/ml"))

    # ---- 单位 ----
    check("mmo1 -> mmol", cl("血糖≥11.1mmo1/L") == "血糖≥11.1mmol/L", cl("血糖≥11.1mmo1/L"))
    check("μmo1 -> μmol", cl("150μmo1/L") == "150μmol/L", cl("150μmo1/L"))
    check("MCV130f1 -> MCV130fl", cl("MCV130f1") == "MCV130fl", cl("MCV130f1"))
    check("umol/L -> μmol/L", cl("肌酐88.4 umol/L") == "肌酐88.4 μmol/L",
          cl("肌酐88.4 umol/L"))
    check("mm3 -> mm³", cl("0.05mm3") == "0.05mm³", cl("0.05mm3"))
    check("mg/d1 -> mg/dl", cl("钙(200mg/d1)") == "钙(200mg/dl)", cl("钙(200mg/d1)"))

    # ---- 错别字（只做词组替换） ----
    check("人院 -> 入院", cl("因发热10 d人院") == "因发热10 d入院", cl("因发热10 d人院"))
    check("亲合素 -> 亲和素", cl("生物素-亲合素系统") == "生物素-亲和素系统",
          cl("生物素-亲合素系统"))
    check("晓虫 -> 蛲虫", cl("诊断晓虫病") == "诊断蛲虫病", cl("诊断晓虫病"))
    check("后穹窟 -> 后穹隆", cl("后穹窟穿刺术") == "后穹隆穿刺术", cl("后穹窟穿刺术"))
    check("正常人 不动", cl("正常人参考区间") == "正常人参考区间", cl("正常人参考区间"))
    check("抗人球蛋白 不动", cl("抗人球蛋白") == "抗人球蛋白", cl("抗人球蛋白"))
    check("反映 不动", cl("反映病情") == "反映病情", cl("反映病情"))
    check("迁徙 不动", cl("细菌迁徙生长") == "细菌迁徙生长", cl("细菌迁徙生长"))
    check("腺苷脱氨酶 不动", cl("腺苷脱氨酶") == "腺苷脱氨酶", cl("腺苷脱氨酶"))


def test_watermark_answers():
    print("== 答案水印污染 ==")
    # 答案行尾巴上挂着水印残骸，真正的解析在下一行的「解析：」里
    lines = [
        {"t": "88.答案：BCA，四样T"},
        {"t": "解析：离心尿液显微镜检查，细胞检查10个高倍镜视野。"},
    ]
    ans, _ = L.parse_answers(lines)
    check("水印尾巴被丢掉", ans[88]["analysis"].startswith("离心尿液"),
          ans[88]["analysis"][:30])
    check("解析前没有残留水印", "四样T" not in ans[88]["analysis"],
          ans[88]["analysis"][:30])
    check("解析前没有重复的「解析：」",
          not ans[88]["analysis"].startswith("解析："), ans[88]["analysis"][:30])

    # 尾巴是正文的一部分（下一行不是「解析：」），要照收
    lines2 = [
        {"t": "12.答案：E某些蛋白"},
        {"t": "的说法不准确。"},
    ]
    ans2, _ = L.parse_answers(lines2)
    check("正文尾巴不被误删", "某些蛋白" in ans2[12]["analysis"],
          ans2[12]["analysis"])

    # 正常写法：解析就在答案行后面
    lines3 = [
        {"t": "16.参考答案：D解析：血管内溶血急性多见。"},
        {"t": "常见于输血反应。"},
    ]
    ans3, _ = L.parse_answers(lines3)
    check("正常解析不被改动",
          ans3[16]["analysis"] == "血管内溶血急性多见。常见于输血反应。",
          ans3[16]["analysis"])


def test_normalize_answer():
    print("== 答案类型判定 ==")
    import import_past_papers as I

    # 2016 专业实践能力 88 在人工表里，这里用一道不在表里的题试自动规则
    q = {"num": 88, "answer": "BCA"}
    how = I._normalize_answer(q, 2019, "专业实践能力")
    check("多字母答案被削成首字母", q["answer"] == "B", q["answer"])
    check("类型定成单选", q["type"] == "single", q.get("type"))
    check("记下是被水印削的", how == "trimmed", how)

    q2 = {"num": 69, "answer": "CA"}
    I._normalize_answer(q2, 2021, "基础知识")
    check("人工表优先", q2["answer"] == "C", q2["answer"])
    check("人工表也定成单选", q2["type"] == "single", q2.get("type"))

    q3 = {"num": 1, "answer": "B"}
    how3 = I._normalize_answer(q3, 2020, "基础知识")
    check("正常答案不动", q3["answer"] == "B" and how3 == "", (q3, how3))

    q4 = {"num": 2, "answer": "A,C"}
    I._normalize_answer(q4, 2020, "基础知识")
    check("带逗号的多字母也只剩首字母", q4["answer"] == "A", q4["answer"])

    check("人工表覆盖 23 道题", len(I.WATERMARK_ANSWERS) == 23,
          len(I.WATERMARK_ANSWERS))
    check("人工表里没有多选题", I.MANUAL_MULTI_ANSWERS == {},
          I.MANUAL_MULTI_ANSWERS)


def test_watermark_fragment():
    print("== 水印残骸识别 ==")
    # 水印被 OCR 读成的垃碎：「案」「答」旁边多出一个不相干的字
    check("整段水印被剔干净",
          L.strip_watermark("8：案苔.12") == "",
          repr(L.strip_watermark("8：案苔.12")))
    check("水印在正文中间也能剔",
          L.strip_watermark("球蛋白是由浆细胞生成。。8：案苔.12")
          == "球蛋白是由浆细胞生成。。",
          repr(L.strip_watermark("球蛋白是由浆细胞生成。。8：案苔.12")))
    check("正常的「认真答题」不被动",
          L.strip_watermark("认真答题") == "认真答题",
          repr(L.strip_watermark("认真答题")))
    check("正常的「答案和解析」不被动",
          L.strip_watermark("答案和解析") == "答案和解析",
          repr(L.strip_watermark("答案和解析")))
    check("「0:答.18」这种也覆盖",
          L.strip_watermark("0:答.18") == "",
          repr(L.strip_watermark("0:答.18")))

    # 消析正文里的水印行要丢掉，但不能把正文一起丢了
    lines = [
        {"t": "12.答案：B。8：案苔.12"},
        {"t": "解析：浆细胞由浆细胞生成。"},
    ]
    ans, _ = L.parse_answers(lines)
    check("水印行不进解析",
          ans[12]["analysis"] == "浆细胞由浆细胞生成。",
          repr(ans[12]["analysis"]))

    lines2 = [
        {"t": "13.答案：C"},
        {"t": "浆细胞由浆细胞生成。8：案苔.12"},
    ]
    ans2, _ = L.parse_answers(lines2)
    check("正文行里的水印被剔掉、正文保留",
          ans2[13]["analysis"] == "浆细胞由浆细胞生成。",
          repr(ans2[13]["analysis"]))


def test_strip_ad():
    print("== 广告残骸裁剪 ==")
    check("公众号广告被截掉",
          L.strip_ad("细菌感染为渗出液形成的原因，其余项均为公众号开通免费题库")
          == "细菌感染为渗出液形成的原因，其余项均为",
          repr(L.strip_ad("细菌感染为渗出液形成的原因，其余项均为公众号开通免费题库")))
    check("微信搜索广告被截掉",
          L.strip_ad("可推断为类风湿性关节炎。微信搜索：医品堂卫生考试中心公众号开通免费题")
          == "可推断为类风湿性关节炎",
          repr(L.strip_ad("可推断为类风湿性关节炎。微信搜索：医品堂卫生考试中心公众号开通免费题")))
    check("扫码广告被截掉",
          L.strip_ad("菌落变异扫码查潘商品详情") == "菌落变异",
          repr(L.strip_ad("菌落变异扫码查潘商品详情")))
    check("正文不被误伤",
          L.strip_ad("白细胞计数23×109/L，中性粒细胞95%") == "白细胞计数23×109/L，中性粒细胞95%",
          repr(L.strip_ad("白细胞计数23×109/L，中性粒细胞95%")))


def main():
    print("历年真题解析器单元测试")
    print("-" * 40)
    test_merge_same_row()
    test_split_columns()
    test_noise_filter()
    test_parse_questions_basic()
    test_shared_options()
    test_shared_across_pages()
    test_parse_answers()
    test_paper_starts()
    test_align()
    test_column_split_boxes()
    test_gutter_scoring()
    test_column_major_order()
    test_group_lines_no_cross_merge()
    test_answer_regex_variants()
    test_truncated_num_repair()
    test_phantom_jump_num()
    test_clean_rules()
    test_watermark_answers()
    test_watermark_fragment()
    test_normalize_answer()
    test_strip_ad()
    print("-" * 40)
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        for f in FAILED:
            print("  FAIL:", f)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
