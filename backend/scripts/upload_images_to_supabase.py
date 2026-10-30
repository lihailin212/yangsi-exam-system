"""把本地图片上传到 Supabase Storage（替代 Vercel Blob）。

用法:
    python scripts/upload_images_to_supabase.py                 # 上传 uploads/images/morph 下全部图片
    python scripts/upload_images_to_supabase.py --dry-run        # 只列计划
    python scripts/upload_images_to_supabase.py --src "E:\\xxx"  # 指定目录

环境变量: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
"""
import argparse, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, ".env.local"), os.path.join(os.path.dirname(ROOT), ".env.local"), os.path.join(ROOT, ".env")):
    if os.path.exists(_p):
        load_dotenv(_p, override=True)

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".gif": "image/gif"}


def load_keys():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        raise SystemExit("缺少 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
    return url.rstrip("/"), key


def upload_one(url, key, bucket, path, filename, retries=3):
    endpoint = f"{url}/storage/v1/object/{bucket}/{path}"
    data = open(filename, "rb").read()
    ctype = MIME.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(endpoint, data=data, method="POST")
        req.add_header("apikey", key)
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Content-Type", ctype)
        req.add_header("x-upsert", "true")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return path, True, ""
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * attempt)
                continue
            return path, False, f"HTTP {e.code} {body}"
        except Exception as e:
            if attempt < retries:
                time.sleep(2 * attempt)
                continue
            return path, False, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "uploads", "images", "morph"))
    ap.add_argument("--bucket", default="exam-images")
    ap.add_argument("--prefix", default="images/morph")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url, key = load_keys()
    if not os.path.isdir(args.src):
        raise SystemExit(f"目录不存在: {args.src}")

    files = sorted(f for f in os.listdir(args.src)
                   if os.path.splitext(f)[1].lower() in MIME
                   and os.path.isfile(os.path.join(args.src, f)))
    total_mb = sum(os.path.getsize(os.path.join(args.src, f)) for f in files) / 1e6
    print(f"待上传 {len(files)} 个文件 / {total_mb:.1f} MB -> {url} bucket={args.bucket}")
    if args.dry_run:
        return

    done = failed = 0
    errors = []

    def task(f):
        path = f"{args.prefix}/{f}"
        return upload_one(url, key, args.bucket, path, os.path.join(args.src, f))

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (path, ok, err) in enumerate(ex.map(task, files), 1):
            if ok:
                done += 1
            else:
                failed += 1
                errors.append((path, err))
            if i % 50 == 0:
                print(f"  进度 {i}/{len(files)}  成功 {done}  失败 {failed}", flush=True)

    print(f"完成: 成功 {done}  失败 {failed}")
    if errors:
        print("失败明细:")
        for p, e in errors[:20]:
            print(f"  {p}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


