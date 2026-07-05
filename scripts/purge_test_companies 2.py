#!/usr/bin/env python3
"""QA 前: 指定会社以外のテスト会社と配下データを削除する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.company_purge import (
    list_company_master_rows,
    plan_company_purge,
    purge_companies_except,
)


DEFAULT_KEEP = ("co-gidr", "test7", "test8", "test9")


def _print_plan(title: str, plan) -> None:
    print(f"\n=== {title} ===")
    print(f"残す会社: {plan.keep_count} 件")
    for cid in plan.keep_ids:
        print(f"  keep: {cid}")
    print(f"削除対象会社: {plan.delete_count} 件")
    if plan.delete_ids:
        preview = plan.delete_ids[:20]
        for cid in preview:
            print(f"  delete: {cid}")
        if len(plan.delete_ids) > len(preview):
            print(f"  ... 他 {len(plan.delete_ids) - len(preview)} 件")
    totals = plan.total_rows_to_delete()
    if totals:
        print("削除予定レコード数（会社合計）:")
        for key in sorted(totals):
            if totals[key]:
                print(f"  {key}: {totals[key]}")


def _print_remaining(db) -> None:
    rows = list_company_master_rows(db)
    print(f"\n=== 削除後: 残存会社 {len(rows)} 件 ===")
    for row in rows:
        name = (row.company_name or "").strip()
        active = "active" if row.is_active else "inactive"
        print(f"  {row.company_id} | {name} | {active}")


def main() -> int:
    parser = argparse.ArgumentParser(description="不要テスト会社を ORM 経由で削除")
    parser.add_argument(
        "--keep",
        nargs="*",
        default=list(DEFAULT_KEEP),
        help="残す company_id（既定: co-gidr test7 test8 test9）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除せず件数のみ表示",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plan = plan_company_purge(db, args.keep)
        _print_plan("削除前", plan)
        if args.dry_run:
            print("\n(dry-run: 削除は実行しません)")
            return 0
        if not plan.delete_ids:
            print("\n削除対象がありません。")
            _print_remaining(db)
            return 0
        purge_companies_except(db, args.keep)
        _print_remaining(db)
        print("\n削除完了。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
