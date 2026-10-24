from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from ..storage import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    upload_image_bytes,
)

router = APIRouter(prefix="/api/upload", tags=["上传"])


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="没有上传文件")
    
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    ext = f".{ext}" if ext else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过5MB限制")
    
    url = upload_image_bytes(contents, file.filename or f"upload{ext}")

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
