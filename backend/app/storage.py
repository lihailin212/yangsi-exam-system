"""统一存储层抽象：生产环境使用 Supabase Storage（首选）或 Vercel Blob，本地开发使用磁盘。"""
import os
import uuid
from datetime import datetime

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

_BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_SUPABASE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "exam-images").strip()
_SUPABASE_PUBLIC_BASE = os.environ.get(
    "SUPABASE_STORAGE_PUBLIC_BASE", ""
).strip().rstrip("/")
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


def supabase_enabled() -> bool:
    """Supabase Storage 是否可用（生产环境首选）。"""
    return bool(_SUPABASE_URL and _SUPABASE_KEY)


def supabase_public_url(pathname: str) -> str:
    """把 images/xxx 之类的对象路径拼成 Supabase Storage 公网地址。"""
    base = _SUPABASE_PUBLIC_BASE or f"{_SUPABASE_URL}/storage/v1/object/public/{_SUPABASE_BUCKET}"
    return f"{base.rstrip('/')}/{pathname.lstrip('/')}"


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
    """把 /uploads/images/xxx 之类的本地路径映射为公网地址。

    优先 Supabase Storage，其次 Vercel Blob。
    """
    name = os.path.basename(pathname)
    if supabase_enabled():
        return supabase_public_url(f"images/{name}")
    return f"{_BLOB_BASE_URL}/images/{name}"


def storage_public_base() -> str:
    """当前对象存储的公网地址前缀（导入脚本拼 URL 用）。"""
    if supabase_enabled():
        return _SUPABASE_PUBLIC_BASE or f"{_SUPABASE_URL}/storage/v1/object/public/{_SUPABASE_BUCKET}"
    return _BLOB_BASE_URL


def upload_bytes(pathname: str, data: bytes, content_type: str = "image/jpeg") -> str:
    """上传到配置好的对象存储，返回公网可访问 URL。

    Supabase Storage 优先；没有配置时回落到 Vercel Blob；两者都没有则报错。
    导入/去水印等脚本统一走这里，不再直接依赖某个厂商 SDK。
    """
    if supabase_enabled():
        return _upload_to_supabase(pathname, data, content_type)
    if blob_enabled():
        from vercel.blob import sync as blob

        res = blob.put_blob(pathname, data, access="public", add_random_suffix=False,
                            allow_overwrite=True)
        return res.url
    raise RuntimeError("没有配置对象存储（需要 SUPABASE_SERVICE_ROLE_KEY 或 BLOB_READ_WRITE_TOKEN）")


def upload_image_bytes(data: bytes, original_filename: str = "") -> str:
    """保存图片，返回可直接访问的 URL（Blob 公网地址或本地相对路径）。"""
    ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    filename = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex}{ext}"

    if supabase_enabled() or blob_enabled():
        return upload_bytes(f"images/{filename}", data)

    # 本地开发：落盘
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return f"/uploads/images/{filename}"


def _upload_to_supabase(pathname: str, data: bytes, content_type: str = "image/jpeg") -> str:
    """上传到 Supabase Storage，返回公网可访问 URL。"""
    import urllib.request

    mime = content_type or "image/jpeg"

    endpoint = f"{_SUPABASE_URL}/storage/v1/object/{_SUPABASE_BUCKET}/{pathname.lstrip('/')}"
    req = urllib.request.Request(endpoint, data=data, method="POST")
    req.add_header("apikey", _SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {_SUPABASE_KEY}")
    req.add_header("Content-Type", mime)
    req.add_header("x-upsert", "true")
    with urllib.request.urlopen(req, timeout=60):
        pass
    return supabase_public_url(pathname)
