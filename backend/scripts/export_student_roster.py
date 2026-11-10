# -*- coding: utf-8 -*-
"""把「学员信息表」(users 表) 里当前生效的数据导出成检验科花名册 CSV。

用途：学员信息在后台核对/修正之后，用本脚本把最新数据落盘，
      替换 backend/scripts/lab_roster.csv（import_lab_roster.py 的数据源）。

默认只导出某个机构下的正式学员（排除 admin 之类的系统账号），
按工号数值升序排列；工号非数字的排在最后。

用法：
    cd backend/scripts && python export_student_roster.py --dry-run
    cd backend/scripts && python export_student_roster.py
"""
import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import connect  # noqa: E402

DEFAULT_CSV = pathlib.Path(__file__).with_name("lab_roster.csv")
DEFAULT_ORG = "杨思医院检验科"
FIELDNAMES = ["工号", "姓名", "手机号码", "科室", "职位", "备注"]


def sort_key(employee_id: str):
    """工号按数值升序；非数字/空的排在最后。"""
    s = (employee_id or "").strip()
    return (0, int(s), "") if s.isdigit() else (1, 0, s)


def main():
    ap = argparse.ArgumentParser(description="导出当前学员信息表为花名册 CSV")
    ap.add_argument("--out", default=str(DEFAULT_CSV), help="输出 CSV 路径")
    ap.add_argument("--org", default=DEFAULT_ORG, help="只导出该机构下的学员；留空导出全部")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    conn = connect()
    try:
        with conn.cursor() as cur:
            if args.org:
                cur.execute(
                    "SELECT u.employee_id, u.name, u.phone, u.dept, u.role "
                    "FROM users u JOIN organizations o ON o.id = u.organization_id "
                    "WHERE o.name = %s AND u.is_active IS TRUE",
                    (args.org,),
                )
            else:
                cur.execute(
                    "SELECT employee_id, name, phone, dept, role FROM users "
                    "WHERE is_active IS TRUE"
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    rows = [r for r in rows if (r[0] or "").strip() and (r[0] or "").strip() != "admin"]
    rows.sort(key=lambda r: sort_key(r[0]))

    out = pathlib.Path(args.out)
    print(f"共 {len(rows)} 人 → {out}")
    for r in rows:
        print("  ", r[0], r[1], r[2] or "")

    if args.dry_run:
        return

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDNAMES)
        for employee_id, name, phone, dept, role in rows:
            w.writerow([employee_id, name, phone or "", dept or "", role or "", ""])
    print("已写入", out)


if __name__ == "__main__":
    main()
