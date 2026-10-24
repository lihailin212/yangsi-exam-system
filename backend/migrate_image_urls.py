#!/usr/bin/env python3
"""
数据库图片 URL 迁移脚本
将数据库中的绝对 URL 转换为相对路径

用法：
    python migrate_image_urls.py

迁移内容：
    - https://stellar-youth-production-1591.up.railway.app/uploads/ -> /uploads/
"""

import sqlite3
import re
import os
from datetime import datetime

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'exam.db')

# 要替换的 URL 前缀
OLD_PREFIX = 'https://stellar-youth-production-1591.up.railway.app'
NEW_PREFIX = ''  # 相对路径不需要前缀

def find_and_replace_urls(db_path):
    """扫描所有表，查找并替换绝对 URL"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 获取所有表
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    total_updates = 0
    changes = []

    for (table_name,) in tables:
        # 获取表的列信息
        columns = cur.execute(f"PRAGMA table_info({table_name})").fetchall()

        for col in columns:
            col_name = col[1]
            # 跳过主键和索引列
            if col_name in ('id', 'rowid'):
                continue

            try:
                # 查找包含旧 URL 的行
                query = f"""
                    SELECT rowid, {col_name}
                    FROM {table_name}
                    WHERE {col_name} LIKE '%{OLD_PREFIX}%'
                """
                rows = cur.execute(query).fetchall()

                for rowid, content in rows:
                    if content and OLD_PREFIX in str(content):
                        # 替换 URL
                        new_content = str(content).replace(OLD_PREFIX, NEW_PREFIX)
                        # 更新数据库
                        update_query = f"UPDATE {table_name} SET {col_name} = ? WHERE rowid = ?"
                        cur.execute(update_query, (new_content, rowid))

                        changes.append({
                            'table': table_name,
                            'column': col_name,
                            'rowid': rowid
                        })
                        total_updates += 1

            except Exception as e:
                # 某些列可能是数字类型，跳过
                continue

    conn.commit()
    conn.close()

    return total_updates, changes

def main():
    if not os.path.exists(DB_PATH):
        print(f"错误：数据库文件不存在: {DB_PATH}")
        return

    print(f"数据库路径: {DB_PATH}")
    print(f"将替换: {OLD_PREFIX}/uploads/")
    print(f"替换为: /uploads/")
    print("-" * 50)

    # 备份数据库
    backup_path = f"{DB_PATH}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    print(f"数据库已备份到: {backup_path}")
    print("-" * 50)

    # 执行替换
    total_updates, changes = find_and_replace_urls(DB_PATH)

    if total_updates == 0:
        print("未发现需要迁移的绝对 URL，数据库已是最新。")
    else:
        print(f"迁移完成！共更新 {total_updates} 处 URL：")
        for change in changes:
            print(f"  - 表: {change['table']}, 列: {change['column']}, 行ID: {change['rowid']}")

        print("-" * 50)
        print("注意：请重启后端服务使更改生效。")

if __name__ == '__main__':
    main()
