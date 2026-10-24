"""调整考试的开考/结束时间。

时间在数据库中按 UTC 存储（后端用 datetime.utcnow() 判断状态，
前端展示时统一 +8 小时）。本脚本接受**本地时间**（默认东八区），
自动换算成 UTC 后写入，避免"看起来是 30 号、实际差 8 小时"。

用法：
    cd backend && python scripts/set_exam_window.py --exam-id 7 \
        --start "2026-10-30 00:00" --end "2026-10-30 23:59"
"""
import argparse
from datetime import datetime, timedelta

from db import connect


def parse_local(text: str) -> datetime:
    text = text.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise SystemExit(f"无法解析时间：{text!r}（示例：2026-10-30 00:00）")


def main():
    ap = argparse.ArgumentParser(description="调整考试时间窗")
    ap.add_argument("--exam-id", type=int, required=True)
    ap.add_argument("--start", required=True, help="本地开始时间，如 2026-10-30 00:00")
    ap.add_argument("--end", required=True, help="本地结束时间，如 2026-10-30 23:59")
    ap.add_argument("--tz-offset", type=int, default=8, help="本地时区与 UTC 的小时差，默认 8")
    args = ap.parse_args()

    local_start = parse_local(args.start)
    local_end = parse_local(args.end)
    if local_end <= local_start:
        raise SystemExit("结束时间必须晚于开始时间")

    utc_start = local_start - timedelta(hours=args.tz_offset)
    utc_end = local_end - timedelta(hours=args.tz_offset)

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, start_time, end_time FROM exams WHERE id = %s",
                (args.exam_id,),
            )
            row = cur.fetchone()
            if not row:
                raise SystemExit(f"考试 id={args.exam_id} 不存在")
            print(f"当前：id={row[0]} {row[1]}")
            print(f"       start_time={row[2]}  end_time={row[3]}（数据库 UTC 值）")

            cur.execute(
                "UPDATE exams SET start_time = %s, end_time = %s WHERE id = %s RETURNING start_time, end_time",
                (utc_start, utc_end, args.exam_id),
            )
            new_start, new_end = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    print("更新后（UTC）：", new_start, "→", new_end)
    print(f"对应本地时间（UTC+{args.tz_offset}）："
          f"{new_start + timedelta(hours=args.tz_offset)} → {new_end + timedelta(hours=args.tz_offset)}")


if __name__ == "__main__":
    main()
