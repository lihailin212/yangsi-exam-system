import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/upload", tags=["上传"])

# Railway 持久化磁盘路径（生产环境）
_DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
UPLOAD_DIR = os.path.join(_DATA_DIR, "uploads", "images")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="没有上传文件")
    
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过5MB限制")
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    filename = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        f.write(contents)

    # 返回相对 URL（不带 backend/ 路径）
    url = f"/uploads/images/{filename}"
    return JSONResponse({
        "errno": 0,
        "data": {
            "url": url,
            "alt": file.filename,
            "href": url
        }
    })


@router.get("/config")
async def get_upload_config():
    return JSONResponse({
        "errno": 0,
        "data": {
            "server": "/api/upload/image",
            "fieldName": "file",
            "maxSize": MAX_FILE_SIZE // 1024,
            "accept": "image/jpeg,image/png,image/gif,image/webp,image/bmp",
            "meta": {},
            "withCredentials": False
        }
    })
