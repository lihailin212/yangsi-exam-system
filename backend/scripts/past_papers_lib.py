# -*- coding: utf-8 -*-
"""历年真题解析核心逻辑（纯函数，方便单测）。

这个模块只做"文本 -> 结构化题目"的转换，不碰数据库、不碰文件，
所以测试时可以直接喂构造的 OCR 文本，断言解析结果。

关键约定（都是对着真题 PDF 实测出来的）：
- PDF 是跨年合订的：2010 的试卷文件尾部就是 2011 基础知识。
  所以卷的切分不能靠文件名，要靠"说明段 + 题号归 1"这个主锚点。
- 每个卷都以「以下每一道…五个备选答案」说明段开头，题号从 1 重新开始。
- 配伍题（题型二/题型三）的共享备选答案标记里的题号会被 OCR 读错，
  所以共享选项的生效范围不依赖标记里的题号。
- 答案格式是「NN.参考答案：X解析：…」，答案与解析在同一行。
"""
import re

# 卷名（按真题里的固定顺序）
PAPER_NAMES = ["基础知识", "相关专业知识", "专业知识", "专业实践能力"]

# 说明段特征串。「一、」这种序号 OCR 经常丢（会变成「、」），所以只认特征串。
INSTRUCTION_MARK = "以下每一道"
SHARED_INSTRUCTION_MARK = "以下提供若干组考题"
SHARED_INSTRUCTION_MARK2 = "共用备选答案单选题"

# 共享备选答案标记：兼容全角/半角括号和各种连接符
SHARED_MARK_RE = re.compile(
    r"[(（]\s*(\d{1,3})\s*[～~\u2014\-]+\s*(\d{1,3})\s*题\s*"
    r"共用备选答案\s*[)）]")

# 配慷题组标记：、83-86题、、83-86题共用备选答案》
# 也覆盖「、83-86题共用备选答案」的形式。
# OCR 常把连接符重复印一遍（「（92～~93题共用备选答案）」）——这种要认，
# 否则整组配伍题的备选答案会被当成正文丢掉（2015 专业知识 92、93 就是
# 这样丢的）。
GROUP_MARK_RE = re.compile(
    r"[(（]\s*(\d{1,3})\s*[～~\u2014\-]+\s*(\d{1,3})\s*题\s*"
    r"(?:共用备选答案)?\s*[)）]")

# OCR 偶尔把连接符吃掉："（9294题共用备选答案）" -> 92、94
GROUP_MARK_RE2 = re.compile(r"[(（]\s*(\d{2})(\d{2})\s*题\s*(?:共用备选答案)?\s*[)）]")
# 三位数："（1517题）" -> 15、17
GROUP_MARK_RE3 = re.compile(r"[(（]\s*(\d)(\d{2})\s*题\s*(?:共用备选答案)?\s*[)）]")

# OCR 把连接符认成点号："（93.95题共用备选答案）"（原卷是「93～95」）；
# 连接符还有别的写法（-、～、~、、），左括号也可能整个丢掉
# （"90~92题共用备选答案）"）。这种标记**整行**就是它，所以用行首行尾
# 都锚死的宽松版本认，免得误伤题干里的数字（"50.剂量1.5mg" 这种）。
GROUP_MARK_LOOSE_RE = re.compile(
    r"^[\s　]*[(（]?[\s　]*(\d{1,3})[\s　]*[-~～—.．、,，_－]+[\s　]*(\d{1,3})"
    r"[\s　]*题[\s　]*(?:共用备选答案)?[\s　]*[)）]?[\s　]*$")
# 连接符整个丢了："9092题共用备选答案）"
GROUP_MARK_LOOSE_RE2 = re.compile(
    r"^[\s　]*[(（]?[\s　]*(\d{2})(\d{2})[\s　]*题[\s　]*(?:共用备选答案)?"
    r"[\s　]*[)）]?[\s　]*$")

# 共用题干组标记："（93～94题共用题干）"、"（83-86题共用题干）"
# 这类题是「一段病例 + 若干道题」：题干（病例）是共用的，**选项不共用**
# （跟配伍题的「共用备选答案」完全不同）。组标记里的题号范围很有用：
# 组内题号必须连号，OCR 认错一位时可以据此纠正。
GROUP_STEM_MARK_RE = re.compile(
    r"[(（]\s*(\d{1,3})\s*[～~\u2014\-]+\s*(\d{1,3})\s*题\s*"
    r"共用\s*(?:题干|案例|病例|资料|背景)\s*[)）]")

# 选项里的字母+句号（用于拆裂粘在一行里的多个选项）
OPT_MARK_RE = re.compile(r"([A-Ea-e])\s*[.．]")

# 题号行：1. / 1、 / 1．
# OCR 偶尔把句号认成逗号（"35，患者，女，28岁"），逗号后面跟数字的不算
# （免得把 "1,234" 这种数字当成题号）。
QNUM_RE = re.compile(r"^[\s_—\-·.]*(\d{1,3})\s*(?:[.、．]|[,，](?!\d))\s*(.*)$")
# 汉字（用来判断一行到底像不像题干）
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 选项行：A. / a、 / A．
OPT_RE = re.compile(r"^([A-Ea-e])\s*[.、．]\s*(.*)$")
# 题号前面粘了相邻栏/上一页的杂字："胖 56.不属于…"、"贾62.血细胞…"、
# "M2.不是网织红细胞"、"氧非75.NK细胞"。杂字长度不定（1~4 个字符）。
# 只有在题号正好是上一题的下一号时才认，否则容易把 "1.5mm" 之类误当成题号。
NOISY_QNUM_RE = re.compile(
    r"^(?P<junk>[^\d]{1,8}?)\s*(?P<num>\d{1,3})\s*[.、．]\s*(?P<rest>.*)$")
# 题号后面没有点号："单27证明细菌具有鞭毛结构…"、"41粪便中巨噬细胞来自…"。
# OCR 经常把「27.」的点号吃掉，题号后面直接跟汉字。这种题号只在
# 「正好是上一题的下一号」时才认，免得把题干里的数字当成题号。
NODOT_QNUM_RE = re.compile(
    r"^(?P<junk>[^\d]{0,4}?)(?P<num>\d{1,3})(?![\d])(?P<rest>[\u4e00-\u9fff].*)$")
# 题号前面粘了页码/别的数字："0873.患者，男，30岁" 其实是 73。
# 这里抓行首连着的一串数字，超过 3 位时取后两位当题号。
NUM_PREFIX_RE = re.compile(r"^(?P<digits>\d{1,5})\s*[.、．]\s*(?P<rest>.*)$")
# 题号后面印的是句号："79。患者男，36岁…"。这种只有在题号正好接上
# 上一题时才认——"NAP染色积分为185。该患者出血是由于("里的 185 是分值，
# 不是题号。
CJK_DOT_QNUM_RE = re.compile(
    r"^(?P<num>\d{1,3})\s*。\s*(?P<rest>[\u4e00-\u9fff].*)$")
# 题号前面只粘了标点：",71.该疾病…"、"）63.患儿…"、"，81.血涂片…"。
# 标点杂字必须短（不超过 3 个），且不能含汉字/字母（那种走 NOISY_QNUM_RE）。
PUNCT_QNUM_RE = re.compile(
    r"^(?P<junk>[，,。；：、（）()【】\[\]！!？?～~\-—＋+][，,。；：、（）()【】\[\]！!？?～~\-—＋+]{0,2})"
    r"\s*(?P<num>\d{1,3})\s*[.、．]\s*(?P<rest>.*)$")
# 答案行：01.参考答案：C解析：… / 31.答案:D / 36．答案：E
# 早年卷写「参考答案」，近年卷只写「答案」，还有的整句被 OCR 吃掉「答案」二字。
# 「43.参考答案；E」的分号、「77.参考答案：.C」的多余句点都见过
# 「21答案：E」「63  答案:C」「13答案B」：题号后的点号、冒号都可能没印出来
# 「答案」两个字有时只 OCR 出一个：「14.案：C80」「34.答：D合酒量」
ANS_RE = re.compile(r"^[\s_—\-·.]*(\d{1,3})\s*(?:[.、．。]|[,，](?!\d))?\s*(?:参考)?(?:答案|答|案)\s*[：:；;]?\s*[.．]?\s*([A-Ea-e]{1,5})\s*[。.．、]?\s*(.*)$")
# OCR 把「答案」吃掉了：69.：B
ANS_RE_LOOSE = re.compile(r"^[\s_—\-·.]*(\d{1,3})\s*(?:[.、．。]|[,，](?!\d))\s*[：:；;]\s*[.．]?\s*([A-Ea-e]{1,5})\s*[。.．、]?\s*(.*)$")
# 题号被重复印/OCR 重复读了一遍："11.11.答案：B"、"24.3答案：C"。
# 取第一个数字当题号，后面重复的那段忽略。
ANS_RE2 = re.compile(
    r"^[\s_—\-·.]*(\d{1,3})(?:\s*[.、．。]\s*\d{1,3})*\s*[.、．。]?\s*"
    r"(?:参考)?(?:答案|答|案)\s*[：:；;]?\s*[.．]?\s*([A-Ea-e]{1,5})\s*[。.．、]?\s*(.*)$")
