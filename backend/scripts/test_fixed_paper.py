import os, shutil, sys, tempfile
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
TMP = tempfile.mkdtemp(prefix="fixedtest_")
DB = os.path.join(TMP, "t.db")
shutil.copy2(os.path.join(BACKEND, "exam.db"), DB)
os.environ["DATABASE_URL"] = "sqlite:///" + DB.replace("\\", "/")
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
tok = c.post("/api/auth/login", json={"employee_id": "admin", "password": "admin123"}).json()["access_token"]
h = {"Authorization": "Bearer " + tok}

r = c.post("/api/exams", json={"title": "固定卷A", "duration": 60, "question_ids": [1, 2, 3]}, headers=h)
print("建固定卷:", r.status_code, r.json().get("question_count"), "random_mode=", r.json().get("random_mode"), "总分=", r.json().get("total_score"))
eid = r.json()["id"]
assert r.json()["random_mode"] is False
assert r.json()["question_count"] == 3

r = c.put("/api/exams/%d" % eid, json={"title": "固定卷A改", "question_ids": [8, 9, 10, 12]}, headers=h)
print("改固定卷:", r.status_code, r.json().get("question_count"), r.json().get("title"))
assert r.json()["question_count"] == 4

r = c.put("/api/exams/%d" % eid, json={"random_mode": True, "random_rules": [
    {"category": "血细胞", "type": "single", "count": 3}]}, headers=h)
print("改成随机卷:", r.status_code, r.json().get("question_count"), r.json().get("random_mode"), r.json().get("random_rules"))
assert r.json()["random_mode"] is True

r = c.put("/api/exams/%d" % eid, json={"random_mode": False, "question_ids": [2, 3]}, headers=h)
print("改回固定卷:", r.status_code, r.json().get("question_count"), r.json().get("random_mode"))
assert r.json()["random_mode"] is False

r = c.post("/api/exams", json={"title": "缺规则", "random_mode": True, "random_rules": []}, headers=h)
print("缺规则:", r.status_code, r.json().get("detail"))
assert r.status_code == 400

r = c.post("/api/exams", json={"title": "题不够", "random_mode": True,
    "random_rules": [{"category": "形态学/其他体液形态学", "type": "", "count": 30}]}, headers=h)
print("题不够:", r.status_code, r.json().get("detail"))
assert r.status_code == 400

shutil.rmtree(TMP, ignore_errors=True)
print("\n固定卷/随机卷切换验证通过 ✅")

