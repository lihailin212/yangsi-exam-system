from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
import os
import time
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from . import models
from .timeutil import epoch_seconds

SECRET_KEY = os.environ.get("SECRET_KEY", "exam-system-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
ARENA_PLAYER_TOKEN_EXPIRE_MINUTES = 60 * 6  # 选手令牌6小时

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 认证用用户信息的短时缓存。
#
# 数据库在远端（Neon，走连接池），一次 SELECT 往返 200ms 以上，而每个请求
# 都得把当前用户取出来一次。考试系统里用户在几十秒内变成管理员或被停用
# 没有实际影响，所以用很短的 TTL 缓存一份快照，把一次数据库往返换成
# 一次内存命中。用户信息被改时会主动作废缓存（见 crud.update_user）。
USER_CACHE_TTL_SECONDS = 30.0
_user_cache = {}


class UserSnapshot:
    """当前用户的只读快照（只带认证与鉴权需要的字段）。"""

    __slots__ = ("id", "employee_id", "name", "password_hash", "dept",
                 "role", "is_admin", "is_active", "created_at")

    def __init__(self, user):
        self.id = user.id
        self.employee_id = user.employee_id
        self.name = user.name
        self.password_hash = user.password_hash
        self.dept = user.dept
        self.role = user.role
        self.is_admin = bool(user.is_admin)
        self.is_active = bool(user.is_active)
        self.created_at = user.created_at


def get_cached_user(user_id: int):
    item = _user_cache.get(user_id)
    if item is None:
        return None
    expires_at, snapshot = item
    if expires_at < time.time():
        _user_cache.pop(user_id, None)
        return None
    return snapshot


def cache_user(user):
    snapshot = UserSnapshot(user)
    _user_cache[user.id] = (time.time() + USER_CACHE_TTL_SECONDS, snapshot)
    return snapshot


def invalidate_user_cache(user_id: int):
    _user_cache.pop(user_id, None)


def clear_user_cache():
    """清空用户缓存（恢复备份这类整体覆盖数据的操作之后要调）。"""
    _user_cache.clear()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    # jose 要求 iat 为整数，写成 ISO 字符串会在解码时抛
    # "Issued At claim (iat) must be an integer"，进而让所有请求 401。
    to_encode.setdefault("iat", epoch_seconds())
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """解析JWT并返回payload，失败抛401。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except JWTError:
        raise credentials_exception
    snapshot = get_cached_user(user_id)
    if snapshot is not None:
        return snapshot
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return cache_user(user)

def require_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def decode_token(token: str) -> dict:
    """解析JWT，失败返回None（供WebSocket等非依赖注入场景使用）"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def create_arena_player_token(player_id: int, arena_id: int, team_id: int) -> str:
    """签发选手专用令牌（选手无需登录，通过邀请码加入）"""
    now = datetime.utcnow()
    payload = {
        "sub": str(player_id),
        "type": "arena_player",
        "arena_id": arena_id,
        "team_id": team_id,
        "iat": epoch_seconds(),
        "exp": now + timedelta(minutes=ARENA_PLAYER_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_arena_player_token(token: str) -> dict:
    """解析选手令牌，返回payload；无效返回None"""
    payload = decode_token(token)
    if not payload or payload.get("type") != "arena_player":
        return None
    return payload