# 题号整个丢了，只剩「答案：X」。靠上下文补题号。
ANS_BARE_RE = re.compile(
    r"^[\s_—\-·.]*(?:答案|答|案)\s*[：:；;]?\s*[.．]?\s*([A-Ea-e]{1,5})\s*[。.．、]?\s*(.*)$")
# 「答案」两个字被整个读成了别的字，题号后面直接跟冒号+字母：
# "91.纹榜：C"、"63.：基"。杂字最多 4 个字，字母必须紧跟冒号。
NOISY_ANS_RE = re.compile(
    r"^[\s_—\-·.]*(\d{1,3})\s*(?:[.、．。]|[,，](?!\d))?\s*([^\d：:；;]{0,4})[：:；;]\s*[.．]?\s*([A-Ea-e])(?![A-Za-z])")
# 紧凑写法：一行里挤了好几道题的答案「53.B54.D55.D56.A」/「83.B 84.A 85.D」
# 前面的 \s* 是必需的：一行里几道题之间常有空格，不然只认得出第一道。
# 前导的点也算：「.12.B」这种行首多一个点的写法（2012 专业知识第 12 题）
ANS_PAIR_RE = re.compile(r"\s*[\s_—\-·.]*(\d{1,3})\s*[.、．。]\s*([A-Ea-e]{1,5})")
# 题号和答案之间没有分隔符：「97.A 98E」里的 98E（要求两位以上，避免把「3C」当答案）
ANS_PAIR_NOSEP_RE = re.compile(r"\s*[\s_—\-·]*(\d{2,3})\s*([A-Ea-e]{1,5})(?![A-Za-z])")
# 只剩题号、答案字母被 OCR 吃掉了：「99.」
ORPHAN_NUM_RE = re.compile(r"^[\s_—\-·]*(\d{1,3})\s*[.、．]\s*$")
# 卷名标题行（答案侧可靠）：2010年检验师基础知识 / 2023 年临床医学检验技术（师）试卷
TITLE_RE = re.compile(r"(\d{4})\s*年[^0-9]{0,20}?(基础知识|相关专业知识|专业知识|专业实践能力)")
# 单独一行只有卷名（试卷侧的卷名常被单独排一行）
BARE_PAPER_RE = re.compile(r"^[\s　]*(基础知识|相关专业知识|专业知识|专业实践能力)[\s　]*$")
# 年份行（试卷侧常见「2010 年检验师职称资格考试」）
YEAR_LINE_RE = re.compile(r"(\d{4})\s*年")
# 年份标题行：整行就是一个年份标题（以年份开头）
YEAR_TITLE_RE = re.compile(r"^(\d{4})\s*年")
# 解析起点。写成「解析；」的也有（“4. C”那年的答案册就是这个样子）。
ANALYSIS_RE = re.compile(r"解析\s*[：:;；]")

# ---------------------------------------------------------------- 水印残骸
#
# 答案册的页面上盖着斜向水印（「需要检验历年真题联系微信…」）。
# 水印是浅灰色的斜向叠加层，现在在 OCR 之前就把水印像素抹掉了
# （见 past_papers_reocr.deshade）；扫描件本身擦不干净的时候，
# 文本层再兜一层底。
#
# 残骸的样子：「案」「答」旁边多出一个不相干的字 ——
# 「8：案答.00」「A：案客.I」「1：雾答8T」「0.案窖」。
# 真正的答案行写的是「答案」，前后不会多出别的字。
#
# 判定用双向白名单（宁可漏判，别误伤正文）：
#   「案」前面是 答/方/个/例  -> 正常词（答案/方案/个案/案例）
#   「答」后面是 案/题/试/…  -> 正常词（答案/答题/答对/答错…）
#   「案」后面跟不相干的字   -> 残骸
#   「答」前面跟不相干的字   -> 残骸

# 残骸里到处都是数字和 ASCII 标点，往两边吸的时候这些一律吸掉。
WM_NOISE = set("0123456789 \t\r\n"
               ".,:;!?()[]{}<>/\\|-+=*&^%$#@~`\'\""
               "：；．")
# 句末标点：它们属于正文。往左吸的时候碰到它们要停下，
# 否则「……生成。。8：案苔.12」里的句号会被一起吃掉。
WM_STOP = set("。，、！？）》」』…～·")

# 「案」后面跟这些字 = 残骸（真词「答案」由前一个字排除）
WM_GARBLE_AFTER = "答客咨容谷警策苔睿荟窖含照蓉誉著音"
# 「答」前面跟这些字 = 残骸
WM_GARBLE_BEFORE = "案家菜实索密素卖虫症赛醍队策谷誉苟警客咨容蓉荟窖睿含照"
# 「案」前面跟这些字 = 正常词
WM_OK_PREV_ANS = "答方个例"
# 「答」前面跟这些字 = 正常词（应答、作答、选择、阅读、回答……）
WM_OK_PREV_DA = "应作选阅满回以好请无不未已"
# 「答」后面跟这些字 = 正常词（答案、答题、答对、答错、答卷……）
WM_OK_NEXT_DA = "案题试复卷者语问用对错访理应"

# 页眉：答案册每页顶上那行「2013临床医学检验技术（师）卫生资格考试试卷答案及解析」。
# 它是通栏的，通常被分栏算法挡在外面；偶尔会被并进正文行，
# 这时要从正文里剔掉（后面紧跟的页码一起）。
WM_HEADER_RE = re.compile(
    r"(?:20\d{2}\s*年?\s*临床医学检验技术[（(]师[）)]\s*(?:卫生资格考试)?\s*"
    r"(?:试卷)?\s*(?:答案)?\s*[及和]\s*解析"
    r"|卫生资格考试\s*(?:试卷)?\s*(?:答案)?\s*[及和]\s*解析)"
    r"(?:\d{1,4}(?=[\u4e00-\u9fff]))?")
# 整行就是页眉（答案册的卷名标题）
WM_HEADER_LINE_RE = re.compile(
    r"^(?:20\d{2}\s*年?\s*)?(?:临床医学检验技术[（(]师[）)]\s*)?"
    r"(?:卫生资格考试)?\s*(?:试卷)?\s*(?:答案)?\s*[及和]\s*解析$")
# 「2012师（基础知识）答案」这种老卷名
WM_TITLE_LINE_RE = re.compile(r"^20\d{2}\s*师[（(][^）)]{0,12}[）)]\s*答案$")


def _wm_is_noise(ch):
    return ch in WM_NOISE


def _wm_spans(t):
    """找出文本里所有水印残骸的区间 [(起, 止), ...]。"""
    n = len(t)
    spans = []
    i = 0
    while i < n:
        ch = t[i]
        anchor = None
        partner = None
        if ch == "案":
            prev = t[i - 1] if i else ""
            nxt = t[i + 1] if i + 1 < n else ""
            if prev not in WM_OK_PREV_ANS:
                if nxt in WM_GARBLE_AFTER:
                    anchor, partner = i, i + 1
                elif (prev in WM_NOISE and nxt in WM_NOISE
                      and re.search(r"\d", t[max(0, i - 3):i + 4])):
                    anchor = i
        elif ch == "答":
            prev = t[i - 1] if i else ""
            nxt = t[i + 1] if i + 1 < n else ""
            if prev not in WM_OK_PREV_DA and nxt not in WM_OK_NEXT_DA:
                if prev in WM_GARBLE_BEFORE:
                    anchor, partner = i, i - 1
                elif prev in WM_NOISE and nxt in WM_NOISE:
                    anchor = i
        if anchor is None:
            i += 1
            continue
        s, e = anchor, anchor + 1
        if partner is not None and partner == e:
            e += 1
        elif partner is not None and partner == s - 1:
            s -= 1
        # 向两边吸噪声：句末标点要停下（那是正文的），字母只在紧挨着
        # 残骸核心的时候才吸（否则答案字母 C、D 会被吃掉）。
        while s > 0:
            c = t[s - 1]
            if c in WM_STOP:
                break
            if _wm_is_noise(c):
                s -= 1
                continue
            if c.isascii() and c.isalpha() and s == anchor:
                s -= 1                  # 紧挨着残骸的字母，一并去掉
                continue
            break
        while e < n:
            c = t[e]
            if c in WM_STOP:
                break
            if _wm_is_noise(c):
                e += 1
                continue
            if c.isascii() and c.isalpha() and e == anchor + 2:
                e += 1
                continue
            break
        spans.append((s, e))
        i = max(e, i + 1)
    return spans


