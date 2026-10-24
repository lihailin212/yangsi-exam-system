from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import inspect, text
from ..auth import clear_user_cache, require_admin
from ..database import SessionLocal, engine
from ..models import SystemSetting, BackupRecord
import json
import os
import shutil
from datetime import datetime

router = APIRouter(prefix="/api/settings", tags=["settings"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

try:
    os.makedirs(BACKUP_DIR, exist_ok=True)
except OSError:
    # 生产环境（Serverless）无持久化磁盘，备份改存数据库
    BACKUP_DIR = ""

class Settings(BaseModel):
    system_name: str = "杨思学考试系统"
    hospital_name: str = ""
    logo_url: str = ""
    exam_show_analysis: bool = True
    notify_exam_start: bool = True
    notify_score_release: bool = True
    notify_course_update: bool = False

def load_settings():
    """读取系统设置：优先数据库，其次本地 settings.json。"""
    db = SessionLocal()
    try:
        rows = db.query(SystemSetting).all()
        if rows:
            result = {}
            for r in rows:
                try:
                    result[r.key] = json.loads(r.value)
                except (TypeError, ValueError):
                    result[r.key] = r.value
            return result
    except Exception:
        pass
    finally:
        db.close()

    try:
        if SETTINGS_FILE and os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_settings(data):
    """保存系统设置到数据库（同时尝试写本地文件，失败不影响）"""
    db = SessionLocal()
    try:
        for key, value in data.items():
            row = db.query(SystemSetting).filter_by(key=key).first()
            if row is None:
                db.add(SystemSetting(key=key, value=json.dumps(value, ensure_ascii=False)))
            else:
                row.value = json.dumps(value, ensure_ascii=False)
        db.commit()
    finally:
        db.close()

    try:
        if SETTINGS_FILE:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

@router.get("/public")
def get_public_settings():
    """获取公开设置（无需认证，供考生登录页使用）"""
    return load_settings()

@router.get("")
def get_settings(_=Depends(require_admin)):
    return load_settings()

@router.post("")
def update_settings(settings: Settings, _=Depends(require_admin)):
    save_settings(settings.model_dump())
    return {"ok": True, "message": "设置已保存"}

# ==================== 数据备份与恢复 ====================

# 需要备份的表（按依赖顺序）
BACKUP_TABLES = [
    "questions",
    "exams",
    "users",
    "exam_records",
    "exam_distributions",
    "exam_question",  # 多对多关系表
]

def table_to_dict(db, table_name):
    """将表数据导出为字典列表"""
    try:
        result = db.execute(text(f"SELECT * FROM {table_name}")).fetchall()
        inspector = inspect(engine)
        col_names = [c["name"] for c in inspector.get_columns(table_name)]
        return [dict(zip(col_names, row)) for row in result]
    except Exception as e:
        print(f"Error exporting {table_name}: {e}")
        return []

def _save_backup(filename: str, content: str):
    """备份内容优先落盘，无持久化磁盘时存数据库。"""
    if BACKUP_DIR:
        try:
            with open(os.path.join(BACKUP_DIR, filename), "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except OSError:
            pass
    db = SessionLocal()
    try:
        row = db.query(BackupRecord).filter_by(filename=filename).first()
        if row is None:
            db.add(BackupRecord(filename=filename, content=content))
        else:
            row.content = content
        db.commit()
    finally:
        db.close()
    return False

def _read_backup(filename: str):
    """按文件名读取备份内容，返回 (内容, 是否在磁盘)。"""
    if BACKUP_DIR:
        filepath = os.path.join(BACKUP_DIR, os.path.basename(filename))
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read(), True
    db = SessionLocal()
    try:
        row = db.query(BackupRecord).filter_by(filename=os.path.basename(filename)).first()
        if row:
            return row.content, False
    finally:
        db.close()
    return None, False

@router.get("/backup")
def create_backup(_=Depends(require_admin)):
    """创建数据备份，返回 JSON 格式的备份文件"""
    db = SessionLocal()
    try:
        backup_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "tables": {}
        }

        for table in BACKUP_TABLES:
            backup_data["tables"][table] = table_to_dict(db, table)

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.json"
        content = json.dumps(backup_data, ensure_ascii=False, indent=2)
        to_disk = _save_backup(filename, content)
        filepath = os.path.join(BACKUP_DIR, filename) if to_disk else None

        # 返回文件路径供下载
        return {
            "ok": True,
            "filename": filename,
            "path": filepath,
            "created_at": backup_data["created_at"],
            "tables_count": {t: len(backup_data["tables"][t]) for t in BACKUP_TABLES}
        }
    finally:
        db.close()

@router.get("/backup/download")
def download_backup(filename: str = None, _=Depends(require_admin)):
    """下载备份文件"""
    if filename:
        content, on_disk = _read_backup(filename)
        if content is None:
            raise HTTPException(status_code=404, detail="备份文件不存在")
        if on_disk:
            filepath = os.path.join(BACKUP_DIR, os.path.basename(filename))
            return FileResponse(
                filepath,
                media_type="application/json",
                filename=os.path.basename(filepath)
            )
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'}
        )
    else:
        # 获取最新的备份文件
        files = []
        if BACKUP_DIR:
            files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".json")]
        db = SessionLocal()
        try:
            for r in db.query(BackupRecord).all():
                if r.filename not in files:
                    files.append(r.filename)
        finally:
            db.close()
        if not files:
            raise HTTPException(status_code=404, detail="暂无备份文件")
        files.sort(reverse=True)
        content, on_disk = _read_backup(files[0])
        if content is None:
            raise HTTPException(status_code=404, detail="备份文件不存在")
        if on_disk:
            filepath = os.path.join(BACKUP_DIR, files[0])
            return FileResponse(
                filepath,
                media_type="application/json",
                filename=os.path.basename(filepath)
            )
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{files[0]}"'}
        )

