# -*- coding: utf-8 -*-
"""考生自学（做题模式）接口。

原来的"考生自学"只是点一下看答案，不判分也不留痕。这里补一套做题模式：

* 选题：随机学习 / 按题型 / 按题号范围 / 按题目编号；
* 作答：考生自己做，提交后由后端判分（和考试交卷同一套对错口径）；
* 留痕：答错的题自动进本人错题本（wrong_questions 表），
  之前做错、这次做对的题标记为"已掌握"。

题号口径和"考生自学"列表完全一致（都是题目 id 倒序），
所以第 N 题在列表、按题号、按题目编号三种方式里指的是同一道题。
"""
import json
import random
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import crud, models
from ..auth import require_entitlement
from ..database import get_db

router = APIRouter(prefix="/api/self-study", tags=["self-study"])

# 一次最多练多少道题，防止把整个题库拉下来塞进浏览器
MAX_QUESTIONS = 200


def _parse_numbers(text):
    """把 "1,5,8-12" 这样的编号串解析成题号列表。"""
    result = []
    for part in re.split(r"[,，;；\s]+", (text or "").strip()):
        if not part:
            continue
        m = re.match(r"^(\d+)\s*[-~－—至]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            result.extend(range(a, b + 1))
        elif part.isdigit():
            result.append(int(part))
    return result


def _options_map(question):
    """题目的选项字典；解析不了就当没有选项。"""
    try:
        obj = json.loads(question.options or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _judgment_correct_key(question):
    """判断题的标准答案在题库里存的是"正确/错误"文本，这里换算成选项键。

    题库里的判断题选项是空的（A/B/C/D 全是空串），前端会把它们显示成
    "正确/错误"两个按钮，所以这里要按同样的口径把标准答案映射回 A/B。
    """
    ans = (question.answer or "").strip()
    opts = _options_map(question)
    for key, label in opts.items():
        if str(label or "").strip() and crud.normalize_fill_text(label) == crud.normalize_fill_text(ans):
            return key
    normalized = crud.normalize_fill_text(ans)
    if normalized in ("正确", "对", "t", "true", "是", "y", "yes", "√"):
        return "A"
    if normalized in ("错误", "错", "f", "false", "否", "n", "no", "×"):
        return "B"
    return ans


def answer_correct(question, user_answer):
    """判一道题的对错，口径和考试交卷一致。"""
    given = (user_answer or "").strip()
    if question.type == "multiple":
        correct = {x.strip() for x in (question.answer or "").split(",") if x.strip()}
        return bool(given) and {x.strip() for x in given.split(",") if x.strip()} == correct
    if question.type == "fill":
        return crud.fill_answer_matches(given, question.answer)
    if question.type == "judgment":
        return given == _judgment_correct_key(question)
    return given == (question.answer or "").strip()


def correct_keys(question):
    """正确答案对应的选项键列表（填空题没有选项，返回空）。"""
    if question.type == "multiple":
        return [x.strip() for x in (question.answer or "").split(",") if x.strip()]
    if question.type == "fill":
        return []
    if question.type == "judgment":
        return [_judgment_correct_key(question)]
    ans = (question.answer or "").strip()
    return [ans] if ans else []


def answer_text(question):
    """把标准答案整理成一句人能看的话（带选项内容）。"""
    ans = (question.answer or "").strip()
    opts = _options_map(question)
    if question.type == "multiple":
        keys = [x.strip() for x in ans.split(",") if x.strip()]
        parts = [f"{k}. {str(opts.get(k) or '').strip()}".strip() for k in keys]
        return "；".join(p for p in parts if p) or ans
    if question.type in ("single", "judgment"):
        if ans and ans in opts and str(opts.get(ans) or "").strip():
            return f"{ans}. {opts[ans]}"
        if question.type == "judgment":
            key = _judgment_correct_key(question)
            label = str(opts.get(key) or "").strip()
            return f"{key}. {label}" if label else (ans or key)
        return ans
    return ans


class GenerateIn(BaseModel):
    """选题方式的入参。

    mode:
      random  随机学习（可带题型/分类/关键词筛选）
      type    按题型（必须给 q_type；count=0 表示该题型全要）
      range   按题号范围（第 start 题到第 end 题）
      number  按题目编号（numbers 形如 "1,5,8-12"，是题号不是题目 id）
    """
    mode: str = "random"
    count: int = 10
    q_type: str = ""
    category: str = ""
    search: str = ""
    start: int = 0
    end: int = 0
    numbers: str = ""


@router.post("/generate")
def generate_questions(payload: GenerateIn,
                       db: Session = Depends(get_db),
                       current_user=Depends(require_entitlement)):
    """按所选方式生成一组练习题（不含答案和解析）。"""
    mode = (payload.mode or "random").strip()
    if mode not in ("random", "type", "range", "number"):
        raise HTTPException(status_code=400, detail="不支持的选题方式")

    pool = crud.get_question_ids(db, q_type=payload.q_type,
                                 search=payload.search,
                                 category=payload.category)
    if not pool:
        raise HTTPException(status_code=400, detail="当前筛选条件下没有题目")

    if mode == "number":
        numbers = _parse_numbers(payload.numbers)
        if not numbers:
            raise HTTPException(status_code=400, detail="请填写题目编号，例如 1,5,8-12")
        picked = []
        for n in numbers:
            if 1 <= n <= len(pool):
                picked.append(pool[n - 1])
        picked = list(dict.fromkeys(picked))
        if not picked:
            raise HTTPException(
                status_code=400,
                detail=f"题目编号超出范围（当前条件下共 {len(pool)} 道题）")
    elif mode == "range":
        start = payload.start or 1
        end = payload.end or start
        if end < start:
            start, end = end, start
        if start < 1:
            start = 1
        if start > len(pool):
            raise HTTPException(
                status_code=400,
                detail=f"起始题号超出范围（当前条件下共 {len(pool)} 道题）")
        end = min(end, len(pool))
        picked = pool[start - 1:end]
    elif mode == "type":
        if not payload.q_type:
            raise HTTPException(status_code=400, detail="请选择题型")
        count = payload.count or 0
        if count > 0:
            picked = random.sample(pool, min(count, len(pool)))
        else:
            picked = list(pool)
    else:  # random
        count = payload.count or 10
        count = min(max(count, 1), MAX_QUESTIONS)
        picked = random.sample(pool, min(count, len(pool)))

    picked = picked[:MAX_QUESTIONS]
    if not picked:
        raise HTTPException(status_code=400, detail="没有符合条件的题目")

    rows = db.query(models.Question).filter(
        models.Question.id.in_(picked)).all()
    qmap = {q.id: q for q in rows}
    # 题号 = 在当前筛选列表里的位置，和"考生自学"页面看到的题号一致
    seq_map = {qid: i + 1 for i, qid in enumerate(pool)}

    items = []
    for qid in picked:
        q = qmap.get(qid)
        if q is None:
            continue
        items.append({
            "id": q.id,
            "seq": seq_map.get(qid),
            "type": q.type,
            "content": q.content,
            "options": q.options,
            "category": q.category,
        })
    return {
        "items": items,
        "total": len(items),
        "mode": mode,
        "pool_total": len(pool),
    }


class AnswerIn(BaseModel):
    """提交一道题的作答。"""
    question_id: int
    answer: str = ""


@router.post("/answer")
def submit_one_answer(payload: AnswerIn,
                      db: Session = Depends(get_db),
                      current_user=Depends(require_entitlement)):
    """判一道题：答对返回正确答案和解析；答错自动写进本人错题本。"""
    question = crud.get_question(db, payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    correct = answer_correct(question, payload.answer)
    if correct:
        # 之前做错过、这次做对了：从错题本里标记为已掌握
        crud.mark_mastered_questions(db, current_user.id, [question.id])
    else:
        # exam_id 留空：自学练习不是一场正式考试，错题本允许没有考试来源
        crud.record_wrong_questions(db, current_user.id, None,
                                    [(question.id, payload.answer or "")])
    db.commit()

    return {
        "question_id": question.id,
        "correct": correct,
        "correct_answer": answer_text(question),
        "analysis": question.analysis or "",
        "mnemonic": question.mnemonic or "",
        "correct_keys": correct_keys(question),
        "in_wrong_book": not correct,
    }


class FinishIn(BaseModel):
    """交卷：把没做的题记成错题。"""
    unanswered_ids: list[int] = []


@router.post("/finish")
def finish_practice(payload: FinishIn,
                    db: Session = Depends(get_db),
                    current_user=Depends(require_entitlement)):
    """交卷收尾：未作答的题按做错处理，记进错题本。"""
    ids = [int(i) for i in (payload.unanswered_ids or [])]
    if ids:
        rows = db.query(models.Question).filter(
            models.Question.id.in_(ids)).all()
        wrong_rows = [(q.id, "") for q in rows]
        crud.record_wrong_questions(db, current_user.id, None, wrong_rows)
        db.commit()
    return {"ok": True, "marked_wrong": len(ids)}
