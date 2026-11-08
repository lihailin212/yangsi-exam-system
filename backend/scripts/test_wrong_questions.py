# -*- coding: utf-8 -*-
"""错题本功能的独立测试（用临时 SQLite，不碰线上 Neon）。

跑法：cd backend && python scripts/test_wrong_questions.py
"""
import os, sys, json, tempfile, shutil

TMP = tempfile.mkdtemp(prefix="wq_test_")
os.environ["DATABASE_URL"] = ""          # 走 SQLite 分支
os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = TMP
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_INITIAL_PASSWORD"] = "AdminTest123"
os.environ.pop("BILLING_ENABLED", None)

sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient
from app.main import app
from app import crud, models
from app.database import SessionLocal

client = TestClient(app)

def mk_user(emp, name, is_admin=False, pwd="AdminTest123"):
    db = SessionLocal()
    try:
        u = models.User(employee_id=emp, name=name, is_admin=is_admin,
                        password_hash=crud.hash_password(pwd))
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()

def login(emp, pwd):
    r = client.post("/api/auth/login", json={"employee_id": emp, "password": pwd})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

def hdr(tok): return {"Authorization": "Bearer " + tok}

ok = 0
def check(name, cond, extra=""):
    global ok
    print(("PASS  " if cond else "FAIL  ") + name + (("  " + str(extra)) if extra else ""))
    if cond: ok += 1
    else: globals()['FAILED'] = True

FAILED = False

# --- 建一个超管和两个学员 ---
admin_id = mk_user("admin", "管理员", True)
stu_id = mk_user("1001", "学员甲")
other_id = mk_user("1002", "学员乙")

admin_tok = login("admin", "AdminTest123")
stu_tok = login("1001", "AdminTest123")
other_tok = login("1002", "AdminTest123")

# --- 造一场考试：3 道题 ---
db = SessionLocal()
qids = []
for i in range(3):
    q = models.Question(type="single", content="<p>测试题%d</p>" % (i + 1),
                         options='{"A":"甲","B":"乙"}', answer="A",
                         analysis="解析", category="测试分类")
    db.add(q); db.flush()
    qids.append(q.id)
exam = models.Exam(title="测试考试", duration=30, kind="normal", pass_score=60,
                   single_score=10, multiple_score=20, judgment_score=5,
                   fill_score=10, total_score=30)
db.add(exam); db.flush()
for qid in qids:
    db.execute(models.exam_question.insert().values(exam_id=exam.id, question_id=qid))
db.commit()
EXAM_ID = exam.id
db.close()
check("测试库建好了", len(qids) == 3, "exam_id=%s" % EXAM_ID)

# --- 交卷：第1题做对，第2题做错，第3题不答 ---
db = SessionLocal()
exam = db.query(models.Exam).filter(models.Exam.id == EXAM_ID).first()
scoring = {qid: (t, a) for qid, t, a in crud.get_scoring_questions(db, EXAM_ID)}
correct_qid = qids[0]
wrong_qid = qids[1]
blank_qid = qids[2]
answers = {str(correct_qid): scoring[correct_qid][1], str(wrong_qid): "X"}
rec = crud.create_record(db, exam, stu_id, json.dumps(answers))
db.close()
check("交卷成功", rec.score is not None, "得分 %s" % rec.score)

# --- 错题本 ---
r = client.get("/api/wrong-questions", headers=hdr(stu_tok))
check("错题本返回 200", r.status_code == 200, r.text[:120])
data = r.json()
check("错题本有 2 条（做错1 + 未答1）", data["total"] == 2, data["total"])
ids = {it["question_id"] for it in data["items"]}
check("包含做错的题", wrong_qid in ids, ids)
check("包含未作答的题", blank_qid in ids, ids)
check("不含做对的题", correct_qid not in ids, ids)
item = next(it for it in data["items"] if it["question_id"] == wrong_qid)
check("记录了我的错答", item["wrong_answer"] == "X", item["wrong_answer"])
check("记录了正确答案", item["answer"] == scoring[wrong_qid][1], item["answer"])
check("状态是待复习", item["status"] == "wrong", item["status"])

# --- 统计 ---
r = client.get("/api/wrong-questions/stats", headers=hdr(stu_tok))
st = r.json()
check("统计待复习=2", st["wrong_total"] == 2, st)
check("统计总数=2", st["all_total"] == 2, st)