@router.get("/backup/list")
def list_backups(_=Depends(require_admin)):
    """列出所有备份文件"""
    files = []
    if BACKUP_DIR:
        for f in os.listdir(BACKUP_DIR):
            if f.startswith("backup_") and f.endswith(".json"):
                filepath = os.path.join(BACKUP_DIR, f)
                stat = os.stat(filepath)
                files.append({
                    "filename": f,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
    db = SessionLocal()
    try:
        known = {f["filename"] for f in files}
        for r in db.query(BackupRecord).all():
            if r.filename in known:
                continue
            files.append({
                "filename": r.filename,
                "size": len(r.content or ""),
                "created_at": r.created_at.isoformat() if r.created_at else ""
            })
    finally:
        db.close()
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files

@router.post("/restore")
def restore_backup(file=None, _=Depends(require_admin)):
    """从上传的备份文件恢复数据"""
    if not file:
        raise HTTPException(status_code=400, detail="请上传备份文件")

    try:
        # 读取备份数据
        contents = file.file.read()
        backup_data = json.loads(contents.decode("utf-8"))

        if "tables" not in backup_data:
            raise HTTPException(status_code=400, detail="无效的备份文件格式")

        db = SessionLocal()
        try:
            # 按依赖顺序恢复数据
            for table in BACKUP_TABLES:
                if table not in backup_data["tables"]:
                    continue

                rows = backup_data["tables"][table]
                if not rows:
                    continue

                # 清空表（除了 users 表中的 admin 用户）
                if table == "users":
                    db.execute(text(f"DELETE FROM {table} WHERE employee_id != 'admin'"))
                else:
                    db.execute(text(f"DELETE FROM {table}"))

                # 插入数据
                for row in rows:
                    # 处理 datetime 字段
                    for key, value in row.items():
                        if isinstance(value, str) and ("T" in value or " " in value):
                            try:
                                if "T" in value:
                                    row[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                                elif ":" in value:
                                    row[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                            except:
                                pass

                    # 构建 INSERT 语句
                    columns = list(row.keys())
                    placeholders = [f":{col}" for col in columns]
                    insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    db.execute(text(insert_sql), row)

            db.commit()
            # 备份恢复会整体覆盖用户和题库，缓存里的旧数据必须作废
            clear_user_cache()
            from .. import crud
            crud.invalidate_exam_questions()

            return {
                "ok": True,
                "message": "数据恢复成功",
                "restored_tables": {t: len(backup_data["tables"].get(t, [])) for t in BACKUP_TABLES if t in backup_data["tables"]}
            }
        finally:
            db.close()

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

@router.get("/backup/db")
def download_db_backup(_=Depends(require_admin)):
    """直接下载整个数据库文件"""
    db_path = os.path.join(BASE_DIR, "exam.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"exam_db_{timestamp}.db"

    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename=filename
    )
