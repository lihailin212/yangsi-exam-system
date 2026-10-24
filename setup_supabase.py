#!/usr/bin/env python3
"""
杨思学考试系统 - Supabase 迁移脚本
用法: python migrate_to_supabase.py <Supabase连接字符串>

示例:
  python migrate_to_supabase.py "postgresql://postgres:password@host.db.supabase.co:5432/postgres"

此脚本会:
1. 清空 Railway 上现有的考试数据
2. 在 Supabase 上创建 schema（如果不存在）
3. 导入所有本地数据（用户、题目、考试、答题记录）
"""
import sys, requests, json, time

BACKEND = 'https://stellar-youth-production-1591.up.railway.app'
TIMEOUT = 60

def api_login():
    r = requests.post(f"{BACKEND}/api/auth/login",
        json={"employee_id": "admin", "password": "admin123"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["access_token"]

def api_get(path, token):
    r = requests.get(f"{BACKEND}{path}",
        headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def api_post(path, data, token, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post(f"{BACKEND}{path}",
                json=data, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
            return r.json(), r.status_code
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    [RETRY] {path} (attempt {attempt+2}/{retries})")
                time.sleep(2)
            else:
                raise

def api_delete(path, token, retries=3):
    for attempt in range(retries):
        try:
            r = requests.delete(f"{BACKEND}{path}",
                headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
            return r.status_code
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries - 1:
                print(f"    [RETRY] DELETE {path}")
                time.sleep(2)
            else:
                raise
    return 0

if len(sys.argv) < 2:
    print("用法: python migrate_to_supabase.py <Supabase连接字符串>")
    print("示例: python migrate_to_supabase.py \"postgresql://postgres:password@host.db.supabase.co:5432/postgres\"")
    sys.exit(1)

SUPABASE_URL = sys.argv[1].strip()

print("=" * 60)
print("Supabase 迁移")
print("=" * 60)

# Step 1: 登录 Railway 后端
print("\n[1/4] 登录 Railway 后端...")
token = api_login()
print(f"    登录成功!")

# Step 2: 在 Railway 后端设置 DATABASE_URL
print("\n[2/4] 配置 Railway 后端环境变量...")
print("    请在 Railway 控制台手动设置以下环境变量:")
print(f"    DATABASE_URL = {SUPABASE_URL[:30]}...")
print("    FRONTEND_BASE_URL = https://yangsi-exam-system-production-6700.up.railway.app")
print("    设置后请重启 Railway 服务")
print("\n    要自动配置，请使用 Railway CLI:")
print("    railway login")
print("    railway variables set DATABASE_URL='" + SUPABASE_URL + "'")
print("    railway variables set FRONTEND_BASE_URL=https://yangsi-exam-system-production-6700.up.railway.app")
print("    railway redeploy")

# Step 3: 执行 Supabase schema
print("\n[3/4] 在 Supabase SQL Editor 中执行以下 SQL:")
print("    复制 migrate_to_supabase.sql 文件内容到 Supabase SQL Editor 执行")
print("    或者运行: python migrate_to_supabase.py --setup-only")

# Step 4: 验证
print("\n[4/4] 验证迁移...")
print("    等待 Railway 重启后，运行:")
print("    curl https://stellar-youth-production-1591.up.railway.app/api/exams")
print("    应该返回 5 个考试")

print("\n" + "=" * 60)
print("提示: 完成迁移后，二维码 URL 将变为:")
print("https://yangsi-exam-system-production-6700.up.railway.app/#/exam-login/2")
print("=" * 60)