# 答案册/试卷上的推广残骸。这些词只出现在广告里（题库里没有“扫码看商品详情”
# 这种题干），所以按锚点直接截断即可；锚点之前的正文一律保留。
AD_RE = re.compile(
    r"(?:"
    r"微信搜索|微信客服|微信公众号|微信号|联系微信|加微信|扫码看|扫码查|扫码|"
    r"微信(?=\s*[：:！!]?\s*$)|"
    r"搜索[:：]|"
    r"公众号|免费题库|免费领题|更多资料|更多真题|更多解析|"
    r"真题/押题|题/(?:押题|原题|保过班)|保过班|押题|原题|历年真题|医品堂|卫资网|"
    r"二维码|客服微信|淘宝|加群"
    r")")


def strip_ad(text):
    """截掉推广广告残骸（公众号/扫码/搜索：…），保留广告之前的正文。"""
    t = (text or "").strip()
    if not t:
        return ""
    m = AD_RE.search(t)
    if not m:
        return t
    out = t[:m.start()].strip()
    # 截断处若留下孤零零的连接词/标点，顺手去掉尾巴
    out = re.sub(r"[，,。；;：:、\s/／]+$", "", out)
    return out


def strip_watermark(text):
    """把解析正文里的水印残骸剥掉，返回剥干净的文字。

    只动「案/答」旁边多出不相干字的那几处 —— 宁可漏判也别误伤正文，
    所以「认真答题」「答案和解析」这种正常词不会被动。
    """
    t = (text or "").strip()
    if not t:
        return ""
    # 页眉夹在正文中间的情况
    t = WM_HEADER_RE.sub("", t).strip()
    # 推广广告残骸（公众号/扫码/搜索：…）直接截尾
    t = strip_ad(t)
    spans = _wm_spans(t)
    if spans:
        out = []
        last = 0
        for s, e in spans:
            out.append(t[last:s])
            last = e
        out.append(t[last:])
        t = "".join(out).strip()
    # 剥完只剩标点和零碎字 → 当成没有解析
    if not t or not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", t):
        return ""
    return t


def is_watermark_fragment(text):
    """这段文字去掉水印之后是不是就没了。"""
    t = (text or "").strip()
    if not t:
        return True
    return not strip_watermark(t)


# 广告/水印行
AD_KEYWORDS = ("微信", "联系", "真题", "押题", "客服", "正版", "扫描", "加群", "QQ", "淘宝")
PAGE_NOISE_RE = re.compile(r"^第\s*\d+\s*页")
# 页眉上的页码：一行孤零零的数字（有时带一个 '|' 或 '/' 尾巴）
PAGE_NUM_RE = re.compile(r"^\d{1,5}[|/]?$")


def is_noise(text):
    """页眉广告、页脚页码、装饰性文字。"""
    t = (text or "").strip()
    if not t:
        return True
    if PAGE_NOISE_RE.match(t):
        return True
    if WM_HEADER_LINE_RE.match(t) or WM_TITLE_LINE_RE.match(t):
        return True
    return any(k in t for k in AD_KEYWORDS)


def merge_same_row(boxes, tol=8):
    """把同一视觉行的多个 OCR 框横向拼成一行。

    OCR 会把一行里被空白隔开的文字拆成多个框（2023 卷第 15 页的
    「91.」和「淀粉酶是（）」就是这样），不合并就会漏题。
    """
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (b["y"], b["x"]))
    rows = []
    cur = [ordered[0]]
    cur_y = ordered[0]["y"]
    for b in ordered[1:]:
        if abs(b["y"] - cur_y) <= tol:
            cur.append(b)
            cur_y = (cur_y * (len(cur) - 1) + b["y"]) / len(cur)
        else:
            rows.append(cur)
            cur = [b]
            cur_y = b["y"]
    if cur:
        rows.append(cur)

    merged = []
    for row in rows:
        row = sorted(row, key=lambda b: b["x"])
        text = "".join(b["t"] for b in row)
        conf = min(b.get("c", 1.0) for b in row)
        merged.append({
            "x": row[0]["x"],
            "x2": max(b["x2"] for b in row),
            "y": row[0]["y"],
            "y2": max(b["y2"] for b in row),
            "t": text.strip(),
            "c": float(conf),
        })
    return merged


def _kmeans2(vals):
    """一维 2-means，返回两个簇的中心。"""
    if len(vals) < 2:
        return None
    lo, hi = min(vals), max(vals)
    for _ in range(30):
        mid = (lo + hi) / 2.0
        left = [v for v in vals if v < mid]
        right = [v for v in vals if v >= mid]
        if not left or not right:
            return None
        nlo = sum(left) / len(left)
        nhi = sum(right) / len(right)
        if abs(nlo - lo) < 0.5 and abs(nhi - hi) < 0.5:
            return nlo, nhi
        lo, hi = nlo, nhi
    return lo, hi


def _best_split(boxes, width, min_side=3, min_side_r=2):
    """找左右两栏之间的最佳分界位置（x 坐标）。

    做法：扫描所有可能的分界位置，取「横跨分界线的框最少」的那个。
    装订线那里一个框都不跨；而说明段、页眉水印这类通栏的长行
    必然跨过，会被算成跨栏框，所以要挑跨得最少的位置。

    之前用的是「找最宽的空白带」，会把页面右边的页边空白当成装订线；
    后来改成「按框中心聚类」，长行会把中心拉偏。分界位置直接按框的
    左右边界扫，跨栏框的数量一目了然，最稳。

    右栏的下限比左栏松（min_side_r=2）：整卷的最后几页右栏常常只剩
    一两行，这时候「右栏至少 3 框」会把分界线拉到右栏里面去，
    左栏的长行于是全被当成通栏丢掉（2020 试卷 p38 的 98~100 题就是这样
    没的：真装订线在 x=725，却判成了 x=512）。
    """
    edges = sorted(set([b["x"] for b in boxes] + [b["x2"] for b in boxes]))
    lo, hi = width * 0.08, width * 0.92
    cands = [e for e in edges if lo <= e <= hi]
    best = None
    for p in cands:
        nl = sum(1 for b in boxes if b["x2"] <= p)
        nr = sum(1 for b in boxes if b["x"] >= p)
        if nl < min_side or nr < min_side_r:
            continue
        ns = len(boxes) - nl - nr        # 横跨分界线的框
        if best is None or ns < best[0]:
            best = (ns, p)
            if ns == 0:
                break
    return best[1] if best else None


def detect_gutter(boxes, page_width=0, bucket=4):
    """找出左右两栏之间的「装订线」。

    返回 (g0, g1)：装订线左右边界；找不到说明这页是单栏，返回 None。
    """
    if len(boxes) < 8:
        return None
    width = page_width or max(b["x2"] for b in boxes)
    p = _best_split(boxes, width)
    if p is None:
        return None
    left = [b for b in boxes if b["x2"] <= p]
    right = [b for b in boxes if b["x"] >= p]
    if len(left) < 3 or len(right) < 2:
        return None
    return (p, p)


