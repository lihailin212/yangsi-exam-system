from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import socket
import sys
from urllib.parse import urlparse

# 空字符串也要当没设置：.env / CI 里常见 RAILWAY_VOLUME_MOUNT_PATH= 这种写法，
# 直接用 os.environ.get 的默认值会被空串顶掉，后面 makedirs("") 直接崩。
_DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip() or os.path.dirname(os.path.dirname(__file__))

DATABASE_URL = os.environ.get("DATABASE_URL")


def _resolve_ipv4(hostname):
    """取该主机名的一个 IPv4 地址，解析不出来返回 None。"""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return None
    return infos[0][4][0] if infos else None


def _ipv4_connect_args(dsn):
    """让 libpq 直接连 IPv4 地址，绕开它对 AAAA 记录的试探。

    这台机器到 Neon 的 IPv6 基本不通，而 libpq 默认按 getaddrinfo 的返回顺序
    先试 IPv6，不通就干等到超时——实测一次建连平均 10 秒、最长 20 秒，
    强制 IPv4 后降到 3 秒左右。查询本身只要 0.04 秒，时间全耗在连线上。

    hostaddr 只指定"连哪个 IP"，host 仍用于 TLS，证书校验不受影响
    （这里用的是 sslmode=require，本来就不校验证书）。

    Neon 的接入 IP 会轮换，所以每次启动现解析一次，不写死。
    DB_FORCE_IPV4=0 可以关掉。
    """
    if os.environ.get("DB_FORCE_IPV4", "1").strip() in ("0", "false", "False", ""):
        return {}
    hostname = urlparse(dsn).hostname
    if not hostname:
        return {}
    # 本来就是 IP 字面量，不需要（也不该）再套 hostaddr
    if all(c not in hostname for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        return {}
    ip = _resolve_ipv4(hostname)
    if not ip:
        print(
            f"[db] 解析 {hostname} 的 IPv4 失败，按默认方式连接",
            file=sys.stderr,
        )
        return {}
    print(f"[db] 强制 IPv4 连接 {hostname} -> {ip}", file=sys.stderr)
    return {"hostaddr": ip}


if DATABASE_URL:
    # PostgreSQL (Supabase / Railway / Neon PostgreSQL)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args=_ipv4_connect_args(DATABASE_URL),
    )
else:
    # Local SQLite fallback
    os.makedirs(_DATA_DIR, exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(_DATA_DIR, 'exam.db')}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# expire_on_commit=False：提交后对象仍带着刚写入的值，
# 不用为了拿 id、提交时间再查一次库。数据库在远端，
# 每省一次往返就少两百多毫秒。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
