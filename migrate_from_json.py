"""
Migrate all local data to Railway using pre-exported JSON (for reliable runs).
Run with: python migrate_from_json.py
"""
import json, sys, time

def do_migrate():
    with open('migration_data.json', encoding='utf-8') as f:
        data = json.load(f)

    BACKEND = 'https://stellar-youth-production-1591.up.railway.app'
    FRONTEND = 'https://yangsi-exam-system-production-6700.up.railway.app'

    import requests
    session = requests.Session()

    def login():
        r = session.post(f'{BACKEND}/api/auth/login', json={'employee_id': 'admin', 'password': 'admin123'}, timeout=90)
        return r.json()['access_token']

    def get(path, token, retries=3):
        for i in range(retries):
            try:
                r = session.get(f'{BACKEND}{path}', headers={'Authorization': f'Bearer {token}'}, timeout=60)
                return r.json()
            except Exception as e:
                if i < retries - 1:
                    print(f'  [RETRY] {path}: {e}')
                    time.sleep(2)
                else:
                    raise

    def post(path, data, token, retries=3):
        for i in range(retries):
            try:
                r = session.post(f'{BACKEND}{path}', json=data, headers={'Authorization': f'Bearer {token}'}, timeout=60)
                return r.json(), r.status_code
            except Exception as e:
                if i < retries - 1:
                    print(f'  [RETRY] {path}: {e}')
                    time.sleep(2)
                else:
                    raise

    sys.stdout.reconfigure(encoding='utf-8')
    print('Logging in...')
    token = login()
    print('Logged in')

    # Check existing
    rq = get('/api/questions?limit=1000', token)
    rq_items = rq.get('items', [])
    eq = {(q['content'], q['type'], q['answer']): q['id'] for q in rq_items}

    re = get('/api/exams?limit=100', token)
    re_items = re.get('items', [])
    ee = {e['title']: e['id'] for e in re_items}

    rs = get('/api/students?limit=100', token)
    rs_items = rs.get('items', [])
    es = {s['employee_id']: s['id'] for s in rs_items}

    print(f'Railway: {len(eq)} q, {len(ee)} e, {len(es)} s')

    # Students
    smap = {}
    for s in data['students']:
        emp = str(s['employee_id'])
        if emp in es:
            smap[s['id']] = es[emp]
            print(f'  [SKIP] {s["name"]}')
            continue
        res, st = post('/api/students', {'employee_id': emp, 'name': s['name'], 'password': '123456', 'dept': s['dept'] or '', 'role': s['role'] or '学员'}, token)
        if st in (200, 201):
            smap[s['id']] = res['id']
            print(f'  [NEW] {s["name"]} -> {res["id"]}')

    # Questions
    qmap = {}
    for q in data['questions']:
        key = (q['content'], q['type'], q['answer'])
        if key in eq:
            qmap[q['id']] = eq[key]
            continue
        res, st = post('/api/questions', {'type': q['type'], 'content': q['content'], 'options': q['options'], 'answer': q['answer'], 'analysis': q['analysis'] or '', 'category': q['category'] or ''}, token)
        if st in (200, 201):
            qmap[q['id']] = res['id']
            print(f'  [NEW] Q{q["id"]} -> {res["id"]}')

    all_qids = sorted(qmap.values())
    print(f'Questions: {len(qmap)} mapped, {len(all_qids)} total')

    # Exams
    emap = {}
    for e in data['exams']:
        if e['title'] in ee:
            emap[e['id']] = ee[e['title']]
            print(f'  [SKIP] {e["title"]}')
            continue
        gv = lambda row, n, d: row[n] if row[n] is not None else d
        res, st = post('/api/exams', {
            'title': e['title'],
            'duration': gv(e, 'duration', 90),
            'pass_score': gv(e, 'pass_score', 60),
            'single_score': gv(e, 'single_score', 10),
            'multiple_score': gv(e, 'multiple_score', 20),
            'judgment_score': gv(e, 'judgment_score', 5),
            'question_ids': all_qids
        }, token)
        if st in (200, 201):
            emap[e['id']] = res['id']
            print(f'  [NEW] {e["title"]} -> {res["id"]}')

    print(f'Exams: {len(emap)} mapped')

    # Distributions
    dc = 0
    for d in data['dists']:
        if d['user_id'] == 1: continue
        eid = emap.get(d['exam_id'])
        uid = smap.get(d['user_id'])
        if not eid or not uid:
            print(f'  [WARN] exam={d["exam_id"]} user={d["user_id"]}')
            continue
        res, st = post('/api/distributions', {'exam_id': eid, 'user_ids': [uid]}, token)
        if st in (200, 201):
            dc += 1
            for r in (res if isinstance(res, list) else [res]):
                print(f'  {r["user_name"]}: {FRONTEND}/#/invite/{r["invite_code"]}')
        elif st == 400:
            pass

    print(f'Distributions: {dc}')
    print('Done!')

if __name__ == '__main__':
    do_migrate()