def column_split_boxes(boxes, page_width=0):
    """把原始 OCR 框分成左栏 / 通栏 / 右栏。

    判据是「装订线」：页面上左右两栏之间那条没有文字的竖缝。
    - 框完全在缝左边 -> 左栏
    - 框完全在缝右边 -> 右栏
    - 跨过缝的框 -> 看它是哪一栏的长行探进了缝（多半是），
      还是真的横跨整页（卷名标题、页眉水印）

    找不到缝就说明这页是单栏，原样返回。
    """
    if len(boxes) < 6:
        return list(boxes), [], []

    gutter = detect_gutter(boxes, page_width)
    if not gutter:
        return list(boxes), [], []
    p = gutter[0]

    left = [b for b in boxes if b["x2"] <= p]
    right = [b for b in boxes if b["x"] >= p]
    cross = [b for b in boxes if b["x"] < p < b["x2"]]
    if len(left) < 3 or len(right) < 2:
        return list(boxes), [], []

    centered = []
    # 右栏的行首位置：用分位数，别用最小值——页脚页码也归在右栏，
    # 它比正文靠左，会把右栏起点拉偏，左栏的长行就判成通栏丢掉了。
    rxs = sorted(b["x"] for b in right)
    right_start = rxs[len(rxs) // 4]
    left_end = max(b["x2"] for b in left)
    for b in cross:
        if b["x2"] <= right_start:
            left.append(b)          # 左栏的长行探进了装订线，不算通栏
        elif b["x"] >= left_end:
            right.append(b)         # 右栏的长行往左探
        else:
            centered.append(b)      # 真的横跨两栏（标题、水印）
    return left, centered, right


def group_lines(boxes, page_width=0, tol=8):
    """先分栏，再在栏内把同一视觉行的多个框拼成一行。

    返回的行带 col 字段：L=左栏，C=通栏，R=右栏。
    """
    groups = []
    for col, g in zip("LCR", column_split_boxes(boxes, page_width)):
        if not g:
            continue
        for row in merge_same_row(g, tol):
            row["col"] = col
            groups.append(row)
    return groups


def split_columns(lines):
    """按 x 起点把行分成左栏 / 居中块 / 右栏。

    栏位偏移每页都不一样（2010 卷第 8 页左栏 x=121，第 15 页 x=186，
    答案页左栏 x=273），所以阈值必须逐页算，不能写死。

    返回 (左栏行, 居中块行, 右栏行)。
    """
    xs = sorted(l["x"] for l in lines if l["t"])
    if len(xs) < 6:
        return list(lines), [], []

    # 一维 2-means：把 x 起点分成两簇
    lo, hi = xs[0], xs[-1]
    for _ in range(20):
        mid = (lo + hi) / 2.0
        left = [x for x in xs if x < mid]
        right = [x for x in xs if x >= mid]
        if not left or not right:
            break
        nlo, nhi = sum(left) / len(left), sum(right) / len(right)
        if abs(nlo - lo) < 0.5 and abs(nhi - hi) < 0.5:
            lo, hi = nlo, nhi
            break
        lo, hi = nlo, nhi
    boundary = (lo + hi) / 2.0

    left = [l for l in lines if l["x"] < boundary]
    right = [l for l in lines if l["x"] >= boundary]
    if not left or not right:
        return list(lines), [], []

    # 居中块：横跨在两栏之间（卷名标题常在这里），不算正文流
    lmin, lmax = min(l["x"] for l in left), max(l["x"] for l in left)
    rmin = min(l["x"] for l in right)
    span = rmin - lmin
    if span > 0:
        centered = [l for l in left if l["x"] > lmin + span * 0.2]
    else:
        centered = []
    if centered:
        cut = {id(c) for c in centered}
        left = [l for l in left if id(l) not in cut]
    return left, centered, right


# 卷名（按真题里的固定顺序）
PAPER_NAMES = ["基础知识", "相关专业知识", "专业知识", "专业实践能力"]

# 卷名关键词，长的排前面（"相关专业知识"里也含"专业知识"）
PAPER_NAME_RE = re.compile(r"(相关专业知识|专业实践能力|专业知识|基础知识)")

# 页中间的接缝（两个版面拼在一页上）阈值，单位是 200dpi 下的像素
SEAM_GAP = 110


def is_paper_title(text):
    """是不是卷名标题行。

    早年卷：``2010年检验师基础知识`` / ``2012师（基础知识）答案``
    近年卷：``基础知识（I）答案及解析`` / ``专业知识（Ⅲ）``
    """
    t = (text or "").strip()
    if not t or len(t) > 40:
        return False
    if not PAPER_NAME_RE.search(t):
        return False
    if re.match(r"^20\d\d", t):
        return True
    return bool(re.match(r"^[\s　]*(相关专业知识|专业实践能力|专业知识|基础知识)\s*[（(]", t))


def split_blocks_by_gap(lines, gap=SEAM_GAP):
    """把一栏的行按 y 切成若干块，块之间是大片空白。"""
    if not lines:
        return []
    lines = sorted(lines, key=lambda l: l["y"])
    blocks = [[lines[0]]]
    for prev, cur in zip(lines, lines[1:]):
        if cur["y"] - prev["y"] >= gap:
            blocks.append([])
        blocks[-1].append(cur)
    return blocks


def _merge_intervals(ivs):
    out = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1] + 40:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def column_major_order(lines):
    """按「左栏读完再右栏」的顺序排行。

    早年的真题册是"一张大纸上排两个小书页"，左边的竖条就是一本书的一页，
    从上到下读完这一竖条，再读右边那一竖条。这种版式下答案编号才是连续的
    （2011 答案第一页：左竖条 82~100、01~06，右竖条 07~14、15~18，
    连起来正好是 82~100 然后 01~18）。
    近年（2014 起）改成了正常的双栏页，页中间还有一条横接缝，
    那时就要用 build_reading_order 的"先上半页再下半页"。
    """
    Ls = sorted([l for l in lines if l.get("col") == "L"], key=lambda l: l["y"])
    Rs = sorted([l for l in lines if l.get("col") == "R"], key=lambda l: l["y"])
    return Ls + Rs


def tail_orders(lines, min_gap=200):
    """有些扫描页上下拼了两块版面：某一栏在页面中途就结束了，另一栏还在往下排。

    这种页的阅读顺序是「上半页（左栏+右栏）→ 下半页（左栏+右栏）」，
    跟普通双栏页的「左栏读完再右栏」不一样。

    2012 试卷第 28 页就是这种：右栏只到 y=461 就没了（83~86 题 + （87-88题）标记），
    左栏却一直排到 y=1910（87~100 题）。按普通顺序读，83~86 会跑到 100 后面去。

    返回 [(切分y, 行序)] 候选。
    """
    cols = {"L": [], "C": [], "R": []}
    for l in lines:
        cols.setdefault(l.get("col", "L"), []).append(l)
    out = []
    for c in ("L", "R"):
        if not cols[c]:
            continue
        others = [o for o in ("L", "R") if o != c and cols[o]]
        if not others:
            continue
        ymax_c = max(l["y"] for l in cols[c])
        ymax_o = max(max(l["y"] for l in cols[o]) for o in others)
        if ymax_c + min_gap >= ymax_o:
            continue              # 两栏差不多高，不是拼接页
        order = []
        for band in (0, 1):
            sel = [l for l in lines if (l["y"] <= ymax_c) == (band == 0)]
            for cc in ("L", "R"):
                order.extend(sorted([l for l in sel if l.get("col") == cc],
                                    key=lambda l: l["y"]))
        out.append((ymax_c, order))
    return out


def build_reading_order(lines, gap=SEAM_GAP):
    """把一页的行排成阅读顺序。

    绝大多数页就是「左栏读完再右栏」。但有的扫描页把上一卷的尾巴和下一卷的开头
    拼进了同一页（页中间横着一大片空白），这时必须先读完上半页（上一卷），
    再读下半页（下一卷），否则两卷的题目会交错在一起。

    接缝的判据：左右两栏在同一片区域都出现大空白（或者空白处正好是
    卷名标题/说明段），才算真的接缝。分界点按每栏自己的空白取中点，
    这样左右两栏的分界才不会差几十像素。
    """
    cols = {"L": [], "C": [], "R": []}
    for l in lines:
        cols.setdefault(l.get("col", "L"), []).append(l)
    for c in cols:
        cols[c].sort(key=lambda l: l["y"])
    if not cols["L"] and not cols["R"]:
        return list(cols["C"])

    # 每栏按大空白切成块，块之间的空白就是「接缝候选」
    blocks = {c: split_blocks_by_gap(cols[c], gap) for c in ("L", "R")}
    gaps = {c: [(b1[-1]["y"], b2[0]["y"])
                for b1, b2 in zip(blocks[c], blocks[c][1:])] for c in ("L", "R")}
    all_gaps = [g for c in ("L", "R") for g in gaps[c]]
    if not all_gaps:
        return cols["L"] + cols["R"]

    anchors = [l["y"] for l in cols["C"] + cols["L"] + cols["R"]
               if is_paper_title(l["t"]) or INSTRUCTION_MARK in (l["t"] or "")]

    seams = []
    for a, b in _merge_intervals(all_gaps):
        cnt = sum(1 for g in all_gaps if g[0] <= b and g[1] >= a)
        has_anchor = any(a - 80 <= y <= b + 80 for y in anchors)
        if cnt >= 2 or has_anchor:
            seams.append((a, b))
    if not seams:
        return cols["L"] + cols["R"]

    # 每栏在每条接缝处的分界点：优先用本栏自己的空白中点
    cuts = {"L": [], "R": []}
    for a, b in seams:
        for c in ("L", "R"):
            own = [g for g in gaps[c] if g[0] <= b and g[1] >= a]
            if own:
                cuts[c].append((own[0][0] + own[0][1]) / 2.0)
            else:
                cuts[c].append((a + b) / 2.0)
    cuts["L"].sort()
    cuts["R"].sort()

    def seg_of(line, c):
        return sum(1 for y in cuts[c] if line["y"] >= y)

    out = []
    for k in range(len(seams) + 1):
        out.extend([l for l in cols["L"] if seg_of(l, "L") == k])
        out.extend([l for l in cols["R"] if seg_of(l, "R") == k])
    return out


