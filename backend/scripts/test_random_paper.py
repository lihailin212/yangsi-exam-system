"""随机卷功能的端到端验证（跑在临时 SQLite 库上，不动开发库）。

注意：本地 exam.db 里没有"填空题"，所以题型规则用单选/多选验证；
生产库有填空题，另有一条针对生产库的只读校验脚本。

覆盖：
1. 抽题接口支持"按分类"和"按题型"两种规则
2. 创建随机卷考试
3. 不同考生拿到题数相同、题目不同的卷子
4. 同一考生重复进入拿到同一份卷子
5. 判分按考生自己的卷子算
"""
import os
import shutil
import sys
import tempfile

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

TMP = tempfile.mkdtemp(prefix="examtest_")
DB = os.path.join(TMP, "test.db")
shutil.copy2(os.path.join(BACKEND, "exam.db"), DB)
os.environ["DATABASE_URL"] = "sqlite:///" + DB.replace("\\", "/")

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models, crud, paper as paper_lib
from app.auth import hash_password

client = TestClient(app)


def login(user, pwd):
    r = client.post("/api/auth/login", json={"employee_id": user, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


admin = login("admin", "admin123")

db = SessionLocal()
users = []
for i in (1, 2):
    emp = "tuser%d" % i
    u = db.query(models.User).filter_by(employee_id=emp).first()
    if not u:
        u = models.User(employee_id=emp, name="考生%d" % i,
                        password_hash=hash_password("123456"),
                        dept="检验科", role="student", is_admin=False, is_active=True)
        db.add(u)
        db.commit()
        db.refresh(u)
    users.append(u)
user_ids = [u.id for u in users]
db.close()

print("== 1. 抽题接口：按亚类别 ==")
r = client.post("/api/questions/random", json={
    "rules": [
        {"category": "血细胞", "type": "single", "count": 3},
        {"category": "尿沉渣", "type": "", "count": 2},
    ]
}, headers=admin)
assert r.status_code == 200, r.text
print("   抽到 %d 道；各规则题库量：%s" % (
    len(r.json()["question_ids"]),
    [(x["category"], x["pool"]) for x in r.json()["rules"]]))
assert len(r.json()["question_ids"]) == 5

print("== 2. 抽题接口：按题型 ==")
r = client.post("/api/questions/random", json={
    "rules": [
        {"category": "", "type": "single", "count": 4},
        {"category": "", "type": "multiple", "count": 2},
    ]
}, headers=admin)
assert r.status_code == 200, r.text
print("   抽到 %d 道" % len(r.json()["question_ids"]))

print("== 3. 题库不够时报错 ==")
r = client.post("/api/questions/random", json={
    "rules": [{"category": "形态学/其他体液形态学", "type": "", "count": 50}]
}, headers=admin)
print("   ", r.status_code, r.json().get("detail"))
assert r.status_code == 400

print("== 4. 创建随机卷考试 ==")
rules = [
    {"category": "血细胞", "type": "single", "count": 5},
    {"category": "尿沉渣", "type": "", "count": 3},
    {"category": "寄生虫", "type": "", "count": 2},
]
r = client.post("/api/exams", json={
    "title": "随机卷测试",
    "duration": 30,
    "random_mode": True,
    "random_rules": rules,
    "question_ids": [],
}, headers=admin)
assert r.status_code == 200, r.text
exam_id = r.json()["id"]
print("   考试 id=%d，候选题库 %d 道" % (exam_id, r.json()["question_count"]))

print("== 5. 预览样卷 ==")
r = client.get("/api/exams/%d/preview-paper" % exam_id, headers=admin)
assert len(r.json()["question_ids"]) == 10, r.text
print("   样卷 %d 道" % len(r.json()["question_ids"]))

print("== 6. 两名考生抽卷 ==")
db = SessionLocal()
exam = crud.get_exam(db, exam_id)
papers = []
for uid in user_ids:
    ids = crud.get_or_create_paper(db, exam, uid, 1)
    papers.append(ids)
    print("   考生%s 题数=%d" % (uid, len(ids)))
    assert len(ids) == 10, "每人题数应相同"
assert set(papers[0]) != set(papers[1]), "不同考生应抽到不同题"
print("   两人题目不同 ✓")

print("== 7. 同一考生重复进入 ==")
again = crud.get_or_create_paper(db, exam, user_ids[0], 1)
assert again == papers[0], "同一人题目应保持不变"
print("   题目不变 ✓")

print("== 8. 补考换一份新卷 ==")
second = crud.get_or_create_paper(db, exam, user_ids[0], 2)
assert len(second) == 10 and set(second) != set(papers[0]), "补考应换新卷"
print("   补考卷 %d 道，与首卷不同 ✓" % len(second))

print("== 9. 判分按本人卷子 ==")
qs = db.query(models.Question).filter(
    models.Question.id.in_(papers[0])).all()
answers = {str(q.id): q.answer for q in qs}
rec = crud.create_record(db, exam, user_ids[0], __import__("json").dumps(answers),
                          attempt_no=1)
db.commit()
print("   得分 %.0f / 总分 %.0f" % (rec.score, rec.total_score))
assert rec.total_score > 0
assert rec.score == rec.total_score, "全对应该满分"

print("== 10. 考生看不到候选题库 ==")
tok = login("tuser1", "123456")
r = client.get("/api/exams/%d" % exam_id, headers=tok)
assert r.status_code == 200, r.text
qs_out = r.json()["questions"]
print("   考生只看到自己抽到的 %d 道（题目 id 数量一致：%d）" % (
    len(qs_out), len(r.json()["question_ids"])))
assert len(qs_out) == 10, "考生只应看到自己抽到的 10 道"

print("== 11. 固定卷面考试不受影响 ==")
r = client.post("/api/exams", json={
    "title": "固定卷测试", "duration": 30,
    "question_ids": [1, 2, 3, 4, 5],
}, headers=admin)
assert r.status_code == 200, r.text
fixed_id = r.json()["id"]
tok2 = login("tuser2", "123456")
r = client.get("/api/exams/%d" % fixed_id, headers=tok2)
assert len(r.json()["questions"]) == 5, r.text
print("   固定卷 %d 道 ✓" % len(r.json()["questions"]))

print("\n全部通过 ✅")
shutil.rmtree(TMP, ignore_errors=True)
