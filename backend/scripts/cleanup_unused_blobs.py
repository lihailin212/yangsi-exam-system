"""清理 Vercel Blob 里"没有任何题目引用"的图片。

背景：Blob 里存着两批图——
  * images/morph/xxx_xxxxxx.jpg   形态学题库在用（压缩过，64MB）
  * images/202604xx_xxx_中文名.jpg  今年 4 月第一批上传的原图（未压缩，415MB）
第二批已经被新的形态学题库取代，题目里一张都没引用，纯占地方。
Vercel Blob 免费额度有限，垃圾不清掉容易把存储撑爆导致 store 被停用。

脚本会拿生产库的题目内容逐一比对，只删"没有任何题目引用"的文件，
而且这些文件本地 backend/uploads/images 里都有备份，删了也能再传。

用法:
    cd backend
    python scripts/cleanup_unused_blobs.py            # 只看会删什么
    python scripts/cleanup_unused_blobs.py --apply    # 真删
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
for line in open(REPO / ".env.local", encoding="utf-8-sig"):
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"'))

sys.path.insert(0, str(BACKEND))
from app.database import SessionLocal
from app.models import Question

API = "https://blob.vercel-storage.com/"


def api(method, params=None, timeout=60):
    url = API + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": "Bearer " + os.environ["BLOB_READ_WRITE_TOKEN"]})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if body else None


def list_blobs():
    out, cursor = [], None
    while True:
        params = {"limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = api("GET", params)
        out += d.get("blobs", [])
        if not d.get("hasMore"):
            break
        cursor = d.get("cursor")
    return out


def used_paths():
    db = SessionLocal()
    used = set()
    try:
        for (content,) in db.query(Question.content).all():
            for u in re.findall(r'src="([^"]+)"', content or ""):
                if "/images/" in u:
                    used.add("images/" + u.split("/images/", 1)[1])
    finally:
        db.close()
    return used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真删（默认只报告）")
    ap.add_argument("--keep-local-check", action="store_true", default=True,
                    help="只删本地有备份的（默认开启）")
    args = ap.parse_args()

    blobs = list_blobs()
    used = used_paths()
    local_dirs = [BACKEND / "uploads" / "images", REPO / "uploads" / "images"]
    local = set()
    for d in local_dirs:
        if d.exists():
            local |= {f.name for f in d.iterdir() if f.is_file()}

    unused = [b for b in blobs if b["pathname"] not in used]
    total_all = sum(b.get("size", 0) for b in blobs)
    targets = [b for b in unused
               if b["pathname"].split("/")[-1] in local or not args.keep_local_check]
    total_del = sum(b.get("size", 0) for b in targets)

    print("Blob 现状: %d 个文件, %.1f MB" % (len(blobs), total_all / 1048576.0))
    print("题目在用  : %d 个, %.1f MB" % (len(used), total_all / 1048576.0 - total_del / 1048576.0))
    print("可清理    : %d 个, %.1f MB（本地都有备份）" % (len(targets), total_del / 1048576.0))
    if not args.apply:
        print("\n（演练模式，加 --apply 才真删）")
        for b in targets[:10]:
            print("   %.1f MB  %s" % (b.get("size", 0) / 1048576.0, b["pathname"]))
        if len(targets) > 10:
            print("   ... 共 %d 个" % len(targets))
        return

    ok, fail = 0, []
    for i, b in enumerate(targets):
        try:
            api("DELETE", {"pathname": b["pathname"]})
            ok += 1
        except urllib.error.HTTPError as e:
            fail.append((b["pathname"], e.code))
        except Exception as e:
            fail.append((b["pathname"], str(e)))
        if (i + 1) % 50 == 0:
            print("  已删 %d/%d" % (i + 1, len(targets)), flush=True)
    print("删除完成 %d 个，失败 %d 个" % (ok, len(fail)))
    for p, e in fail[:10]:
        print("   失败 %s -> %s" % (p, e))
    blobs2 = list_blobs()
    print("清理后: %d 个文件, %.1f MB" % (
        len(blobs2), sum(b.get("size", 0) for b in blobs2) / 1048576.0))


if __name__ == "__main__":
    main()