def is_instruction(text):
    t = (text or "").strip()
    return (INSTRUCTION_MARK in t or SHARED_INSTRUCTION_MARK in t
            or SHARED_INSTRUCTION_MARK2 in t)


def is_shared_instruction(text):
    """题型二 / 题型三的说明段——进入配伍模式，之前的共享选项作废。"""
    t = (text or "").strip()
    return SHARED_INSTRUCTION_MARK in t or SHARED_INSTRUCTION_MARK2 in t


def split_double_question_lines(lines):
    """一行里挤了两道题的题号。

    "99.酸中毒时,将导致(100.碱中毒时,将导致(" —— 2014 专业实践能力
    最后一页就是这样，第 99、100 两道题印在同一行上。拆成两行，
    后面的解析逻辑一行都不用改。

    只在「第一个题号后面紧跟着第二个题号（正好 +1）、且前一段以空括号
    收尾」时才拆：每道题的题干都以"（"结尾，所以前一段必然以它收尾。
    这样"50.剂量1.5mg"、"12.答案见13.4节" 之类都不会被误拆。
    """
    out = []
    for ln in lines:
        t = (ln.get("t") or "").strip()
        m = QNUM_RE.match(t)
        if m:
            num = int(m.group(1))
            rest = m.group(2)
            m2 = re.search(r"(?<![0-9])(\d{1,3})\s*[.、．]\s*(?![0-9])", rest)
            if m2 and int(m2.group(1)) == num + 1:
                head = rest[:m2.start()].strip()
                tail = rest[m2.end():].strip()
                if head and tail and head[-1] in "（(":
                    a = dict(ln)
                    a["t"] = "%d.%s" % (num, head)
                    b = dict(ln)
                    b["t"] = "%d.%s" % (num + 1, tail)
                    out.append(a)
                    out.append(b)
                    continue
        out.append(ln)
    return out


def split_option_line(text):
    """一行里可能挤了好几个选项（OCR 常见，比如 "A. C1B.C2C.C3D. C4E. C5"）。

    只认 "A -> B -> C -> D -> E" 这种字母递增的切法，避免把选项内容里的
    字母当成分隔符。返回 [(字母, 内容)]。
    """
    t = (text or "").strip()
    if not t:
        return []
    marks = [(m.start(), m.group(1).upper(), m.end()) for m in OPT_MARK_RE.finditer(t)]
    if not marks:
        return []
    if len(marks) == 1 or marks[0][0] != 0 or marks[0][1] != "A":
        m = marks[0]
        return [(m[1], t[m[2]:].strip())]
    order = "ABCDE"
    chosen = [marks[0]]
    want = 1
    for m in marks[1:]:
        if want < len(order) and m[1] == order[want]:
            chosen.append(m)
            want += 1
    if len(chosen) < 2:
        m = marks[0]
        return [(m[1], t[m[2]:].strip())]
    out = []
    for i, (_pos, key, end) in enumerate(chosen):
        stop = chosen[i + 1][0] if i + 1 < len(chosen) else len(t)
        out.append((key, t[end:stop].strip()))
    return out


