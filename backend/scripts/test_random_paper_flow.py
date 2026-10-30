"""需求 4 的完整 HTTP 流程验证：每人题数相同、题目随机。

覆盖：
1. 管理员建一场"每人随机卷"考试（规则规定题量）
2. 两名考生进考试 -> 题目数量相同、题目不同
3. 同一考生刷新/重进 -> 题目不变
4. 考生拿不到候选题库、拿不到答案
5. 判分按考生本人那份卷子，总分按本人卷子算
6. 补考换一份新卷
7. 普通固定卷考试完全不受影响

用法：cd backend && python scripts/test_random_paper_flow.py
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

TMP = tempfile.mkdtemp(prefix="paperflow_")
DB = os.path.join(TMP, "t.db")
shutil.copy2(os.path.join(BACKEND, "exam.db"), DB)
os.environ["DATABASE_URL"] = "sqlite:///" + DB.replace("\\", "/")

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, Question
from app.auth import hash_password

client = TestClient(app)
db = SessionLocal()

emps = []
for i in (1, 2):
    emp = "paperflow%d" % i
    u = db.query(User).filter_by(employee_id=emp).first()
    if not u:
        u = User(employee_id=emp, name="考生%d" % i,
                 password_hash=hash_password("123456"), dept="检验科",
                 role="student", is_admin=False, is_active=True)
        db.add(u)
        db.commit()
        db.refresh(u)
    emps.append(emp)
db.close()

ah = {"Authorization": "Bearer " + client.post(
    "/api/auth/login", json={"employee_id": "admin", "password": "admin123"}
).json()["access_token"]}


def student(emp):
    tok = client.post("/api/auth/login",
                       json={"employee_id": emp, "password": "123456"}).json()["access_token"]
    return {"Authorization": "Bearer " + tok}


def qids_of(cat, limit=6):
    db = SessionLocal()
    qs = db.query(Question).filter(Question.category == cat).limit(limit).all()
    out = [q.id for q in qs]
    db.close()
    return out


print("== 1. 管理员建卷：每人随机卷，规则规定题量 ==")
rules = [
    {"category": "血细胞", "type": "single", "count": 4},
    {"category": "尿沉渣", "type": "", "count": 3},
]
r = client.post("/api/exams", json={
    "title": "【本地】每人随机卷验证", "duration": 60,
    "start_time": (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "end_time": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "random_mode": True, "random_rules": rules, "question_ids": [],
}, headers=ah)
assert r.status_code == 200, r.text
exam_id = r.json()["id"]
print("   考试 id=%d  random_mode=%s  候选题库=%d 道  预估总分=%s" % (
    exam_id, r.json()["random_mode"], r.json()["question_count"], r.json()["total_score"]))
assert r.json()["random_mode"] is True

print("== 2. 两名考生开考 ==")
papers = []
for emp in emps:
    h = student(emp)
    s = client.post("/api/exams/%d/start" % exam_id, headers=h)
    assert s.status_code == 200, s.text
    g = client.get("/api/exams/%d" % exam_id, headers=h)
    assert g.status_code == 200, g.text
    ids = [q["id"] for q in g.json()["questions"]]
    papers.append(ids)
    print("   %s 抽到 %d 道（题目 id: %s）" % (emp, len(ids), ids))
    assert len(ids) == 7, "每人题数应与规则一致(4+3)"
    assert all(q["answer"] == "" for q in g.json()["questions"]), "考试中不应下发答案"

assert len(papers[0]) == len(papers[1]), "两人题数必须相同"
assert set(papers[0]) != set(papers[1]), "两人题目必须不同"
print("   ✓ 题数相同(%d)、题目不同" % len(papers[0]))

print("== 3. 同一考生重新进入 -> 题目不变 ==")
h = student(emps[0])
client.post("/api/exams/%d/start" % exam_id, headers=h)
again = [q["id"] for q in client.get("/api/exams/%d" % exam_id, headers=h).json()["questions"]]
assert again == papers[0], "同一人题目应保持不变"
print("   ✓ 题目不变")

print("== 4. 判分按本人卷子 ==")
db = SessionLocal()
qs = db.query(Question).filter(Question.id.in_(papers[0])).all()
answers = {str(q.id): q.answer for q in qs}
db.close()
r = client.post("/api/exams/%d/submit" % exam_id,
                json={"exam_id": exam_id, "answers": json.dumps(answers)}, headers=h)
assert r.status_code == 200, r.text
print("   考生1 得分 %s / 总分 %s" % (r.json()["score"], r.json()["total_score"]))
assert r.json()["total_score"] == 70.0, "总分应按本人卷子(7题×10分)算"

print("== 5. 考生拿不到候选题库 ==")
h2 = student(emps[1])
g = client.get("/api/exams/%d" % exam_id, headers=h2)
# 管理员看到的是候选题池，考生看到的是自己那份
pool_size = len(client.get("/api/exams/%d" % exam_id, headers=ah).json()["question_ids"])
print("   考生2 看到 %d 道（管理员那边候选池有 %d 道，考生拿不到）" % (
    len(g.json()["questions"]), pool_size))
assert len(g.json()["questions"]) == 7 and pool_size > 7

print("== 6. 补考换一份新卷 ==")
db = SessionLocal()
from app import crud
exam = crud.get_exam(db, exam_id)
u = db.query(User).filter_by(employee_id=emps[0]).first()
second = crud.get_or_create_paper(db, exam, u.id, 2)
db.close()
print("   第 2 轮抽到 %d 道，与第 1 轮相同？%s" % (
    len(second), set(second) == set(papers[0])))
assert len(second) == 7 and set(second) != set(papers[0]), "补考应换新卷"

print("== 7. 普通固定卷考试不受影响 ==")
r = client.post("/api/exams", json={
    "title": "【本地】固定卷对照", "duration": 60,
    "start_time": (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "end_time": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "question_ids": qids_of("形态学/血细胞形态学", 5),
}, headers=ah)
assert r.status_code == 200, r.text
fixed_id = r.json()["id"]
g = client.get("/api/exams/%d" % fixed_id, headers=h2)
print("   固定卷：random_mode=%s，题目 %d 道" % (
    g.json()["random_mode"], len(g.json()["questions"])))
assert g.json()["random_mode"] is False and len(g.json()["questions"]) == 5

shutil.rmtree(TMP, ignore_errors=True)
print("\n✅ 需求 4 全流程验证通过：每人题数相同、题目随机")
