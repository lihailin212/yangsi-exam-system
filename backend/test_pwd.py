import sqlite3
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

conn = sqlite3.connect('exam.db')
cur = conn.cursor()
cur.execute('SELECT id, employee_id, name, password_hash FROM users WHERE id > 1')
rows = cur.fetchall()

test_passwords = [
    '123456', '12345678', 'password', '123456789',
    '1234567', '123123', 'password123', '1234567890',
    '1234', '000000', '123456a', 'abc123'
]

found = False
for pwd in test_passwords:
    for r in rows:
        if pwd_ctx.verify(pwd, r[3]):
            print(f"  密码 [{pwd}] 匹配: {r[2]}({r[1]})")
            found = True

if not found:
    print("  未找到常见默认密码")
    print("  建议：为考生重置密码")

conn.close()
