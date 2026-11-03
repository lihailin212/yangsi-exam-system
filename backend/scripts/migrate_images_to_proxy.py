# -*- coding: utf-8 -*-
"""把题库里指向对象存储的绝对图片地址改成走后端代理的相对地址。

为什么：对象存储（Supabase）在境外，医院内网/部分运营商出口连不上，
浏览器直接取图就裂成破图。改成 /api/images/<文件名> 之后，
浏览器只跟后端要图，后端再从对象存储转发，客户端通不通对象存储都不影响。

改的是这几处：
- questions.content / analysis / options 里的 <img src="...">
- system_settings.logo_url（登录页和侧边栏的 Logo）

幂等：已经是 /api/images/ 开头的不会再动，可以反复跑。
回滚：python backend/scripts/migrate_images_to_proxy.py --revert
"""
import pathlib
import re
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.db import connect  # noqa: E402

# 字符类里用 \x22 \x27 表示引号，免得正则里的引号把 Python 字符串截断
_QUOTE = r'\x22\x27'
_EXT = r'(?:jpg|jpeg|png|webp|gif|bmp)'

# https://<host>/storage/v1/object/public/<bucket>/images/<name>
_PAT_SUPABASE = re.compile(
    r'https?://[^\s' + _QUOTE + r'<>)]*?/storage/v1/object/public/[^\s' + _QUOTE + r'<>)]*?/images/((?:[\w.\-]+/)*[\w.\-]+\.' + _EXT + r')',
    re.I)
# https://<host>.public.blob.vercel-storage.com/images/<name>
_PAT_BLOB = re.compile(
    r'https?://[^\s' + _QUOTE + r'<>)]*?\.public\.blob\.vercel-storage\.com/images/((?:[\w.\-]+/)*[\w.\-]+\.' + _EXT + r')',
    re.I)

PROXY_PREFIX = '/api/images/'
_PROXY_RE = re.compile(r'/api/images/((?:[\w.\-]+/)*[\w.\-]+\.' + _EXT + r')', re.I)


def to_proxy(text):
    """把绝对图片地址换成代理相对地址，返回 (新文本, 命中次数)。"""
    if not text:
        return text, 0
    hits = 0

    def repl(m):
        nonlocal hits
        hits += 1
        return PROXY_PREFIX + m.group(1)

    text = _PAT_SUPABASE.sub(repl, text)
    text = _PAT_BLOB.sub(repl, text)
    return text, hits


def to_absolute(text, sample_url):
    """回滚：把 /api/images/xxx 换回样例给出的绝对地址。"""
    if not text:
        return text, 0
    prefix = sample_url.rsplit('/', 1)[0] + '/'
    hits = 0

    def repl(m):
        nonlocal hits
        hits += 1
        return prefix + m.group(1)

    return _PROXY_RE.sub(repl, text), hits


def main():
    revert = '--revert' in sys.argv
    conn = connect()
    cur = conn.cursor()

    # 找一个样例绝对地址，回滚时照着拼
    cur.execute("SELECT content FROM questions WHERE content LIKE '%supabase.co%' LIMIT 1")
    row = cur.fetchone()
    sample = ''
    if row:
        m = re.search(r'https?://\S+?\.(?:jpg|jpeg|png|webp|gif)', row[0] or '')
        if m:
            sample = m.group(0)

    total = 0
    if revert:
        if not sample:
            print('[迁移] 找不到样例地址，无法回滚')
            conn.close()
            return
        for col in ('content', 'analysis', 'options'):
            cur.execute(f"SELECT id, {col} FROM questions WHERE {col} LIKE '%/api/images/%'")
            for rid, val in cur.fetchall():
                new, hits = to_absolute(val, sample)
                if hits:
                    cur.execute(f'UPDATE questions SET {col} = %s WHERE id = %s', (new, rid))
                    total += hits
        cur.execute("SELECT key, value FROM system_settings WHERE value LIKE '%/api/images/%'")
        for key, val in cur.fetchall():
            new, hits = to_absolute(val, sample)
            if hits:
                cur.execute('UPDATE system_settings SET value = %s WHERE key = %s', (new, key))
                total += hits
    else:
        for col in ('content', 'analysis', 'options'):
            cur.execute(
                f"SELECT id, {col} FROM questions WHERE {col} LIKE '%supabase.co%' OR {col} LIKE '%vercel-storage.com%'")
            for rid, val in cur.fetchall():
                new, hits = to_proxy(val)
                if hits:
                    cur.execute(f'UPDATE questions SET {col} = %s WHERE id = %s', (new, rid))
                    total += hits
        cur.execute("SELECT key, value FROM system_settings WHERE value LIKE '%supabase.co%' OR value LIKE '%vercel-storage.com%'")
        for key, val in cur.fetchall():
            new, hits = to_proxy(val)
            if hits:
                cur.execute('UPDATE system_settings SET value = %s WHERE key = %s', (new, key))
                total += hits

    conn.commit()
    print(f'[迁移] 共处理 {total} 处图片地址'
          + ('（已回滚为绝对地址）' if revert else '（已改为 /api/images/ 代理地址）'))

    cur.execute("SELECT COUNT(*) FROM questions WHERE content LIKE '%/api/images/%' OR analysis LIKE '%/api/images/%'")
    print(f'[迁移] 现在走代理的题目图片数: {cur.fetchone()[0]}')
    conn.close()


if __name__ == '__main__':
    main()
