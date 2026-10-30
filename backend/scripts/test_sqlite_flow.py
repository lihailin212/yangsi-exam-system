"""本地 SQLite 库跑完整考试流程（回归测试）。

背景：get_exam_progress 里原来写死了 Postgres 的 "NULL::bigint"，
本地开发用的 SQLite 库会直接报语法错，导致"编辑考试/开考/交卷"
这些接口在本地全是 500。改成 SQLAlchemy 的 cast(null(), ...) 后
两种数据库都能跑，这个脚本就是防它退化用的。

用法：cd backend && python scripts/test_sqlite_flow.py
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

TMP = tempfile.mkdtemp(prefix="sqliteflow_")
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

emp = "sqlflowtest"
u = db.query(User).filter_by(employee_id=emp).first()
if not u:
    u = User(employee_id=emp, name="本地流程测试",
             password_hash=hash_password("123456"), dept="检验科",
             role="student", is_admin=False, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
qids = [q.id for q in db.query(Question).filter(
    ~Question.content.startswith("<p>[SYSTEM_CATEGORY]")).limit(3).all()]
db.close()

admin = client.post("/api/auth/login",
                    json={"employee_id": "admin", "password": "admin123"}).json()["access_token"]
ah = {"Authorization": "Bearer " + admin}
tok = client.post("/api/auth/login",
                  json={"employee_id": emp, "password": "123456"}).json()["access_token"]
sh = {"Authorization": "Bearer " + tok}

r = client.post("/api/exams", json={
    "title": "【本地】SQLite 流程回归",
    "duration": 60,
    "start_time": (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "end_time": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
    "question_ids": qids,
}, headers=ah)
assert r.status_code == 200, r.text
exam_id = r.json()["id"]
print("建考试:", r.status_code, "id =", exam_id)

for label, fn in (
    ("管理端 取考试详情(编辑按钮)", lambda: client.get("/api/exams/%d" % exam_id, headers=ah)),
    ("管理端 考试列表", lambda: client.get("/api/exams", headers=ah)),
    ("考生 开考", lambda: client.post("/api/exams/%d/start" % exam_id, headers=sh)),
    ("考生 取卷面", lambda: client.get("/api/exams/%d" % exam_id, headers=sh)),
):
    resp = fn()
    print("%-24s %s" % (label, resp.status_code))
    assert resp.status_code == 200, resp.text

db = SessionLocal()
qs = db.query(Question).filter(Question.id.in_(qids)).all()
answers = {str(q.id): q.answer for q in qs}
db.close()
r = client.post("/api/exams/%d/submit" % exam_id,
                json={"exam_id": exam_id, "answers": json.dumps(answers)}, headers=sh)
print("%-24s %s (得分 %s)" % ("考生 交卷", r.status_code, r.json().get("score")))
assert r.status_code == 200, r.text

for label, fn in (
    ("管理端 看成绩", lambda: client.get("/api/exams/%d/records" % exam_id, headers=ah)),
    ("管理端 导出 Excel", lambda: client.get("/api/exams/%d/export" % exam_id, headers=ah)),
):
    resp = fn()
    print("%-24s %s" % (label, resp.status_code))
    assert resp.status_code == 200, resp.text

shutil.rmtree(TMP, ignore_errors=True)
print("\n✅ 本地 SQLite 全流程跑通")
