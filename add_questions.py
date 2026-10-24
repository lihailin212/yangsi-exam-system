import json
import random
import urllib.request

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzc2NDI1MTY0fQ.l9HEVsoRC1Lyol80P4xyQCVCR39fZo9Px03jOVAlpEQ"
BASE_URL = "http://localhost:8000"

url_map = {
    "多分叶中性粒细胞": "/uploads/images/20260416_bb049a1737a6404983a174e04672c338.jpg",
    "巨大血小板": "/uploads/images/20260416_29b8bbe7b4c143c9a48a8b5716022391.png",
    "异型淋巴细胞": "/uploads/images/20260416_b8c4196dbf73493eac3c6b5bd81e2729.png",
    "异常早幼粒细胞": "/uploads/images/20260416_c729169f91f8418d89a9f917535a037d.jpg",
    "浆细胞": "/uploads/images/20260416_eb20c08a30e94a3fa258ad2fc2db0e9f.jpg",
    "绦虫卵": "/uploads/images/20260416_8f1963f736de4a42b91155012850c2b1.jpg",
    "肝吸虫卵": "/uploads/images/20260416_b4f44f4f0e0c4441b72f056ebea01f25.jpg",
    "钩虫卵": "/uploads/images/20260416_d17fbba341254645a23c9ddd03b1b0ba.png",
    "颗粒管型": "/uploads/images/20260416_03be4780be7246b89f9acb28699a6da1.png",
}

cells = list(url_map.keys())
random.seed(42)

success = 0
for i, correct in enumerate(cells):
    correct_pos = random.choice(['A', 'B', 'C', 'D'])
    others = [c for c in cells if c != correct]
    wrong_options = random.sample(others, 3)

    opts = {}
    positions = ['A', 'B', 'C', 'D']
    idx = positions.index(correct_pos)
    opts['A'] = ''
    opts['B'] = ''
    opts['C'] = ''
    opts['D'] = ''
    opts[correct_pos] = correct

    cnt = 0
    for pos in positions:
        if pos != correct_pos:
            opts[pos] = wrong_options[cnt]
            cnt += 1

    content = f'<p>请选择下图所示细胞名称</p><img src="{url_map[correct]}" style="width:50%" />'

    payload = {
        "type": "single",
        "content": content,
        "options": json.dumps(opts, ensure_ascii=False),
        "answer": correct_pos,
        "analysis": "",
        "category": "形态学/细胞形态学"
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f"{BASE_URL}/api/questions",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f"OK {i+1}: {correct} -> {correct_pos} | A={opts['A']} B={opts['B']} C={opts['C']} D={opts['D']}")
            success += 1
    except Exception as e:
        print(f"FAIL {i+1}: {correct} -> {e}")

print(f"\nDone! {success}/9 questions created")
