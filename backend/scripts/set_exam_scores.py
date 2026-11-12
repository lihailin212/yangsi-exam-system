"""修改一场考试的题型分值，并按抽题规则重算总分。

背景：后台新建考试时「题型分值」默认单选 10 分，而「及格分」输入框上限是 100。
新建时忘了改分值，一场 100 道单选题的考试就成了「满分 1000 分、及格 60 分」，
蒙对 6 题也算及格（截图里就是这个问题）。本脚本把单题分值改回 1 分，
并把已交卷记录的总分、得分一起按新分值重算。

只改分数，不动错题本：对错和分值是两回事，改分值不该影响错题本。

用法：
    cd backend && python scripts/set_exam_scores.py --exam-id 156 --single 1 --dry-run
    cd backend && python scripts/set_exam_scores.py --exam-id 156 --single 1
"""
import argparse
import json
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from db import load_dotenv_local

# app.database 在 import 时就要读 DATABASE_URL，必须先加载 .env.local
load_dotenv_local()

from app import crud, models, paper as paper_lib  # noqa: E402
from app.database import SessionLocal  # noqa: E402

# 题型 -> exams 表里的分值列
TYPE_FIELDS = {
    "single": "single_score",
    "fill": "fill_score",
    "multiple": "multiple_score",
    "judgment": "judgment_score",
}


def score_map(exam):
    """判分用的「题型 -> 分值」对照，和后台判分口径一致。"""
    return {
        "single": exam.single_score,
        "fill": exam.fill_score,
        "multiple": exam.multiple_score,
        "judgment": exam.judgment_score,
    }


def exam_total(db, exam):
    """按后台保存考试时同样的口径重算这场考试的总分。"""
    if exam.random_mode:
        rules = paper_lib.parse_rules(exam.random_rules)
        return paper_lib.estimate_total_score(db, exam, rules)
    return crud._calc_total_score(exam)


def record_total(exam, old_total, new_total, record_old_total):
    """考生那份卷子的总分。

    固定卷面：所有考生同一份卷，总分就是考试总分。
    随机卷：按抽题规则算。规则限定了题型的，每份卷子构成一样，总分也一样；
    规则没限定题型时每人抽到的题型可能不同，按总分比例缩放。
    """
    if not exam.random_mode:
        return new_total
    rules = paper_lib.parse_rules(exam.random_rules)
    new_map = score_map(exam)
    total = 0.0
    for rule in rules:
        if not rule.get("type"):
            ratio = (new_total / old_total) if old_total else 1
            return record_old_total * ratio
        total += (new_map.get(rule["type"]) or 10) * rule["count"]
    return total


def rescore(db, exam, record, new_map):
    """按新的题型分值重新判分，返回这次的得分。

    判分范围是这条记录**当时那份卷子**（crud.get_record_questions 会按交卷时间
    定位到那一轮的 ExamPaper），和交卷当时的判分口径一致：考生没答的题算 0，
    答了的题按新分值给分。题目对错不会变，所以错题本不用动。
    """
    answers = json.loads(record.answers or "{}")
    if not isinstance(answers, dict):
        answers = {}
    questions = crud.get_record_questions(db, record)
    if not questions:
        # 没有卷子快照的历史数据，退回按答案里出现的题号判
        qids = [int(q) for q in answers if str(q).isdigit()]
        if qids:
            questions = (db.query(models.Question)
                         .filter(models.Question.id.in_(qids)).all())
    score = 0.0
    for q in questions:
        given = answers.get(str(q.id), "")
        if q.type == "multiple":
            ok = bool(given) and set((q.answer or "").split(",")) == set(given.split(","))
        elif q.type == "fill":
            ok = crud.fill_answer_matches(given, q.answer)
        else:
            ok = str(given).strip() == str(q.answer or "").strip()
        if ok:
            score += new_map.get(q.type) or 10
    return score


def main():
    ap = argparse.ArgumentParser(description="修改考试题型分值并重算总分")
    ap.add_argument("--exam-id", type=int, required=True)
    ap.add_argument("--single", type=int, help="单选题分值")
    ap.add_argument("--fill", type=int, help="填空题分值")
    ap.add_argument("--multiple", type=int, help="多选题分值")
    ap.add_argument("--judgment", type=int, help="判断题分值")
    ap.add_argument("--dry-run", action="store_true", help="只打印改动，不写库")
    args = ap.parse_args()

    changes = {"single": args.single, "fill": args.fill,
               "multiple": args.multiple, "judgment": args.judgment}
    changes = {k: v for k, v in changes.items() if v is not None}
    if not changes:
        raise SystemExit("没有指定要改的分值（--single / --fill / --multiple / --judgment）")

    db = SessionLocal()
    try:
        exam = db.query(models.Exam).filter(models.Exam.id == args.exam_id).first()
        if not exam:
            raise SystemExit(f"考试 id={args.exam_id} 不存在")

        old_total = exam.total_score
        print(f"考试：id={exam.id} {exam.title}（随机卷={bool(exam.random_mode)}）")
        print(f"  改前：单选 {exam.single_score} / 填空 {exam.fill_score} / "
              f"多选 {exam.multiple_score} / 判断 {exam.judgment_score}，总分 {old_total}")

        for qtype, value in changes.items():
            setattr(exam, TYPE_FIELDS[qtype], value)
        db.flush()

        new_total = exam_total(db, exam)
        exam.total_score = new_total
        db.flush()
        print(f"  改后：{changes}，总分 {new_total}")

        new_map = score_map(exam)
        records = (db.query(models.ExamRecord)
                     .filter(models.ExamRecord.exam_id == exam.id).all())
        for record in records:
            score = rescore(db, exam, record, new_map)
            total = record_total(exam, old_total, new_total, record.total_score)
            print(f"  记录 id={record.id}：{record.score}/{record.total_score} -> {score}/{total}")
            record.score = score
            record.total_score = total

        if args.dry_run:
            db.rollback()
            print("（--dry-run，未写库）")
        else:
            db.commit()
            print("已写入")
    finally:
        db.close()


if __name__ == "__main__":
    main()
