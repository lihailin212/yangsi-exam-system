"""
Migrate all local SQLite data to Railway cloud.
Idempotent: safe to run multiple times.
Steps:
  1. Login
  2. Migrate students (creates if not exists)
  3. Migrate questions (creates if not exists)
  4. Migrate exams (creates if not exists, updates question_ids)
  5. Migrate distributions (creates if not exists)
"""
import requests, json, sqlite3, time

BACKEND = 'https://stellar-youth-production-1591.up.railway.app'
FRONTEND = 'https://yangsi-exam-system-production-6700.up.railway.app'
LOCAL_DB = "backend/exam.db"
TIMEOUT = 60

session = requests.Session()
session.verify = True

def api_login():
    r = session.post(f"{BACKEND}/api/auth/login",
        json={"employee_id": "admin", "password": "admin123"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["access_token"]

def api_get(path, token):
    r = session.get(f"{BACKEND}{path}",
        headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def api_post(path, data, token, retries=3):
    for attempt in range(retries):
        try:
            r = session.post(f"{BACKEND}{path}",
                json=data, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
            return r.json(), r.status_code
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    [RETRY] {path} (attempt {attempt+2}/{retries})")
                time.sleep(2)
            else:
                raise
    return None, 0

def api_put(path, data, token, retries=3):
    for attempt in range(retries):
        try:
            r = session.put(f"{BACKEND}{path}",
                json=data, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
            return r.json(), r.status_code
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    [RETRY] PUT {path} (attempt {attempt+2}/{retries})")
                time.sleep(2)
            else:
                raise
    return None, 0

conn = sqlite3.connect(LOCAL_DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("Railway Cloud Migration (Idempotent)")
print("=" * 60)

# Step 1: Login
print("\n[1/5] Logging into Railway backend...")
token = api_login()
print(f"    Logged in! Token: {token[:20]}...")

# Step 2: Check existing Railway state
print("\n[2/5] Checking Railway current state...")
rq = api_get("/api/questions?limit=1000", token)
rq_items = rq.get('items', [])
existing_q_ids = {q['id']: q for q in rq_items}

rs = api_get("/api/students?limit=100", token)
rs_items = rs.get('items', [])
existing_students = {s['employee_id']: s for s in rs_items}

re = api_get("/api/exams?limit=100", token)
re_items = re.get('items', [])
existing_exams = {e['id']: e for e in re_items}

rd = api_get("/api/distributions?exam_id=1", token)  # just to check if API works
print(f"    Railway: {len(existing_q_ids)} questions, "
      f"{len(existing_students)} students, "
      f"{len(existing_exams)} exams")

# Step 3: Migrate students
print("\n[3/5] Migrating students...")
local_students = cur.execute(
    "SELECT * FROM users WHERE is_admin != 1 ORDER BY id"
).fetchall()
student_map = {}  # local_id -> railway_id

for s in local_students:
    emp_id = str(s["employee_id"])
    if emp_id in existing_students:
        student_map[s["id"]] = existing_students[emp_id]["id"]
        print(f"    [SKIP] {s['name']} ({emp_id}) already exists")
        continue
    data = {
        "employee_id": emp_id,
        "name": s["name"],
        "password": "123456",
        "dept": s["dept"] or "",
        "role": s["role"] or "学员"
    }
    result, status = api_post("/api/students", data, token)
    if status in (200, 201):
        student_map[s["id"]] = result["id"]
        print(f"    [NEW] {s['name']} ({emp_id}) -> ID {result['id']}")
    else:
        print(f"    [FAIL] {s['employee_id']}: {result}")
print(f"    {len(student_map)} students mapped.")

# Step 4: Migrate questions
print("\n[4/5] Migrating questions...")
local_questions = cur.execute("SELECT * FROM questions ORDER BY id").fetchall()
question_map = {}  # local_id -> railway_id

for q in local_questions:
    # Check if question with same content exists
    found = None
    for rid, rq_item in existing_q_ids.items():
        if (rq_item.get('content') == q['content'] and
            rq_item.get('type') == q['type'] and
            rq_item.get('answer') == q['answer']):
            found = rid
            break

    if found is not None:
        question_map[q["id"]] = found
        print(f"    [SKIP] Q{q['id']} already exists")
        continue

    data = {
        "type": q["type"],
        "content": q["content"],
        "options": q["options"],
        "answer": q["answer"],
        "analysis": q["analysis"] or "",
        "category": q["category"] or ""
    }
    result, status = api_post("/api/questions", data, token)
    if status in (200, 201):
        question_map[q["id"]] = result["id"]
        print(f"    [NEW] Q{q['id']} -> new ID {result['id']}")
    else:
        print(f"    [FAIL] Q{q['id']}: {result}")
print(f"    {len(question_map)} questions mapped.")

# Get ALL railway question IDs for exam assignment
all_rq = api_get("/api/questions?limit=1000", token)
all_rq_items = all_rq.get('items', [])
all_railway_q_ids = sorted([q['id'] for q in all_rq_items])
print(f"    Total Railway questions available: {len(all_railway_q_ids)}")

# Step 5: Migrate exams and distributions
print("\n[5/5] Migrating exams and distributions...")
local_exams = cur.execute("SELECT * FROM exams ORDER BY id").fetchall()
exam_id_map = {}  # local_exam_id -> railway_exam_id

for e in local_exams:
    # Check if exam with same title exists
    found_exam = None
    for re_ in re_items:
        if re_.get('title') == e['title']:
            found_exam = re_
            break

    if found_exam is not None:
        exam_id_map[e['id']] = found_exam['id']
        print(f"    [SKIP] Exam '{e['title']}' (local {e['id']}) already exists as railway {found_exam['id']}")
        # Still update question_ids
        update_data = {
            "title": e["title"],
            "duration": e["duration"] or 90,
            "pass_score": e["pass_score"] or 60,
            "single_score": e["single_score"] if e["single_score"] is not None else 10,
            "multiple_score": e["multiple_score"] if e["multiple_score"] is not None else 20,
            "judgment_score": e["judgment_score"] if e["judgment_score"] is not None else 5,
            "question_ids": all_railway_q_ids,
        }
        api_put(f"/api/exams/{found_exam['id']}", update_data, token)
        print(f"    Updated question_ids to {len(all_railway_q_ids)}")
        continue

    # Get local question IDs for this exam
    eq_rows = cur.execute(
        "SELECT question_id FROM exam_question WHERE exam_id = ?", (e["id"],)
    ).fetchall()
    local_qids = sorted([question_map.get(r["question_id"]) for r in eq_rows])
    local_qids = [q for q in local_qids if q is not None]

    def get_col(row, name, default):
        v = row[name]
        return v if v is not None else default

    data = {
        "title": e["title"],
        "duration": get_col(e, "duration", 90),
        "pass_score": get_col(e, "pass_score", 60),
        "single_score": get_col(e, "single_score", 10),
        "multiple_score": get_col(e, "multiple_score", 20),
        "judgment_score": get_col(e, "judgment_score", 5),
        "question_ids": local_qids or all_railway_q_ids,  # fallback to all if no specific mapping
    }
    result, status = api_post("/api/exams", data, token)
    if status in (200, 201):
        exam_id_map[e["id"]] = result["id"]
        print(f"    [NEW] Exam '{e['title']}' (local {e['id']}) -> railway {result['id']} ({len(data['question_ids'])} questions)")

        # Now update to include ALL questions
        update_data = dict(data)
        update_data["question_ids"] = all_railway_q_ids
        api_put(f"/api/exams/{result['id']}", update_data, token)
        print(f"    Updated to {len(all_railway_q_ids)} questions")
    else:
        print(f"    [FAIL] Exam '{e['title']}': {result}")

# Distributions
print("\n[Distributions] Creating distributions...")
dists = cur.execute("SELECT * FROM exam_distributions ORDER BY id").fetchall()
dist_count = 0

for d in dists:
    if d["user_id"] == 1:  # Skip admin
        continue
    new_exam_id = exam_id_map.get(d["exam_id"])
    new_user_id = student_map.get(d["user_id"])
    if not new_exam_id:
        print(f"    [WARN] No exam mapping for local exam_id={d['exam_id']}")
        continue
    if not new_user_id:
        print(f"    [WARN] No user mapping for local user_id={d['user_id']}")
        continue

    data = {"exam_id": new_exam_id, "user_ids": [new_user_id]}
    result, status = api_post("/api/distributions", data, token)
    if status in (200, 201):
        dist_count += 1
        results = result if isinstance(result, list) else [result]
        for r in results:
            url = f"{FRONTEND}/invite/{r.get('invite_code', '')}"
            print(f"    {r.get('user_name', '?')}: {url}")
    elif status == 400:
        print(f"    [SKIP] Distribution already exists for exam={new_exam_id} user={new_user_id}")
    else:
        print(f"    [FAIL] distribution: {result}")

print(f"\n    {dist_count} distributions created/skipped.")

conn.close()

print("\n" + "=" * 60)
print("Migration Complete!")
print("=" * 60)
print(f"  Students:      {len(student_map)} mapped")
print(f"  Questions:     {len(question_map)} mapped")
print(f"  Exams:        {len(exam_id_map)} mapped")
print(f"  Distributions: {dist_count}")
print(f"\n  Railway backend: {BACKEND}")
print(f"  Railway frontend: {FRONTEND}")
print("=" * 60)
