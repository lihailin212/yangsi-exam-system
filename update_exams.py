"""
Update exam questions on Railway to use all migrated question IDs.
"""
import requests, json, sqlite3

BACKEND = 'https://stellar-youth-production-1591.up.railway.app'
r = requests.post(f'{BACKEND}/api/auth/login',
    json={'employee_id':'admin','password':'admin123'}, timeout=30)
token = r.json()['access_token']

def api_get(path):
    rv = requests.get(f'{BACKEND}{path}',
        headers={'Authorization':f'Bearer {token}'}, timeout=30)
    rv.raise_for_status()
    return rv.json()

def api_put(path, data):
    rv = requests.put(f'{BACKEND}{path}',
        json=data,
        headers={'Authorization':f'Bearer {token}'}, timeout=30)
    return rv.json(), rv.status_code

conn = sqlite3.connect('backend/exam.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get Railway question IDs
rq = api_get('/api/questions')
railway_qs = rq.get('items', rq) if isinstance(rq, dict) else rq
railway_q_ids = sorted([q['id'] for q in railway_qs])
print(f'Railway questions: {len(railway_q_ids)} IDs')

# Get local exam → Railway exam mapping (by title)
re = api_get('/api/exams')
railway_exams = re.get('items', re) if isinstance(re, dict) else re
local_exams = cur.execute('SELECT * FROM exams ORDER BY id').fetchall()

# Build local_title → railway_exam mapping
exam_map = {}  # local_exam_id -> railway_exam dict
for le in local_exams:
    for re_ in railway_exams:
        if le['title'] == re_['title']:
            exam_map[le['id']] = re_
            break

print('Exam mapping:')
for lid, re_ in exam_map.items():
    print(f'  local {lid} -> railway {re_["id"]} ({re_["title"]})')

# For each exam, get all question_ids and update
print('\nUpdating exams with complete question sets...')
for le in local_exams:
    if le['id'] not in exam_map:
        print(f'  [SKIP] No mapping for local exam {le["id"]}')
        continue

    re_ = exam_map[le['id']]
    # Get local exam questions
    eq_rows = cur.execute(
        'SELECT question_id FROM exam_question WHERE exam_id = ?', (le['id'],)
    ).fetchall()
    local_qids = sorted([r['question_id'] for r in eq_rows])
    print(f'\n  Exam {re_["id"]} ({le["title"]}): {len(local_qids)} local questions')

    # The Railway exam was created with partial question IDs
    # Update it with all available question IDs that match
    # Since we don't know which Railway Q IDs correspond to which local Q IDs,
    # we use ALL available Railway Q IDs (the ones migrated from this exam's questions)
    # But actually we should use ALL questions on Railway - the exam can have any of them
    all_qids = railway_q_ids

    update_data = {
        "title": le["title"],
        "duration": le["duration"] or 90,
        "pass_score": le["pass_score"] or 60,
        "single_score": le["single_score"] if le["single_score"] is not None else 10,
        "multiple_score": le["multiple_score"] if le["multiple_score"] is not None else 20,
        "judgment_score": le["judgment_score"] if le["judgment_score"] is not None else 5,
        "question_ids": all_qids,
    }
    result, status = api_put(f'/api/exams/{re_["id"]}', update_data)
    if status in (200, 201):
        print(f'  Updated: {len(all_qids)} questions assigned')
    else:
        print(f'  [FAIL] {result}')

conn.close()
print('\nDone!')
