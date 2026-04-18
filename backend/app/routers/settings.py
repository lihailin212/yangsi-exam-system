from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..auth import require_admin
import json
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

class Settings(BaseModel):
    system_name: str = "杨思学考试系统"
    hospital_name: str = ""
    logo_url: str = ""
    exam_show_analysis: bool = True
    notify_exam_start: bool = True
    notify_score_release: bool = True
    notify_course_update: bool = False

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
