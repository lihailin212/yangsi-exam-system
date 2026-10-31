"""随机卷：每位考生题数相同、题目随机。

管理员在创建考试时用"抽题规则"规定每个亚类别/题型各抽多少道，
保存考试后，每个考生进入考试时按同一份规则从题库里随机抽题，
落库到 exam_papers 表，保证同一个人刷新页面题目不变，
不同的人题目不同（防止互相抄答案）。
"""
import json
import random

from sqlalchemy.orm import Session

from . import models

# 题库里的亚类别短名 -> 实际分类名。
# "其他体液"在题库里拆成了两处：正经的"其他体液形态学"和历史遗留的"其他形态学"。
SUB_CATEGORY_ALIASES = {
    "血细胞": ["形态学/血细胞形态学"],
    "尿沉渣": ["形态学/尿沉渣形态学"],
    "寄生虫": ["形态学/寄生虫形态学"],
    "其他体液": ["形态学/其他体液形态学", "形态学/其他形态学"],
    "其他": ["形态学/其他形态学"],
}

TYPE_ALIASES = {
    "single": "single", "单选": "single", "单选题": "single",
    "multiple": "multiple", "多选": "multiple", "多选题": "multiple",
    "judgment": "judgment", "判断": "judgment", "判断题": "judgment",
    "fill": "fill", "填空": "fill", "填空题": "fill",
}

TYPE_LABELS = {
    "single": "单选题", "multiple": "多选题",
    "judgment": "判断题", "fill": "填空题",
}


class RuleError(Exception):
    """抽题规则不合法或题库不够。"""


def normalize_type(value):
    if not value:
        return None
    return TYPE_ALIASES.get(str(value).strip())


def parse_rules(raw):
    """把存库的规则 JSON 解析成 [{categories, type, count}]。"""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if not isinstance(raw, list):
        return []
    rules = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            count = int(item.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        cats = item.get("categories")
        rules.append({
            # category 要留着：categories 为空时靠它回查题库里的真实分类
            "category": (item.get("category") or "").strip(),
            "categories": cats if isinstance(cats, list) else None,
            "type": normalize_type(item.get("type")),
            "count": count,
            "label": item.get("label") or "",
        })
    return rules


def rules_to_json(rules):
    """把前端的规则数组存成 JSON 文本。"""
    out = []
    for item in rules or []:
        if not isinstance(item, dict):
            continue
        try:
            count = int(item.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        category = (item.get("category") or "").strip()
        cats = item.get("categories")
        out.append({
            "category": category,
            "categories": cats if isinstance(cats, list) else None,
            "type": normalize_type(item.get("type")),
            "count": count,
        })
    return json.dumps(out, ensure_ascii=False)


def resolve_categories(db: Session, category: str):
    """把规则里写的分类名解析成题库里真实存在的分类列表。

    支持三种写法：短名（血细胞）、完整分类名（形态学/血细胞形态学）、
    关键字（形态学 表示所有形态学子类）。
    """
    if not category:
        return None
    category = category.strip()
    names = [row[0] for row in db.query(models.Question.category).distinct().all() if row[0]]
    if category in SUB_CATEGORY_ALIASES:
        cats = SUB_CATEGORY_ALIASES[category]
        return [c for c in cats if c in names] or cats
    if category in names:
        return [category]
    hit = [n for n in names if category in n]
    if hit:
        return hit
    return [n for n in names if n.startswith(category)]


def _pool_query(db: Session, rule):
    """按规则查候选题目。

    categories 的语义：
      None  -> 不限分类（全部题目）
      []    -> 指定了分类但没匹配到任何分类（结果为空）
      [...] -> 按这些分类过滤
    """
    q = db.query(models.Question).filter(
        ~models.Question.content.startswith("<p>[SYSTEM_CATEGORY]")
    )
    cats = rule.get("categories")
    if cats is not None:
        if not cats:
            return q.filter(False)
        q = q.filter(models.Question.category.in_(cats))
    if rule.get("type"):
        q = q.filter(models.Question.type == rule["type"])
    return q


def pool_questions(db: Session, rule):
    """一条规则对应的候选题目。"""
    cats = rule.get("categories")
    if cats is None and rule.get("category"):
        # 规则里只写了分类名（血细胞/尿沉渣…），这里解析成题库里的真实分类
        cats = resolve_categories(db, rule["category"]) or []
        rule = dict(rule)
        rule["categories"] = cats
    return _pool_query(db, rule).all()


def pool_ids(db: Session, rules):
    """所有规则合起来的候选题库（去重）。"""
    ids = []
    seen = set()
    for rule in rules:
        for q in pool_questions(db, rule):
            if q.id not in seen:
                seen.add(q.id)
                ids.append(q.id)
    return ids


def build_paper(db: Session, rules, seed=None):
    """按规则随机抽题，返回题目 id 列表（顺序也打乱）。

    每条规则独立抽题，抽过的题不再重复；题量不足直接报错，
    不给考生凑数的机会。
    """
    rnd = random.Random(seed)
    used = set()
    picked = []
    for idx, rule in enumerate(rules):
        cand = [q.id for q in pool_questions(db, rule) if q.id not in used]
        count = rule["count"]
        if len(cand) < count:
            raise RuleError(
                "规则「%s」题库不足，需要 %d 道，实际只有 %d 道" % (
                    describe_rule(rule), count, len(cand)
                )
            )
        chosen = rnd.sample(cand, count)
        used.update(chosen)
        picked.extend(chosen)
    rnd.shuffle(picked)
    return picked


def describe_rule(rule):
    cats = rule.get("categories")
    label = rule.get("label") or ""
    if not label:
        if isinstance(cats, list) and cats:
            label = "/".join(cats)
        else:
            label = rule.get("category") or "全部分类"
    qtype = TYPE_LABELS.get(rule.get("type"), "不限题型")
    return "%s · %s · %d 道" % (label, qtype, rule.get("count") or 0)


def score_map(exam):
    return {
        "single": exam.single_score or 10,
        "multiple": exam.multiple_score or 20,
        "judgment": exam.judgment_score or 5,
        "fill": exam.fill_score or 10,
    }


def estimate_total_score(db: Session, exam, rules):
    """随机卷的总分估算：按规则里各题型的分值累加。

    规则没限定题型时，用候选题目里各题型分值的平均值，
    这样管理端显示的总分和考生实际拿到的卷子基本一致。
    """
    scores = score_map(exam)
    total = 0.0
    for rule in rules:
        qtype = rule.get("type")
        if qtype:
            total += scores.get(qtype, 10) * rule["count"]
            continue
        pool = pool_questions(db, rule)
        if not pool:
            continue
        avg = sum(scores.get(q.type, 10) for q in pool) / float(len(pool))
        total += avg * rule["count"]
    # 只是管理端的预估总分（考生实际总分按本人卷子算），取整好看些
    return float(round(total))
