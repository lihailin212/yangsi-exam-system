import json
import re
import io
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas, models
from .. import paper as paper_lib
from ..auth import get_current_user, require_admin
from ..storage import upload_image_bytes

router = APIRouter(prefix="/api/questions", tags=["questions"])

def _resolve_image_for_export(img_url: str):
    """把题目中的图片地址解析为本地可读文件路径（供 Excel 内嵌图片）。
    支持 Blob 公网 URL（下载到临时目录）与本地磁盘路径。"""
    import tempfile
    import urllib.request

    if not img_url:
        return None

    if img_url.startswith("http://") or img_url.startswith("https://"):
        try:
            suffix = os.path.splitext(img_url.split("?")[0])[1] or ".png"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as out:
                with urllib.request.urlopen(img_url, timeout=30) as resp:
                    out.write(resp.read())
            return tmp_path
        except Exception as e:
            print(f"下载图片失败 {img_url}: {e}")
            return None

    base = os.environ.get(
        "RAILWAY_VOLUME_MOUNT_PATH",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    img_path = os.path.join(base, "uploads", "images", os.path.basename(img_url))
    return img_path if os.path.exists(img_path) else None

@router.get("")
def list_questions(skip: int = 0, limit: int = 20, type: str = "", search: str = "", category: str = "",
                   db: Session = Depends(get_db), _=Depends(require_admin)):
    items, total = crud.get_questions(db, skip=skip, limit=limit, q_type=type, search=search, category=category)
    return {"items": [schemas.QuestionOut.model_validate(q) for q in items], "total": total}

# 考生自学 - 获取题目列表（只需登录即可）
@router.get("/study")
def study_questions(
    skip: int = 0,
    limit: int = 100,
    type: str = "",
    category: str = "",
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    """获取用于自学的题目（不包含答案）"""
    # 处理形态学父级筛选
    if category == "形态学/":
        # 筛选所有形态学分类的题目
        query = db.query(models.Question).filter(models.Question.category.like('形态学/%'))
        if type:
            query = query.filter(models.Question.type == type)
        total = query.count()
        items = query.offset(skip).limit(limit).all()
    else:
        items, total = crud.get_questions(db, skip=skip, limit=limit, q_type=type, search="", category=category)

    # 移除答案和解析，只返回题目信息
    result = []
    for q in items:
        result.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
            "options": q.options,
            "category": q.category,
        })
    return {"items": result, "total": total}

# 获取单题详情（包含答案和解析，用于自学时点击查看）
@router.get("/study/{question_id}")
def study_question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """获取题目详情（包含答案和解析）"""
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    result = {
        "id": q.id,
        "type": q.type,
        "content": q.content,
        "options": q.options,
        "answer": q.answer,
        "analysis": q.analysis,
        "category": q.category,
    }
    # 该题若正在某场考试中使用，不对考生公开答案，防止通过自学功能查答案
    if not current_user.is_admin:
        now = datetime.utcnow()
        in_active_exam = db.query(models.exam_question.c.exam_id).join(
            models.Exam, models.exam_question.c.exam_id == models.Exam.id
        ).filter(
            models.exam_question.c.question_id == question_id,
            models.Exam.start_time <= now,
            models.Exam.end_time >= now
        ).first()
        if in_active_exam:
            result["answer"] = ""
            result["analysis"] = ""
    return result