def repair_truncated_num(num, prev_num):
    """题号掉了十位（扫描件把「36」印成了「6」）。

    同一份卷子里题号是递增的，出现「上一题 35、这道题 6」这种倒退，
    只可能是十位被切掉了。按上一题的十位补回去。

    补出来的号必须正好是「上一题 + 1」才算数：上一题 62、这一题印成「9」，
    按十位补回去是 69，但卷子里第 63 题才是紧接的，所以「9」多半是正文里的
    数字（2015 专业实践能力：「…血液分析仪显.09，H示血小板极度减低…」），
    不能当成题号。
    """
    if prev_num is None or num is None:
        return num
    if not (1 <= num <= 9) or prev_num < 10 or prev_num >= 100:
        return num
    if num >= prev_num:
        return num
    fixed = (prev_num // 10) * 10 + num
    if fixed != prev_num + 1:
        return num          # 补出来不是紧接着的下一号，不猜
    return fixed


def split_embedded_question(text, prev_num=None):
    """选项行里混进了下一道题的题号：「E.A+C.34.最大的沉淀反应发生在」。

    返回 (选项部分, 题号, 题干)，没有题号时返回 (text, None, None)。

    只有两种情况才算「粘了下一题的题号」：
    1. 题号正好是上一题的下一号（34 紧跟在 33 后面）；
    2. 题号前面刚写完一个选项字母（「E.」+「34.」）——说明确实是选项行接题号。
    否则像「齿20.畏」这种数字出现在题干中间的情况不能拆，
    否则会凭空造出一道第 20 题。
    """
    t = (text or "").strip()
    if not t:
        return t, None, None
    # 本行出现的所有选项字母（位置）
    letters = [m.start() for m in re.finditer(r"[A-Ea-e]\s*[.．]", t)]
    best = None
    for m in re.finditer(r"(?<![0-9A-Za-z])(\d{2,3})\s*[.、．]\s*([\u4e00-\u9fffA-Za-z])", t):
        num = int(m.group(1))
        if not (10 <= num <= 200):
            continue
        # 数字前面是不是紧挨着一个选项字母？
        mm = re.search(r"([A-Ea-e])\s*[.．]\s*$", t[:m.start()])
        if mm is not None and len(letters) == 1 and letters[0] == mm.start(1):
            # 这个选项字母是本行唯一的选项字母：数字多半是**选项内容**
            # （"D. 46. XY, i(17q)" 里的 46），不是题号。
            continue
        if prev_num is not None and num == prev_num + 1:
            best = m
            break
        if best is None and mm is not None:
            # 刚写完一个选项字母，后面紧跟题号
            best = m
    if best is None:
        return t, None, None
    return t[:best.start()].strip(), int(best.group(1)), t[best.end():].strip()


def parse_questions(lines, paper_name="", year=None):
    """把一个卷的正文行解析成题目列表。

    lines 必须是按阅读顺序排好的行（先左栏后右栏，跨页拼接）。
    """
    lines = split_double_question_lines(lines)
    questions = []
    cur = None
    shared_opts = {}      # 当前配伍组的备选答案（可以出现在题目前面）
    shared_span = None    # 组内题数跨度（从 "(83-86题)" 标记里读出来）
    shared_first = None   # 这一组第一道题的题号
    shared_mode = False   # 是否处于配伍题区
    pending_year = year
    last_num = None       # 上一道题的题号（用来判断题号是否缺了十位）
    pending_stem = ""     # 题号行前面那一行的文字（见下面的说明）
    seen = set()          # 已经出过的题号（用来判断题号是不是往回跳）
    last_opt_key = None   # 上一行是选项行时，那个选项的字母
    # 共用题干组（"（93～94题共用题干）"）：一段病例 + 若干道题，
    # 病例是共用的，选项不共用。lo/hi 是组里的题号范围，
    # next 是组内下一道题该有的题号，case 是那段病例的文字。
    stem_group = None

    def flush():
        nonlocal cur
        if cur is not None:
            questions.append(cur)
        cur = None

    def reset_group():
        nonlocal shared_opts, shared_span, shared_first
        shared_opts = {}
        shared_span = None
        shared_first = None

    def seq_ok(num):
        """题号必须正好接上一题，否则多半是正文里的数字。"""
        return ((last_num is not None and num == last_num + 1)
                or (last_num is None and num == 1))

    # 预计算：每一行后面最近的一个「行首题号」是多少。
    # 用来判断某个跳号是真的漏了一道题，还是正文里的数字。
    lead = []
    for ln in lines:
        t = (ln.get("t") or "").strip()
        m = QNUM_RE.match(t) if t else None
        lead.append(int(m.group(1)) if m else None)
    next_lead = [None] * len(lead)
    nxt = None
    for i in range(len(lead) - 1, -1, -1):
        next_lead[i] = nxt
        if lead[i] is not None:
            nxt = lead[i]

    # 预计算：每一行「往后第一个有结构的行」是选项行还是题号行。
    # 选项文字换行时，续行要接回上一个选项；「题干排在题号前面」时，
    # 续行要留给下一题。两种续行长得一样，只能靠后面跟的是选项还是题号来分。
    nxt_kind = [None] * len(lines)
    nxt_opt_key = [None] * len(lines)
    kind = key = None
    for i in range(len(lines) - 1, -1, -1):
        nxt_kind[i] = kind
        nxt_opt_key[i] = key
        t2 = (lines[i].get("t") or "").strip()
        if not t2:
            continue
        pairs_i = split_option_line(t2)
        if pairs_i:
            kind = "opt"
            key = pairs_i[0][0].upper()
        elif QNUM_RE.match(t2):
            kind = "num"
            key = None
        # 普通行不改变 kind：往后找的是「下一个有结构的行」

    for li, ln in enumerate(lines):
        text = (ln.get("t") or "").strip()
        if not text:
            continue

        # 卷名标题（单独一行）
        if BARE_PAPER_RE.match(text):
            continue

        # 年份标题行（试卷侧「2012年检验（师）」）。
        # 必须整行就是标题：以年份开头、够短、不带标点——
        # 否则题干里出现「1976年…」这种会被当成年份，整卷的年份就错了。
        if YEAR_TITLE_RE.match(text) and len(text) <= 20 and not any(
                ch in text for ch in "，。；,.;:"):
            pending_year = int(YEAR_TITLE_RE.match(text).group(1))
            continue

        # 说明段
        if is_instruction(text):
            flush()
            if is_shared_instruction(text):
                shared_mode = True
                reset_group()
            else:
                shared_mode = False
                reset_group()
            continue

        # 共用题干组标记：（93～94题共用题干）
        # 要放在配伍题标记前面判：「共用题干」的选项不共用，
        # 跟「共用备选答案」是两种不同的题型。
        sm = GROUP_STEM_MARK_RE.search(text)
        if sm:
            flush()
            shared_mode = False
            reset_group()
            lo = int(sm.group(1))
            hi = int(sm.group(2))
            stem_group = {"lo": lo, "hi": max(lo, hi), "next": lo, "case": []}
            pending_stem = ""
            continue

        # 配伍题组标记：（83-86题）/（83-86题共用备选答案）
        gm = GROUP_MARK_RE.search(text)
        gm2 = gm3 = gm4 = gm5 = None
        span = None
        if gm:
            span = int(gm.group(2)) - int(gm.group(1))
        else:
            gm2 = GROUP_MARK_RE2.search(text)
            if gm2:
                span = int(gm2.group(2)) - int(gm2.group(1))
            else:
                gm3 = GROUP_MARK_RE3.search(text)
                if gm3:
                    span = int(gm3.group(2)) - int(gm3.group(1))
                else:
                    gm4 = GROUP_MARK_LOOSE_RE.match(text)
                    if gm4:
                        span = int(gm4.group(2)) - int(gm4.group(1))
                    else:
                        gm5 = GROUP_MARK_LOOSE_RE2.match(text)
                        if gm5:
                            span = int(gm5.group(2)) - int(gm5.group(1))
        if gm or gm2 or gm3 or gm4 or gm5:
            flush()
            shared_mode = True
            reset_group()
            shared_span = span if (span is not None and span >= 0) else None
            continue

        # 选项行（可能一行里挤了好几个选项）
        # 也可能一行尾部粘着下一题的题号：「E.A+C.34.最大的沉淀反应发生在」
        opt_text, emb_num, emb_stem = split_embedded_question(text, last_num)
        pairs = split_option_line(opt_text)
        if pairs:
            for key, val in pairs:
                if not val:
                    continue
                if cur is None:
                    # 题干还没出现：这是配伍题的备选答案，先存着
                    if not shared_mode:
                        continue
                    if shared_opts.get(key):
                        # 又出现一个 A：说明开始了一组新的备选答案
                        reset_group()
                    shared_opts[key] = val
                    continue
                if key in cur["options"] and len(cur["options"]) >= 4:
                    # 这道题的选项已经凑齐 4 个以上，后来的同字母行属于下一题
                    # （常见于试卷里的表格题：题干被 OCR 吞了，选项行直接跟上来）
                    continue
                cur["options"][key] = val
                if shared_mode:
                    shared_opts[key] = val
                last_opt_key = key
                cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
            if emb_num is not None:
                # 这一行后半段是新题目的题号
                flush()
                last_num = emb_num
                seen.add(emb_num)
                cur = {
                    "num": emb_num,
                    "stem": emb_stem,
                    "options": {},
                    "answer": "",
                    "analysis": "",
                    "conf": float(ln.get("c", 1.0)),
                    "shared": False,
                    "year": pending_year,
                }
                last_opt_key = None
                if shared_mode and shared_opts:
                    if shared_first is None:
                        shared_first = emb_num
                    if shared_span is None or emb_num <= shared_first + shared_span:
                        cur["options"] = dict(shared_opts)
                        cur["shared"] = True
            continue

        # 题号行
        qm = QNUM_RE.match(text)
        if qm:
            raw_num = int(qm.group(1))
            stem = qm.group(2).strip()
        else:
            # 题号前面粘了相邻栏的杂字（"胖 56.属于…"、"M2.不是网织…"）
            # 或粘了页码数字（"0873.患者…"其实是 73）。
            # 只有在题号正好接上一题时才认，否则 "1.5mm" 之类会被误当成题号。
            raw_num = stem = None

            # 行首连着数字："0873.患者…"其实是第 73 题（前面粘了页码）
            mp = NUM_PREFIX_RE.match(text)
            if mp:
                digits = mp.group("digits")
                cand = int(digits) if len(digits) <= 3 else int(digits[-2:])
                if cand > 100:
                    cand = cand % 100
                if 1 <= cand <= 100 and seq_ok(cand):
                    raw_num = cand
                    stem = mp.group("rest").strip()

            # 题号后面印的是句号："79。患者男，36岁…"
            md = CJK_DOT_QNUM_RE.match(text)
            if raw_num is None and md:
                cand = int(md.group("num"))
                if cand > 100:
                    cand = cand % 100
                if 1 <= cand <= 100 and seq_ok(cand):
                    raw_num = cand
                    stem = md.group("rest").strip()

            for m in (PUNCT_QNUM_RE.match(text), NOISY_QNUM_RE.match(text),
                      NODOT_QNUM_RE.match(text)):
                if raw_num is not None or not m:
                    continue
                cand = int(m.group("num"))
                junk = m.group("junk")
                # 杂字里不能有标点（那多半是上一句的尾巴），长度也不该太长
                if m.re is PUNCT_QNUM_RE:
                    # 纯标点杂字，长度不能太大
                    ok = len(junk.strip()) <= 3
                elif m.re is NODOT_QNUM_RE:
                    # 无点号的题号：杂字里不能有标点，否则多半是选项或正文
                    ok = (len(junk.strip()) <= 4
                          and not any(ch in junk for ch in "，。；：、,;:.。"))
                    # 上一道题的选项必须已经收齐，否则这行多半是上一题的题干
                    # 续行，而不是新题的开头。
                    # （2018 专业知识第 7 题：左栏「7.荧光显微镜观察的注意事项中，
                    #   下列哪项」右栏接着「8是错误的）用同共」——行首那个「8」
                    #   是叠加在页边上的水印噪声，被当成第 8 题的题号，把第 7 题
                    #   的题干续行抢走了。）
                    if cur is not None and len(cur.get("options") or {}) < 2:
                        ok = False
                else:
                    # 杂字最多 3 个，可以带一个逗号（"死,79."、"，湘53."），
                    # 括号无所谓（"（）最25.自身免疫性疾病…"），
                    # 但不能带句号/冒号之类（那多半是上一句的尾巴）
                    js = junk.strip()
                    commas = sum(js.count(ch) for ch in ",，、")
                    ok = (len(js) <= 3
                          and commas <= 1
                          and not any(ch in js for ch in "。；：:！？"))
                if cand > 100:
                    # 三位数多半是把页码粘上来了："共664.患者…"其实是第 64 题
                    cand = cand % 100
                if ok and 1 <= cand <= 100 and seq_ok(cand):
                    raw_num = cand
                    stem = m.group("rest").strip()
                    break
        # 跳号的「假题号」：正文里的数字被当成了题号。
        # 2016 专业实践能力第 15 题后面混进一行「100.0」（图表里的读数），
        # 被当成第 100 题；后面的 16~99 题于是全成了「往回跳」，
        # 一路当成上一题的续行吞掉，整卷只剩 15 题。
        # 2022 相关专业知识第 9 题里的「12.6×10°/L」同理。
        #
        # 怎么区分「真的漏了一道题」和「正文里的数字」？看下一个题号：
        # 真的漏题时，后面的题号接着往下走（比跳过去的号大）；
        # 假的题号后面，跟着的才是真正的下一题（比它小）。
        if (raw_num is not None and stem and last_num is not None
                and 1 <= raw_num <= 100
                and raw_num > last_num + 1
                and next_lead[li] is not None
                and next_lead[li] <= raw_num):
            # 假的题号：这行是上一道题的续行
            if cur is not None and CJK_RE.search(stem):
                cur["stem"] = (cur["stem"] + text).strip()
                cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
            continue

        # 共用题干组内：题号必须落在组里的连号区间上。
        # OCR 把「93」认成「92」时（2020 专业实践能力 93、94 那组），
        # 用组内顺序把它纠正回来；认得离谱（不在区间附近）就当组结束。
        if raw_num is not None and stem_group is not None:
            lo, hi = stem_group["lo"], stem_group["hi"]
            if lo <= raw_num <= hi:
                pass                       # 认对了，按原样用
            elif lo - 1 <= raw_num <= hi:
                raw_num = stem_group["next"]   # 差一号，按组内顺序纠正
            else:
                stem_group = None
        if raw_num is not None:
            # 题号往回跳（题号不该递减），多半是「1.5mm」这种续行或十位被切掉
            out_seq = last_num is not None and raw_num <= last_num
            if out_seq and stem[:1].isdigit():
                # 「1.5mm，菌落周围…」：数字开头的续行，不是新题
                if cur is not None:
                    cur["stem"] = (cur["stem"] + text).strip()
                    cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
                continue
            if out_seq and raw_num <= 9 and last_num >= 10:
                # 题号掉了十位："36"被印成"6"，按上一题的十位补回去
                # （2012 专业实践能力 36：卷面上印的是「6.血清学试验的后带…」）
                fixed = repair_truncated_num(raw_num, last_num)
                if fixed != raw_num and fixed not in seen:
                    raw_num = fixed
                    out_seq = False
            if out_seq and raw_num == last_num:
                # 同一道题在扫描件上印了两遍（页有重叠），跳过
                continue
            if (out_seq and raw_num in seen and cur is not None
                    and len(cur.get("options") or {}) >= 4
                    and nxt_kind[li] == "opt" and stem
                    and last_num is not None and last_num < 100):
                # 题号往回跳、而且这个号**已经用过了**：这不是上一题的续行，
                # 是一道新题，题号被 OCR 认错了。
                # 2023 基础知识第 34 题：卷面印的是「34」，200dpi 下「4」的
                # 斜笔太淡，被认成了「1」——整行读成「31.丝虫病的传播媒介是」。
                # 而 31 早被真正的第 31 题用掉了；上一题（33）的选项已经齐了，
                # 下一行又是选项行——正好是一道新题该有的样子。
                # 正确的题号就是上一题的下一号。
                num = last_num + 1
                flush()
                last_num = num
                seen.add(num)
                cur = {
                    "num": num,
                    "stem": stem,
                    "options": {},
                    "answer": "",
                    "analysis": "",
                    "conf": float(ln.get("c", 1.0)),
                    "shared": False,
                    "year": pending_year,
                }
                last_opt_key = None
                if shared_mode and shared_opts:
                    if shared_first is None:
                        shared_first = num
                    if shared_span is None or num <= shared_first + shared_span:
                        cur["options"] = dict(shared_opts)
                        cur["shared"] = True
                continue
            if out_seq:
                # 题号往回跳、而且补不回「上一题 + 1」：这个数字一定是正文里的
                # （「血细胞比容(Hct)0.」+「65,WBC22…」、
                #  「…血液分析仪显.09，H示血小板极度减低…」），
                # 当成上一题的续行。题号必须是递增的，往回跳的绝不会是新题。
                if cur is not None:
                    cur["stem"] = (cur["stem"] + text).strip()
                    cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
                continue
            if raw_num > 100:
                # 题号前面粘进了页码/杂字符："134.下列不符合…"其实是第 34 题。
                # 每卷只有 100 题，所以三位数一定是错的；去掉百位后正好接上
                # 上一题才认（134 -> 34），认不准就当正文。
                cand = raw_num % 100
                if 1 <= cand <= 100 and seq_ok(cand):
                    raw_num = cand
                else:
                    if cur is not None:
                        cur["stem"] = (cur["stem"] + text).strip()
                        cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
                    continue
            if 1 <= raw_num <= 100:
                flush()
                num = repair_truncated_num(raw_num, last_num)
                last_num = num
                seen.add(num)
                if not stem:
                    stem = pending_stem
                pending_stem = ""
                cur = {
                    "num": num,
                    "stem": stem,
                    "options": {},
                    "answer": "",
                    "analysis": "",
                    "conf": float(ln.get("c", 1.0)),
                    "shared": False,
                    "year": pending_year,
                }
                last_opt_key = None
                if shared_mode and shared_opts:
                    if shared_first is None:
                        shared_first = num
                    if shared_span is None or num <= shared_first + shared_span:
                        cur["options"] = dict(shared_opts)
                        cur["shared"] = True
                if stem_group is not None:
                    # 共用题干：把那段病例拼到每道题的题干前面
                    if stem_group["case"]:
                        cur["stem"] = ("\n".join(stem_group["case"])
                                       + "\n" + cur["stem"]).strip()
                    stem_group["next"] = max(stem_group["next"], num + 1)
                    if stem_group["next"] > stem_group["hi"]:
                        stem_group = None
            continue

        # 普通行：要么是题干的续行，要么是选项的续行
        if cur is not None:
            if (last_opt_key and cur["options"].get(last_opt_key)
                    and not cur.get("shared")
                    and nxt_kind[li] == "opt"
                    and nxt_opt_key[li] not in cur["options"]):
                # 选项的文字换行了，续行接回上一个选项，
                # 别塞进题干里（2022 基础知识 50：A 选项的尾巴被当成题干）。
                cur["options"][last_opt_key] = (
                    cur["options"][last_opt_key] + text).strip()
                cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
                continue
            if len(cur["options"]) >= 2 and not cur.get("shared"):
                # 上一道题的选项已经齐了，这一行多半是「下一题的题干」。
                # OCR 常把「53.」和题干拆成两行，题干反而排在了题号前面
                # （2023 试卷第 12 页：y=1526 是题干，y=1543 才是「53.」）。
                # 这种情况题干会空掉，整道题被丢掉。
                pending_stem = text
            else:
                cur["stem"] = (cur["stem"] + text).strip()
                cur["conf"] = min(cur["conf"], float(ln.get("c", 1.0)))
            continue
        if stem_group is not None:
            # 还没有题目，说明这几行是共用题干的那段病例
            stem_group["case"].append(text)
            continue
        pending_stem = text

    flush()

    out = []
    for q in questions:
        if len(q["options"]) >= 2 and q["stem"]:
            out.append(q)
    for q in out:
        q["paper_name"] = paper_name
        q["year"] = q.get("year") or pending_year
        if q["shared"]:
            q["stem"] = (q["stem"] + "（本组题共用备选答案）").strip()
        # 试卷页上印的“扫码查看商品详情”之类广告残骸
        q["stem"] = strip_ad(q["stem"])
        for k, v in list((q.get("options") or {}).items()):
            q["options"][k] = strip_ad(v)
    return out


def parse_answer_line(text):
    """识别一行里的答案，返回 [(题号, 答案字母, 行尾文本)]。

    早年卷：87.参考答案：B解析：xxx
    近年卷：12.答案:E / 31.答案:D / 39、答案:E
    还有一种把好几道题挤在一行的写法：53.B54.D55.D56.A
    """
    t = (text or "").strip()
    if not t:
        return []

    m = ANS_RE.match(t) or ANS_RE_LOOSE.match(t)
    if m:
        return [(int(m.group(1)), m.group(2).upper(), (m.group(3) or "").strip())]

    m = ANS_RE2.match(t)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 200:
            return [(num, m.group(2).upper(), (m.group(3) or "").strip())]

    m = NOISY_ANS_RE.match(t)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 200:
            return [(num, m.group(3).upper(), (t[m.end():] or "").strip())]

    out = []
    pos = 0
    while True:
        m2 = ANS_PAIR_RE.match(t, pos) or ANS_PAIR_NOSEP_RE.match(t, pos)
        if not m2:
            break
        num = int(m2.group(1))
        if not (1 <= num <= 200):     # 太离谱的题号当噪音
            break
        out.append((num, m2.group(2).upper(), ""))
        pos = m2.end()
    if not out:
        return []
    tail = t[pos:].strip()
    if tail:
        om = ORPHAN_NUM_RE.match(tail)
        if om:
            # 行尾只剩一个题号（答案字母没认出来），别把它当解析粘到上一题
            out.append((int(om.group(1)), "", ""))
        else:
            out[-1] = (out[-1][0], out[-1][1], tail)
    return out


def repair_answer_stream(entries):
    """修掉答案流里「跳过头又折回来」的那几条。

    答案册按题号递增排，所以答案条目的题号必须一路递增。
    扫描件里偶尔混进别的卷的答案：2020 专业实践能力那一段，
    第 20 页右栏开头印着另一卷的「99.答案：B」「100B拍」，
    紧接着又是本卷的 7、8、9……；本卷真正的 99、100（在第 26 页）
    于是被当成重复号丢掉，答案就错了。

    修法：题号回退时
      - 这个号前面已经出现过 → 多出来的这条是重复，丢掉；
      - 否则说明前面跳过头了，把跳过去的那几条丢掉。
    """
    kept = []
    for e in entries:
        n = e["num"]
        if not kept or n > kept[-1]["num"]:
            kept.append(e)
            continue
        if any(k["num"] == n for k in kept):
            continue                    # 重复号：这条是印重/误识的，丢掉
        # 前面跳过头了（99、100 抢在 7 前面），把跳过去的那几条丢掉
        kept = [k for k in kept if k["num"] <= n]
        kept.append(e)
    return kept


def parse_answers(lines):
    """解析答案段，返回 (答案字典, 题号顺序)。

    答案格式：「NN.参考答案：X解析：…」，解析正文跨行直到下一条答案。
    """
    entries = []          # 按出现顺序记下来的答案条目：{"num","answer","analysis"}
    cur_num = None
    cur_ans = ""
    cur_analysis = []
    in_analysis = False
    prev_num = None       # 上一条答案的题号（用来判断题号是否缺了十位）
    events = []           # 按出现顺序记下来的答案事件，用来给「没题号的答案」补题号

    def flush():
        nonlocal cur_num, cur_ans, cur_analysis, in_analysis
        if cur_num is not None:
            entries.append({
                "num": cur_num,
                "answer": cur_ans,
                # 拼起来之后再裁一次广告：广告词常被断在两行之间
                # （上一行末尾「微」+ 下一行开头「信搜索：…」）
                "analysis": strip_ad("".join(cur_analysis).strip()),
            })
        cur_num, cur_ans, cur_analysis, in_analysis = None, "", [], False

    texts = [(ln.get("t") or "").strip() for ln in lines]

    def next_text(idx):
        """往后找第一个非空行。"""
        for k in range(idx, len(texts)):
            if texts[k]:
                return texts[k]
        return ""

    for li, ln in enumerate(lines):
        text = texts[li]
        if not text:
            continue
        pairs = parse_answer_line(text)
        if not pairs:
            # 题号被整个 OCR 吃掉了，只剩「答案：X」。
            # 答案册是按题号顺序排的，等看到下一个有题号的答案时，
            # 就知道这个空缺是哪个题号了。
            mb = ANS_BARE_RE.match(text)
            if mb and len(text) <= 40:
                flush()
                events.append(("bare", mb.group(1).upper(),
                                (mb.group(2) or "").strip()))
                continue
        if pairs:
            for num, ans, tail in pairs:
                flush()
                cur_num = repair_truncated_num(num, prev_num)
                num = cur_num
                prev_num = num
                cur_ans = ans
                events.append(("num", num, ans))
                cur_analysis = []
                # 解析正文往往写在答案行的下一行、下下行（“1. c”
                # 后面跟着整段“解析：…”），答案行本身有没有尾巴都不应该影响它。
                in_analysis = True
                if tail:
                    am = ANALYSIS_RE.search(tail)
                    if am:
                        in_analysis = True
                        cur_analysis.append(tail[am.end():])
                    else:
                        # 答案行尾巴上可能挂着水印残骸，剔掉；
                        # 另外，如果下一行是「解析：」，说明这截尾巴
                        # 不是正文（真正的解析在下一行），整截丢掉。
                        keep = "" if next_text(li + 1).startswith("解析") \
                            else strip_watermark(tail)
                        in_analysis = True
                        if keep:
                            cur_analysis.append(keep)
            continue
        if cur_num is None:
            continue
        # 答案标题行「2010年检验师基础知识 / 答案和解析」跳过
        if TITLE_RE.search(text) and len(text) < 40:
            continue
        if is_instruction(text):
            continue
        if in_analysis:
            text = strip_watermark(text)
            if not text:
                continue
            # 「解析：」这个引导词只出现一次，出现在答案行或解析的第一行，
            # 存进字段时去掉，免得解析正文前面挂个"解析："。
            am = ANALYSIS_RE.match(text)
            cur_analysis.append(text[am.end():] if am else text)
    flush()

    # 同号重复：答案册里同一个题号连着出现两次，通常是前一个题的题号被印错/读错，
    # 而那个题号在整卷里恰好是缺的。例如 2012 相关专业知识：…89, 91, 91, 92…
    #   —— 前面那个「91」其实是「90」。
    # 这种情况下把「第一次出现的那个重复号」改成 缺的那个号（num-1）。
    nums_seen = {e["num"] for e in entries}
    for i in range(1, len(entries)):
        n = entries[i]["num"]
        if n != entries[i - 1]["num"]:
            continue
        prev = entries[i - 1]["num"]
        if (n - 1) >= 1 and (n - 1) not in nums_seen:
            entries[i - 1]["num"] = n - 1
            nums_seen.add(n - 1)

    entries = repair_answer_stream(entries)

    answers = {}
    order = []
    for e in entries:
        if e["num"] in answers:
            # 仍然重复（题号本身没错，册子里印重了）：保留先出现的那条
            continue
        answers[e["num"]] = {"answer": e["answer"], "analysis": e["analysis"]}
        order.append(e["num"])

    # 把「没有题号的答案」填进题号的空缺里。
    #
    # 答案册的题号是 1..N 连续的。OCR 认不出题号时只留下「答案：X」，
    # 这一行的位置就是它所属题号的位置。所以先把所有「已知题号」列出来，
    # 找出其中的空缺，再把裸答案按出现顺序填进这些空缺。
    known = [n for n in answers if answers[n]["answer"]]
    if not known:
        return answers, order
    gaps = [n for n in range(min(known), max(known) + 1)
            if n not in answers or not answers[n]["answer"]]
    bare_list = [ev for ev in events if ev[0] == "bare"]
    for ev, gap in zip(bare_list, gaps):
        ans, tail = ev[1], ev[2]
        answers[gap] = {"answer": ans, "analysis": tail}
        order.append(gap)

    return answers, order


def detect_paper_starts(lines):
    """在一条阅读流里找出"新卷开始"的位置。

    主锚点：说明段「以下每一道…」之后的第一道题题号归 1。
    返回 [(说明段行下标, 题号行下标)]。
    """
    starts = []
    for i, ln in enumerate(lines):
        text = (ln.get("t") or "").strip()
        if INSTRUCTION_MARK not in text:
            continue
        for j in range(i + 1, min(i + 10, len(lines))):
            t2 = (lines[j].get("t") or "").strip()
            if TITLE_RE.search(t2) and len(t2) < 40:
                continue
            qm = QNUM_RE.match(t2)
            if qm:
                if int(qm.group(1)) == 1:
                    starts.append((i, j))
                break
    return starts


def align_by_order(qnums, anums):
    """题号对不齐时，按出现顺序对齐（先精确配对，剩下按序配）。"""
    qset, aset = set(qnums), set(anums)
    pairs = [(q, q) for q in qnums if q in aset]
    used_q = {q for q, _ in pairs}
    used_a = {a for _, a in pairs}
    rest_q = [q for q in qnums if q not in used_q]
    rest_a = [a for a in anums if a not in used_a]
    for q, a in zip(rest_q, rest_a):
        pairs.append((q, a))
    return pairs
