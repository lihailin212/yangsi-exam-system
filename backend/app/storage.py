"""统一存储层抽象：生产环境使用 Vercel Blob，本地开发使用磁盘。"""
import os
import uuid
from datetime import datetime

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

_BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
_BLOB_BASE_URL = os.environ.get(
    "BLOB_BASE_URL", "https://u2wff8olceezsvlg.public.blob.vercel-storage.com"
).strip().rstrip("/")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(BACKEND_DIR)
_VOLUME_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()

# 新图片统一落在 backend/uploads/images：历史图片实际都在这里，
# 之前的路径多拼了一层 ".."，指向了仓库根的 uploads/images，
# 结果是新图存一个目录、老图在另一个目录，谁也找不到谁。
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads", "images")


def blob_enabled() -> bool:
    return bool(_BLOB_TOKEN)


def local_image_dirs() -> list:
    """按优先级返回本地图片目录：线上挂载盘 → backend/uploads/images → 仓库根 uploads/images。"""
    candidates = []
    if _VOLUME_DIR:
        candidates.append(os.path.join(_VOLUME_DIR, "uploads", "images"))
    candidates.append(UPLOAD_DIR)
    candidates.append(os.path.join(REPO_DIR, "uploads", "images"))

    seen, dirs = set(), []
    for d in candidates:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen:
            seen.add(key)
            dirs.append(d)
    return dirs


def find_local_image(filename: str):
    """在本地目录里找一张图片，返回绝对路径；找不到返回 None。

    只认文件名本身（取 basename），避免 /uploads/../ 之类的路径穿越。
    """
    name = os.path.basename(filename or "")
    if not name or name in (".", ".."):
        return None
    for d in local_image_dirs():
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None


def local_upload_dir() -> str:
    """本地磁盘目录（本地开发/迁移脚本用）。"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


def blob_url_for(pathname: str) -> str:
    """把 /uploads/images/xxx 之类的本地路径映射为 Blob 公网地址。"""
    name = os.path.basename(pathname)
    return f"{_BLOB_BASE_URL}/images/{name}"


def upload_image_bytes(data: bytes, original_filename: str = "") -> str:
    """保存图片，返回可直接访问的 URL（Blob 公网地址或本地相对路径）。"""
    ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    filename = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"

    if blob_enabled():
        from vercel.blob import sync as blob

        result = blob.put_blob(
            f"images/{filename}",
            data,
            access="public",
            add_random_suffix=False,
            allow_overwrite=True,
        )
        return result.url

    # 本地开发：落盘
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return f"/uploads/images/{filename}"
