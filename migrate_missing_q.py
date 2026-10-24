"""Migrate remaining questions to Railway."""
import json, sqlite3, subprocess

BACKEND = "https://stellar-youth-production-1591.up.railway.app"
FRONTEND = "https://yangsi-exam-system-production-6700.up.railway.app"

def curl_req(method, path, data=None):
    if data is not None:
        tmp = 'd:/opencodeli/exam-system-mr/_tmp_body.json'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        args = ['curl', '-s', f'{BACKEND}{path}', '-X', method,
            '-H', f'Authorization: Bearer {token}',
            '-H', 'Content-Type: application/json',
            '--data-binary', '@' + tmp]
    else:
        args = ['curl', '-s', f'{BACKEND}{path}', '-X', method,
            '-H', f'Authorization: Bearer {token}']
    proc = subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace')
    raw = proc.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except:
        print(f"  Raw response: {raw[:200]}")
        raise

# Login
login_json = json.dumps({"employee_id":"admin","password":"admin123"})
proc = subprocess.run(['curl', '-s', f'{BACKEND}/api/auth/login', '-X', 'POST',
    '-H', 'Content-Type: application/json', '-d', login_json],
    capture_output=True, encoding='utf-8', errors='replace')
raw = proc.stdout.strip()
if not raw:
    print(f"Login failed, raw: {proc.stderr}")
    raise Exception("Login failed")
token = json.loads(raw)['access_token']
print(f"Logged in")

# Get existing Railway questions
rq = curl_req('GET', '/api/questions?limit=1000')
rq_items = rq.get('items', [])
eq = {(q['content'][:50], q['type'], q['answer']): q['id'] for q in rq_items}
print(f"Railway already has {len(eq)} questions")

conn = sqlite3.connect('backend/exam.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Missing question IDs
missing_ids = [1, 13, 15, 16, 17, 18, 29]
lqs = cur.execute('SELECT * FROM questions WHERE id IN ({})'.format(
    ','.join(map(str, missing_ids)))).fetchall()
print(f"Migrating {len(lqs)} questions...")

qmap = {}
for q in lqs:
    key = (q['content'][:50], q['type'], q['answer'])
    if key in eq:
        qmap[q['id']] = eq[key]
        print(f"  [SKIP] Q{q['id']} already exists")
        continue
    data = {
        "type": q['type'],
        "content": q['content'],
        "options": q['options'] or "{}",
        "answer": q['answer'],
        "analysis": q['analysis'] or "",
        "category": q['category'] or ""
    }
    result = curl_req('POST', '/api/questions', data)
    if 'id' in result:
        qmap[q['id']] = result['id']
        print(f"  [NEW] Q{q['id']} -> {result['id']}")
    else:
        print(f"  [FAIL] Q{q['id']}: {result}")

print(f"\nMigrated {len(qmap)} questions")
conn.close()
