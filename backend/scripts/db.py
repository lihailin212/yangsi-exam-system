"""运维脚本共用工具：连接数据库（优先生产库 .env.local，其次环境变量）。"""
import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


def load_dotenv_local():
    """加载仓库根目录 .env.local（生产库连接串）。"""
    env_path = REPO_DIR / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def connect():
    """返回与生产一致的 psycopg2 连接。"""
    load_dotenv_local()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("未找到 DATABASE_URL（检查 .env.local 或环境变量）")
    import psycopg2

    url = url.replace("postgres://", "postgresql://")
    return psycopg2.connect(url)