# --- 别人的错题本看不到 ---
r = client.get("/api/wrong-questions", headers=hdr(other_tok))
check("别人的错题本是空的", r.json()["total"] == 0, r.json()["total"])

# --- 再错一次，次数累加 ---
db = SessionLocal()
exam = db.query(models.Exam).filter(models.Exam.id == EXAM_ID).first()
crud.create_record(db, exam, stu_id, json.dumps(answers))
db.close()
r = client.get("/api/wrong-questions", headers=hdr(stu_tok))
item = next(it for it in r.json()["items"] if it["question_id"] == wrong_qid)
check("错题次数累加到 2", item["wrong_count"] == 2, item["wrong_count"])

# --- 做对了 -> 标记已掌握 ---
db = SessionLocal()
exam = db.query(models.Exam).filter(models.Exam.id == EXAM_ID).first()
allright = {str(q): scoring[q][1] for q in qids}
crud.create_record(db, exam, stu_id, json.dumps(allright))
db.close()
r = client.get("/api/wrong-questions?status=mastered", headers=hdr(stu_tok))
check("做对后进入已掌握", r.json()["total"] == 2, r.json()["total"])
r = client.get("/api/wrong-questions?status=wrong", headers=hdr(stu_tok))
check("待复习清空", r.json()["total"] == 0, r.json()["total"])

# --- 筛选 ---
r = client.get("/api/wrong-questions?status=&q_type=judgment", headers=hdr(stu_tok))
check("按题型筛选可用", r.status_code == 200, r.status_code)

# --- 生成练习卷 ---
r = client.post("/api/wrong-questions/generate-exam", headers=hdr(stu_tok),
                json={"status": "mastered", "q_type": "", "limit": 10})
check("生成练习卷 200", r.status_code == 200, r.text[:200])
gen = r.json()
check("练习卷有题", gen["question_count"] == 2, gen)

# 练习卷要标成 wrong_practice，只有本人能做
db = SessionLocal()
pe = db.query(models.Exam).filter(models.Exam.id == gen["exam_id"]).first()
check("练习卷 kind=wrong_practice", pe.kind == "wrong_practice", pe.kind)
check("练习卷归属于本人", pe.created_by == stu_id, pe.created_by)
db.close()

# 别人做这张卷子应被拒
r = client.post("/api/exams/%d/start" % gen["exam_id"], headers=hdr(other_tok))
check("他人不能做我的错题练习卷", r.status_code == 403, r.status_code)

# 本人可以做
r = client.post("/api/exams/%d/start" % gen["exam_id"], headers=hdr(stu_tok))
check("本人可以开考", r.status_code == 200, r.text[:150])

# 练习卷不出现在正式考试列表里
r = client.get("/api/exams?skip=0&limit=100&kind=normal", headers=hdr(stu_tok))
ids_in_list = {it["id"] for it in r.json()["items"]}
check("练习卷不进正式考试列表", gen["exam_id"] not in ids_in_list)

# 我的练习卷列表能看到
r = client.get("/api/wrong-questions/practice-exams", headers=hdr(stu_tok))
check("我的练习卷列表", any(i["exam_id"] == gen["exam_id"] for i in r.json()["items"]))

# --- 导出 Excel ---
r = client.get("/api/wrong-questions/export?status=mastered", headers=hdr(stu_tok))
check("导出 200", r.status_code == 200, r.status_code)
check("是 xlsx", "spreadsheetml" in r.headers.get("content-type", ""), r.headers.get("content-type"))
check("文件非空", len(r.content) > 3000, len(r.content))
open(os.path.join(TMP, "export.xlsx"), "wb").write(r.content)

# --- 删除一条 ---
r = client.get("/api/wrong-questions?status=mastered", headers=hdr(stu_tok))
wid = r.json()["items"][0]["id"]
r = client.delete("/api/wrong-questions/%d" % wid, headers=hdr(stu_tok))
check("删除成功", r.status_code == 200, r.status_code)
r = client.delete("/api/wrong-questions/%d" % wid, headers=hdr(stu_tok))
check("删已删的返回 404", r.status_code == 404, r.status_code)

# --- my-scores 批量接口 ---
r = client.get("/api/exam-records/my-scores", headers=hdr(stu_tok))
check("my-scores 200", r.status_code == 200, r.status_code)
check("my-scores 是字典", isinstance(r.json(), dict), type(r.json()))

print()
print("通过 %d 项" % ok)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAILED else 0)
