#!/usr/bin/env python3
"""随机选一只可透视的 ETF（供每日推送用）。

从本地 DuckDB 选 equity-track、在市、有持仓、近期有流动性的 ETF，随机挑 1 只。
stdout 只打印纯代码（便于 orchestration: CODE=$(pick.py); report.py $CODE）。

筛选:
  - category='equity' 且 delist_date IS NULL
  - 有持仓数据（fact_etf_holding）
  - 近 N 自然日均成交额 >= --min-amount（默认 5千万，过滤僵尸 ETF）

去重:
  - --history-file 给定时，排除文件中最近 --no-repeat 条已推代码，并在选定后追加，
    实现「每日推不重样」。

用法:
    pick.py --db market.duckdb
    pick.py --db market.duckdb --history-file ~/.etf_push_history --verbose
"""
import argparse
import os
import random
import sys

import duckdb


def main():
    ap = argparse.ArgumentParser(description="随机选一只可透视 ETF")
    ap.add_argument("--db", default=os.environ.get("MINE_DATA_DB"))
    ap.add_argument("--min-amount", type=float, default=5e7, help="近期日均成交额下限(元)")
    ap.add_argument("--recent-days", type=int, default=30, help="成交额统计窗口(自然日)")
    ap.add_argument("--exclude", default="", help="额外排除的代码,逗号分隔")
    ap.add_argument("--history-file", default=None, help="去重历史文件")
    ap.add_argument("--no-repeat", type=int, default=30, help="历史去重窗口(最近N次)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--verbose", action="store_true", help="选中信息打到 stderr")
    args = ap.parse_args()
    if not args.db or not os.path.exists(args.db):
        print(f"错误: DB 不存在: {args.db}", file=sys.stderr)
        sys.exit(2)

    exclude = {c.strip() for c in args.exclude.split(",") if c.strip()}
    if args.history_file and os.path.exists(args.history_file):
        with open(args.history_file, encoding="utf-8") as f:
            recent = [ln.strip() for ln in f if ln.strip()]
        exclude |= set(recent[-args.no_repeat:])

    con = duckdb.connect(args.db, read_only=True)
    try:
        pool = con.execute(
            "WITH recent AS ("
            "  SELECT etf_code, avg(amount) avg_amt FROM fact_etf_daily "
            "  WHERE trade_date >= (SELECT max(trade_date) - ? FROM fact_etf_daily) "
            "  GROUP BY etf_code) "
            "SELECT e.etf_code, e.etf_name, r.avg_amt "
            "FROM dim_etf e JOIN recent r ON e.etf_code=r.etf_code "
            "WHERE e.category='equity' AND e.delist_date IS NULL "
            "  AND r.avg_amt >= ? "
            "  AND EXISTS (SELECT 1 FROM fact_etf_holding h WHERE h.etf_code=e.etf_code)",
            [args.recent_days, args.min_amount]
        ).fetchall()
    finally:
        con.close()

    pool = [row for row in pool if row[0] not in exclude]
    if not pool:
        print("错误: 流动性池为空(可能阈值过高或历史排除过多)", file=sys.stderr)
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)
    code, name, amt = random.choice(pool)

    if args.history_file:
        with open(args.history_file, "a", encoding="utf-8") as f:
            f.write(code + "\n")
    if args.verbose:
        print(f"选中 {code} {name} | 近{args.recent_days}日均成交额 {amt/1e8:.2f}亿 "
              f"| 池大小 {len(pool)}", file=sys.stderr)
    print(code)


if __name__ == "__main__":
    main()
