"""
Finish migration: distributions + remaining questions.
"""
import requests, json, sqlite3, time

BACKEND = 'https://stellar-youth-production-1591.up.railway.app'
FRONTEND = 'https://yangsi-exam-system-production-6700.up.railway.app'
LOCAL_DB = "backend/exam.db"

session = requests.Session()

r = session.post(f"{BACKEND}/api/auth/login",
    json={"employee_id":"admin","password":"admin123"}, timeout=30)
token = r.json()["access_token"]

def api_get(path):
    r = session.get(f"{BACKEND}{path}",
        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()

def api_post(path, data):
    r = session.post(f"{BACKEND}{path}",
        json=data,
        headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return r.json(), r.status_code

conn = sqlite3.connect(LOCAL_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Current state
rq = api_get("/api/questions")
existing_q_ids = set(q["id"] for q in rq.get("items", []))
print(f"Railway has {len(existing_q_ids)} questions, IDs: {sorted(existing_q_ids)}")

# Check local question IDs
local_questions = cur.execute("SELECT id FROM questions ORDER BY id").fetchall()
local_q_ids = [q["id"] for q in local_questions]
print(f"Local has {len(local_q_ids)} questions")

missing_q_ids = [qid for qid in local_q_ids if qid not in existing_q_ids]
print(f"Need to migrate: {missing_q_ids}")

# Step 1: Migrate missing questions
print("\n[1] Migrating missing questions...")
for qid in missing_q_ids:
    q = cur.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    data = {
        "type": q["type"],
        "content": q["content"],
        "options": q["options"],
        "answer": q["answer"],
        "analysis": q["analysis"] or "",
        "category": q["category"] or ""
    }
    result, status = api_post("/api/questions", data)
    if status in (200, 201):
        print(f"    Q{qid} -> new ID {result['id']}")
    else:
        print(f"    [FAIL] Q{qid}: {result}")

# Step 2: Create distributions using known mappings
print("\n[2] Creating distributions...")
# local_user_id -> railway_user_id
user_map = {2: 2, 3: 3, 4: 4, 6: 5}
# local_exam_id -> railway_exam_id
exam_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

dists = cur.execute("SELECT * FROM exam_distributions ORDER BY id").fetchall()
created = 0
for d in dists:
    if d["user_id"] == 1:  # Skip admin
        continue
    r_exam = exam_map.get(d["exam_id"])
    r_user = user_map.get(d["user_id"])
    if not r_exam or not r_user:
        print(f"    Skip: local_exam={d['exam_id']} local_user={d['user_id']}")
        continue
    result, status = api_post("/api/distributions", {"exam_id": r_exam, "user_ids": [r_user]})
    if status in (200, 201):
        results = result if isinstance(result, list) else [result]
        for r in results:
            url = f"{FRONTEND}/#/invite/{r['invite_code']}"
            print(f"    {r['user_name']}: {url}")
        created += 1
    else:
        print(f"    [FAIL] exam={r_exam} user={r_user}: {result}")

print(f"\n{created} distributions created.")
conn.close()
