#!/usr/bin/env python3
"""
批量从图片创建题目脚本

用法：
    python batch_create_questions.py

功能：
    - 扫描指定文件夹中的所有图片
    - 为每张图片创建一道单选题
    - 题干：文字描述 + 图片
    - 选项：正确答案 + 3个随机干扰项
    - 自动分类（根据子文件夹名称）
"""

import os
import sys
import json
import random
import shutil
import sqlite3
from datetime import datetime

# ============== 配置 ==============
# 图片源文件夹
SOURCE_DIR = r"D:\desktop\室间、飞行形态学图片\室间、飞行形态学图片"

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 图片目标目录（相对于项目根目录）
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "images")

# 数据库路径
DB_PATH = os.path.join(PROJECT_ROOT, "exam.db")

# 题干模板
QUESTION_TEMPLATE = "请选择下图所示细胞名称："

# 分类映射（根据文件夹名称）
CATEGORY_MAP = {
    "血片": "形态学/血细胞形态学",
    "血细胞": "形态学/血细胞形态学",
    "尿沉渣": "形态学/尿沉渣形态学",
    "寄生虫": "形态学/寄生虫形态学",
    "其他体液": "形态学/其他形态学",
    "2020": "形态学/血细胞形态学",
    "2021": "形态学/血细胞形态学",
    "2022": "形态学/血细胞形态学",
    "2023": "形态学/血细胞形态学",
    "2024": "形态学/血细胞形态学",
    "2025": "形态学/血细胞形态学",
}

# ============== 主程序 ==============

def get_category_from_path(filepath):
    """根据文件路径确定分类"""
    for key, category in CATEGORY_MAP.items():
        if key in filepath:
            return category
    return "形态学/其他形态学"


def scan_images(directory):
    """扫描所有图片文件"""
    images = []
    extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')

    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(extensions):
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, directory)
                images.append({
                    'filename': filename,
                    'filepath': filepath,
                    'rel_path': rel_path,
                    'category': get_category_from_path(filepath)
                })

    return images


def copy_image_to_uploads(image_info):
    """复制图片到 uploads 目录"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = image_info['filename']
    source = image_info['filepath']

    # 生成唯一文件名（加时间戳避免重复）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name, ext = os.path.splitext(filename)
    new_filename = f"{timestamp}_{name}{ext}"
    dest = os.path.join(UPLOAD_DIR, new_filename)

    # 复制文件
    shutil.copy2(source, dest)

    return f"/uploads/images/{new_filename}"


def generate_options(correct_answer, all_names, count=4):
    """生成选项，A为正确答案，其余为干扰项"""
    # 清理文件名作为选项文字（去掉扩展名）
    correct_option = os.path.splitext(correct_answer)[0]

    # 获取所有其他名称作为干扰项
    other_names = [os.path.splitext(n)[0] for n in all_names if n != correct_answer]
    random.shuffle(other_names)

    # 确保有足够的干扰项
    if len(other_names) < count - 1:
        # 如果干扰项不够，重复使用一些
        while len(other_names) < count - 1:
            other_names.extend([os.path.splitext(n)[0] for n in all_names[:count-1] if os.path.splitext(n)[0] != correct_option])
            other_names = list(set(other_names))

    # 取前 count-1 个干扰项
    distractors = other_names[:count - 1]

    # 构建选项字典
    options = {'A': correct_option}
    for i, d in enumerate(distractors):
        key = chr(ord('B') + i)
        options[key] = d

    # 打乱选项顺序（但记录正确答案位置）
    correct_key = [k for k, v in options.items() if v == correct_option][0]

    # 随机打乱
    keys = list(options.keys())
    random.shuffle(keys)
    shuffled_options = {k: options[k] for k in keys}

    # 返回打乱后的选项和正确答案
    return shuffled_options, correct_key


def create_question(conn, image_info, all_filenames):
    """创建一道题目"""
    # 复制图片并获取URL
    image_url = copy_image_to_uploads(image_info)

    # 生成题干（HTML格式）
    content = f"""<p>{QUESTION_TEMPLATE}</p>
<img src="{image_url}" alt="image" style="max-width: 50%;" />"""

    # 生成选项
    options, correct_answer = generate_options(image_info['filename'], all_filenames)

    # 转换为JSON
    options_json = json.dumps(options, ensure_ascii=False)

    # 插入数据库
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO questions (type, content, options, answer, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        'single',
        content,
        options_json,
        correct_answer,
        image_info['category'],
        datetime.now().isoformat()
    ))

    return cursor.lastrowid


def main():
    print("=" * 50)
    print("批量创建题目脚本")
    print("=" * 50)

    # 检查源目录
    if not os.path.exists(SOURCE_DIR):
        print(f"错误：图片源目录不存在: {SOURCE_DIR}")
        return

    # 创建目标目录
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 扫描图片
    print(f"\n正在扫描图片目录: {SOURCE_DIR}")
    images = scan_images(SOURCE_DIR)
    print(f"共找到 {len(images)} 张图片")

    if len(images) == 0:
        print("未找到任何图片文件！")
        return

    # 获取所有文件名（用于生成干扰选项）
    all_filenames = [img['filename'] for img in images]

    # 连接数据库
    print(f"\n正在连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    # 统计已存在的题目数量
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions WHERE category LIKE '形态学/%'")
    existing_count = cursor.fetchone()[0]
    print(f"数据库中现有形态学题目: {existing_count} 道")

    # 自动确认（跳过交互式确认）
    print(f"\n将为 {len(images)} 张图片创建 {len(images)} 道单选题")
    print("自动开始创建...")

    # 创建题目
    print("\n正在创建题目...")
    success_count = 0
    error_count = 0

    for i, image_info in enumerate(images, 1):
        try:
            question_id = create_question(conn, image_info, all_filenames)
            success_count += 1

            if i % 10 == 0 or i == len(images):
                print(f"  进度: {i}/{len(images)}", end='\r')

        except Exception as e:
            error_count += 1
            print(f"\n  创建题目失败: {image_info['filename']}, 错误: {e}")

    # 提交更改
    conn.commit()
    conn.close()

    # 完成
    print("\n" + "=" * 50)
    print("完成！")
    print(f"  成功创建: {success_count} 道题目")
    print(f"  失败: {error_count} 道")
    print(f"  图片已复制到: {UPLOAD_DIR}")
    print("=" * 50)

    # 提示用户需要重启后端
    print("\n提示：请重启后端服务使新题目生效")


if __name__ == '__main__':
    main()
