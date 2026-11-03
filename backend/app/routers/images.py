# -*- coding: utf-8 -*-
"""图片代理：GET /api/images/<文件名>。

题库里的图片原本直接指向 Supabase Storage 的公网地址。对象存储在境外，
医院内网、部分运营商的出口经常连不上 supabase.co，页面上的图就全裂成破图。

改成由后端转发：浏览器只跟后端说话，后端再从对象存储取。
客户端能不能直连对象存储，就不影响题图显示了。

优先顺序：
1. 本地磁盘（上传目录里有就直接给，不走网络）
2. Supabase Storage
3. Vercel Blob

这个接口是公开的（登录页的 Logo 在登录前就要显示）。
"""
import os
import time
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, FileResponse

from ..storage import find_local_image, supabase_enabled, supabase_public_url, blob_enabled, _BLOB_BASE_URL

router = APIRouter(prefix="/api/images", tags=["images"])

# 进程内缓存：同一张图反复请求不用每次都去对象存储取一遍。
# 单实例最多留 200 张，超了就按最早用的淘汰。
_CACHE = {}
_CACHE_MAX = 200
_CACHE_TTL = 3600  # 秒

_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
}


def _content_type(name: str) -> str:
    return _MIME.get(os.path.splitext(name)[1].lower(), "image/jpeg")


def _cache_get(name: str):
    item = _CACHE.get(name)
    if item is None:
        return None
    data, ctype, at = item
    if time.time() - at > _CACHE_TTL:
        _CACHE.pop(name, None)
        return None
    return data, ctype


def _cache_put(name: str, data: bytes, ctype: str):
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][2])
        _CACHE.pop(oldest, None)
    _CACHE[name] = (data, ctype, time.time())


def _fetch(url: str) -> tuple:
    req = urllib.request.Request(url, headers={"User-Agent": "exam-system/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read(), resp.headers.get("Content-Type") or "image/jpeg"


@router.get("/{pathname:path}")
def get_image(pathname: str):
    """按对象路径取图，例如 /api/images/morph/xxx.jpg。

    路径会先做安全检查（不允许 .. 和绝对路径），再拼到对象存储的 images/ 下。
    """
    rel = (pathname or "").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise HTTPException(status_code=404, detail="文件不存在")
    name = os.path.basename(rel)

    # 1) 本地磁盘
    path = find_local_image(name)
    if path:
        return FileResponse(
            path,
            media_type=_content_type(name),
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # 2) 进程内缓存
    cached = _cache_get(name)
    if cached:
        data, ctype = cached
        return Response(
            content=data,
            media_type=ctype,
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # 3) 对象存储
    errors = []
    urls = []
    if supabase_enabled():
        urls.append(supabase_public_url(f"images/{rel}"))
    if blob_enabled():
        urls.append(f"{_BLOB_BASE_URL}/images/{rel}")
    for url in urls:
        try:
            data, ctype = _fetch(url)
            _cache_put(name, data, ctype)
            return Response(
                content=data,
                media_type=ctype,
                headers={"Cache-Control": "public, max-age=604800"},
            )
        except Exception as e:  # 换下一个源
            errors.append(f"{url}: {e}")

    if not urls:
        raise HTTPException(status_code=404, detail="图片存储未配置")
    raise HTTPException(status_code=404, detail="文件不存在")
