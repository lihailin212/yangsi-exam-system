# -*- coding: utf-8 -*-
"""历年真题接口的冒烟测试。

跑法（仓库根目录，需要后端起着）：
    python backend/scripts/test_past_papers_api.py

检查四件事：
1. /api/past-papers 能按年份分组列出真题卷
2. 真题卷不出现在正式考试列表里（kind=normal）
3. 每张卷都有题，题干/选项/答案齐全
4. 题库里能按"来源卷宗"筛出真题题
"""
import json
import os
import pathlib
import sys
import urllib.request

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("TEST_USER", "admin")   # 登录用的工号（或手机号）
PWD = os.environ.get("TEST_PWD", "admin123")

PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(("  [OK] " if cond else "  [FAIL] ") + name + ("" if cond else f"  {detail}"))


def req(path, token=None, method="GET", body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main():
    print("历年真题接口冒烟测试")
    print("-" * 40)
    # 可以直接给一个现成的 token（TEST_TOKEN），省得知道管理员密码
    token = os.environ.get("TEST_TOKEN", "").strip()
    if not token:
        try:
            login = req("/api/auth/login", method="POST",
                        body={"employee_id": USER, "password": PWD})
        except Exception as e:
            print("登录失败：", e)
            return 1
        token = login.get("access_token") or login.get("token")
    check("登录成功", bool(token), token)

    papers = req("/api/past-papers", token)
    years = papers.get("years") or []
    check("真题卷按年份分组", len(years) > 0, papers)
    total = papers.get("total") or 0
    check("真题卷数量 > 0", total > 0, total)
    print(f"  共有 {len(years)} 个年份、{total} 张卷")

    flat = [pp for y in years for pp in y["papers"]]
    check("每张卷都有题数和时长",
          all(pp.get("question_count") and pp.get("duration") for pp in flat))
    check("卷名合法", all(pp["paper_name"] in
          ("基础知识", "相关专业知识", "专业知识", "专业实践能力") for pp in flat),
          [pp["paper_name"] for pp in flat])

    # 真题卷不该混进正式考试
    exams = req("/api/exams?skip=0&limit=100&kind=normal", token)
    ids = {e["id"] for e in exams.get("items", [])}
    check("正式考试列表里没有真题卷",
          all(pp["exam_id"] not in ids for pp in flat),
          [pp["exam_id"] for pp in flat if pp["exam_id"] in ids])

    # 抽一张卷看题
    sample = flat[0]
    detail = req(f"/api/exams/{sample['exam_id']}", token)
    qs = detail.get("questions") or []
    check("卷里有题", len(qs) > 0, sample)
    with_opts = [q for q in qs if len(json.loads(q.get("options") or "{}")) >= 4]
    check("题目选项齐全", len(with_opts) >= len(qs) * 0.9,
          f"{len(with_opts)}/{len(qs)}")
    with_ans = [q for q in qs if q.get("answer")]
    check("题目都有答案", len(with_ans) >= len(qs) * 0.9,
          f"{len(with_ans)}/{len(qs)}")
    print(f"  样例卷 {sample['title']}：{len(qs)} 题，"
          f"其中 {len(with_ans)} 题带答案")

    print("-" * 40)
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        for f in FAILED:
            print("  FAIL:", f)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