@router.post("", response_model=schemas.QuestionOut)
def create_question(q_in: schemas.QuestionCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return crud.create_question(db, q_in)

@router.put("/{question_id}", response_model=schemas.QuestionOut)
def update_question(question_id: int, q_in: schemas.QuestionUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    q = crud.update_question(db, question_id, q_in)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    return q

@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    crud.delete_question(db, question_id)
    return {"ok": True}

@router.post("/import")
async def import_questions(file: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(require_admin)):
    content = await file.read()
    filename = file.filename.lower()
    questions = []
    
    type_map_reverse = {"单选题": "single", "多选题": "multiple", "判断题": "judgment", "单选": "single", "多选": "multiple", "判断": "judgment",
                       "填空题": "fill", "填空": "fill", "fill": "fill"}

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # 跳过表头
            if not row[0]:
                continue
            
            q_type_raw = str(row[0] or "single").strip()
            q_type = type_map_reverse.get(q_type_raw, q_type_raw if q_type_raw in ("single", "multiple", "judgment", "fill") else "single")
            
            content_text = str(row[1] or "").strip()
            options_str = str(row[2] or "").strip()
            answer = str(row[3] or "").strip()
            analysis = str(row[4] or "").strip()
            # 注意：分值现在在考试层面设置，这里忽略导入的分值字段
            # score = int(row[5]) if row[5] and str(row[5]).isdigit() else 10
            category = str(row[6] or "").strip() if len(row) > 6 else ""
            img_paths = str(row[7] or "").strip() if len(row) > 7 else ""
            
            if img_paths:
                content_html = f"<p>{content_text}</p>"
                for img_path in img_paths.split("\n"):
                    img_path = img_path.strip()
                    if img_path:
                        content_html += f'<img src="{img_path}" alt="image" style="max-width: 50%;" />'
                content_text = content_html
            
            options = _parse_options(options_str)
            questions.append({
                "type": q_type,
                "content": content_text,
                "options": json.dumps(options, ensure_ascii=False),
                "answer": answer,
                "analysis": analysis,
                "category": category
            })

    elif filename.endswith(".txt") or filename.endswith(".csv"):
        text = content.decode("utf-8-sig")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 6)
            if len(parts) < 4:
                continue
            q_type_raw = parts[0].strip()
            q_type = type_map_reverse.get(q_type_raw, q_type_raw if q_type_raw in ("single", "multiple", "judgment", "fill") else "single")
            content_text = parts[1].strip()
            options_str = parts[2].strip() if len(parts) > 2 else ""
            answer = parts[3].strip() if len(parts) > 3 else ""
            analysis = parts[4].strip() if len(parts) > 4 else ""
            # 注意：分值现在在考试层面设置，这里忽略导入的分值字段
            # score = int(parts[5].strip()) if len(parts) > 5 and parts[5].strip().isdigit() else 10
            category = parts[6].strip() if len(parts) > 6 else ""
            options = _parse_options(options_str)
            questions.append({"type": q_type, "content": content_text, "options": json.dumps(options, ensure_ascii=False),
                               "answer": answer, "analysis": analysis, "category": category})
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 xlsx/xls/txt/csv")

    count = crud.bulk_create_questions(db, questions)
    return {"imported": count}

def _parse_options(options_str: str) -> dict:
    """解析 'A:选项1|B:选项2' 格式"""
    result = {}
    if not options_str:
        return result
    for part in options_str.split("|"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            result[k.strip()] = v.strip()
    return result

@router.get("/export")
async def export_questions(type: str = "", search: str = "", category: str = "",
                          db: Session = Depends(get_db), _=Depends(require_admin)):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.drawing.image import Image as XLImage
    
    items, _ = crud.get_questions(db, skip=0, limit=10000, q_type=type, search=search, category=category)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "题目导出"
    
    headers = ["题型", "题目内容", "选项", "答案", "解析", "分类", "图片路径"]
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    type_map = {"single": "单选题", "multiple": "多选题", "judgment": "判断题", "fill": "填空题"}
    
    for row_idx, q in enumerate(items, 2):
        q_type = type_map.get(q.type, q.type)
        content_html = q.content or ""
        
        img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_html)
        img_display = "\n".join(img_urls) if img_urls else ""
        
        plain_text = re.sub(r'<[^>]+>', '', content_html).strip()
        
        try:
            options = json.loads(q.options) if q.options else {}
            options_str = "|".join([f"{k}:{v}" for k, v in options.items()])
        except:
            options_str = q.options or ""
        
        answer = q.answer or ""
        analysis = q.analysis or ""
        cat = q.category or ""

        ws.cell(row=row_idx, column=1, value=q_type)
        ws.cell(row=row_idx, column=2, value=plain_text)
        ws.cell(row=row_idx, column=3, value=options_str)
        ws.cell(row=row_idx, column=4, value=answer)
        ws.cell(row=row_idx, column=5, value=analysis)
        ws.cell(row=row_idx, column=6, value=cat)
        ws.cell(row=row_idx, column=7, value=img_display)

        img_row = row_idx + 1
        for img_url in img_urls:
            try:
                img_path = _resolve_image_for_export(img_url)
                if img_path:
                    img = XLImage(img_path)
                    img.width = 300
                    img.height = 200
                    ws.add_image(img, f'B{img_row}')
                    ws.row_dimensions[img_row].height = 130
                    break
            except Exception as e:
                print(f"Error: {e}")
                pass
    
    for col in range(1, 8):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20
    
    ws.column_dimensions['B'].width = 50
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=questions_export.xlsx"}
    )


# ---- 分类管理接口 ----

@router.get("/categories")
def list_categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """获取所有分类及其题目数量"""
    return crud.get_all_categories(db)


@router.post("/categories")
def create_category_endpoint(data: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    """创建新分类"""
    category_name = data.get("name", "").strip()
    if not category_name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    success = crud.create_category(db, category_name)
    if not success:
        raise HTTPException(status_code=400, detail="分类名称已存在")
    return {"ok": True}


@router.put("/categories/rename")
def rename_category_endpoint(data: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    """重命名分类"""
    old_name = data.get("old_name", "").strip()
    new_name = data.get("new_name", "").strip()
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    if old_name == new_name:
        return {"ok": True}
    # 检查新名称是否已存在
    existing = crud.get_all_categories(db)
    if any(c["name"] == new_name for c in existing):
        raise HTTPException(status_code=400, detail="分类名称已存在")
    crud.rename_category(db, old_name, new_name)
    return {"ok": True}


@router.delete("/categories/{category_name:path}")
def delete_category_endpoint(category_name: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    """删除分类（仅当无题目时）"""
    # URL decode category_name
    from urllib.parse import unquote
    category_name = unquote(category_name)
    categories = crud.get_all_categories(db)
    category = next((c for c in categories if c["name"] == category_name), None)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    if category["count"] > 0:
        raise HTTPException(status_code=400, detail="该分类下还有题目，无法删除")
    # 由于没有独立的分类表，且该分类下无题目，直接返回成功
    # 实际删除逻辑：将所有该分类的题目（应该为0个）的 category 设为空
    crud.rename_category(db, category_name, "")
    return {"ok": True}


@router.post("/random")
def random_questions(data: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    """按规则随机抽题。

    两种写法都能用：
    1) 规则式（推荐）：
       {"rules": [{"category": "血细胞", "type": "single", "count": 5},
                  {"category": "尿沉渣", "type": "", "count": 3}]}
       category 可以写亚类别短名（血细胞/尿沉渣/寄生虫/其他体液）、
       完整分类名（形态学/血细胞形态学）或关键字（形态学）；
       type 留空表示不限题型（single/multiple/judgment/fill）。
    2) 老写法：{"single": 5, "multiple": 3, "judgment": 2, "fill": 10}
       相当于按题型各抽若干道。

    返回: {"question_ids": [...], "questions": [...], "rules": [...]}
    """
    import random

    rules = []
    raw_rules = data.get("rules")
    if isinstance(raw_rules, list) and raw_rules:
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            try:
                count = int(item.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if count <= 0:
                continue
            category = (item.get("category") or "").strip()
            categories = item.get("categories")
            if not isinstance(categories, list):
                categories = paper_lib.resolve_categories(db, category) if category else None
            rules.append({
                "category": category,
                "categories": categories,
                "type": paper_lib.normalize_type(item.get("type")),
                "count": count,
            })
    else:
        for t in ("single", "multiple", "judgment", "fill"):
            try:
                count = int(data.get(t) or 0)
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                rules.append({"category": "", "categories": None,
                              "type": t, "count": count})

    if not rules:
        raise HTTPException(status_code=400, detail="请至少设置一条抽题规则")

    result_ids = []
    used = set()
    details = []
    for rule in rules:
        pool = [q.id for q in paper_lib.pool_questions(db, rule) if q.id not in used]
        if len(pool) < rule["count"]:
            desc = rule["category"] or "全部分类"
            if rule["type"]:
                desc += " · " + paper_lib.TYPE_LABELS.get(rule["type"], rule["type"])
            raise HTTPException(
                status_code=400,
                detail="「%s」题库不足，需要 %d 道，实际只有 %d 道" % (
                    desc, rule["count"], len(pool)))
        picked = random.sample(pool, rule["count"])
        used.update(picked)
        result_ids.extend(picked)
        details.append({
            "category": rule["category"],
            "type": rule["type"],
            "count": rule["count"],
            "pool": len(pool),
            "picked": picked,
        })

    # 查询选中题目的详细信息（用于前端显示）
    selected_questions = db.query(models.Question.id, models.Question.type).filter(
        models.Question.id.in_(result_ids)
    ).all()
    types = {q.id: q.type for q in selected_questions}

    return {
        "question_ids": result_ids,
        "questions": [{"id": q.id, "type": types.get(q.id)} for q in selected_questions],
        "rules": details,
    }


@router.post("/batch-create-from-images")
def batch_create_from_images(data: dict, db: Session = Depends(get_db), _=Depends(require_admin)):
    """批量从本地文件夹图片创建单选题
    请求体: {"folderPath": "D:\\images\\folder"}
    每张图片文件名（去掉扩展名）作为正确答案，其他图片名作为干扰项
    """
    import shutil
    import os as _os
    import random
    import json as _json
    from datetime import datetime

    folder_path = data.get("folderPath", "").strip()
    if not folder_path or not _os.path.exists(folder_path):
        raise HTTPException(status_code=400, detail="文件夹路径无效或不存在")

    extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    images = []
    for root, dirs, files in _os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith(extensions):
                images.append(filename)

    if len(images) == 0:
        raise HTTPException(status_code=400, detail="文件夹中未找到图片文件")

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

    def get_category(fp):
        for key, cat in CATEGORY_MAP.items():
            if key in fp:
                return cat
        return "形态学/其他形态学"

    upload_dir = _os.path.join(_os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "images")
    try:
        _os.makedirs(upload_dir, exist_ok=True)
    except OSError:
        pass  # 生产环境只读文件系统，图片统一存 Blob

    def generate_options(correct_filename, all_filenames):
        correct_name = _os.path.splitext(correct_filename)[0]
        other_names = [_os.path.splitext(n)[0] for n in all_filenames if n != correct_filename]
        _random.shuffle(other_names)
        if len(other_names) < 3:
            others = list(set(other_names + [_os.path.splitext(n)[0] for n in all_filenames[:10]]))
            _random.shuffle(others)
            other_names = others
        distractors = other_names[:3]
        # A/B/C/D 固定顺序，正确答案随机分配到其中一个
        correct_key = _random.choice(['A', 'B', 'C', 'D'])
        opts = {'A': '', 'B': '', 'C': '', 'D': ''}
        opts[correct_key] = correct_name
        other_keys = [k for k in opts if k != correct_key]
        for i, dk in enumerate(other_keys[:3]):
            opts[dk] = distractors[i] if i < len(distractors) else ''
        return opts, correct_key

    now = datetime.now()
    created = 0
    errors = 0

    for filename in images:
        try:
            src = _os.path.join(folder_path, filename)
            timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
            name, ext = _os.path.splitext(filename)
            new_filename = f"{timestamp}_{random.randint(0,999999):06d}_{name[:30]}{ext}"
            with open(src, "rb") as fh:
                image_bytes = fh.read()
            image_url = upload_image_bytes(image_bytes, new_filename)

            content = f"""<p>请选择下图所示细胞名称：</p>
<img src="{image_url}" alt="image" style="max-width: 50%;" />"""

            options, correct_key = generate_options(filename, images)
            options_json = _json.dumps(options, ensure_ascii=False)

            q = models.Question(
                type='single',
                content=content,
                options=options_json,
                answer=correct_key,
                analysis='',
                category=get_category(src),
                created_at=now
            )
            db.add(q)
            db.commit()
            db.refresh(q)
            created += 1
        except Exception as e:
            print(f"Error creating question {filename}: {e}")
            errors += 1

    return {"created": created, "errors": errors, "total": len(images)}
