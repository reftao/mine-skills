#!/usr/bin/env python3
"""ETF 透视报告 — 数字骨架（equity-track，自包含）。

只依赖 duckdb + pandas，读一个本地 DuckDB 文件（mine-data 导出的 market.duckdb）。
输出确定性数字骨架；叙事层由调用方 agent 基于本骨架撰写（见 SKILL.md）。

用法:
    report.py <etf_code> --db /path/to/market.duckdb
    report.py <etf_code>                # 用环境变量 MINE_DATA_DB

依赖表: dim_etf, fact_etf_daily, fact_etf_holding, fact_stock_daily, dim_stock_enrich
"""
import argparse
import os
import sys

import duckdb
import pandas as pd


def _ret(con, table, code_col, code, days=None, since=None):
    """复权区间收益%。days: 近 N 自然日；since: 起算日（YTD 用年初）。adj=close*adjfactor。"""
    df = con.execute(
        f"SELECT trade_date, close, adjfactor FROM {table} "
        f"WHERE {code_col}=? ORDER BY trade_date", [code]
    ).fetch_df()
    if df.empty:
        return None
    df["adj"] = df["close"] * df["adjfactor"].fillna(1.0)
    last_dt = df["trade_date"].iloc[-1]
    cutoff = since if since is not None else last_dt - pd.Timedelta(days=days)
    prior = df[df["trade_date"] <= cutoff]
    if prior.empty:
        return None
    return (df["adj"].iloc[-1] / prior["adj"].iloc[-1] - 1) * 100


def _fmt(v, suffix="%", sign=True):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:+.1f}{suffix}" if sign else f"{v:.1f}{suffix}"


def report(con, etf_code: str) -> str:
    out = []
    prof = con.execute(
        "SELECT etf_name, category, manager, mgmt_fee, custodian_fee, "
        "total_mv, index_code, index_name, inception_date "
        "FROM dim_etf WHERE etf_code=?", [etf_code]
    ).fetchone()
    if prof is None:
        return f"[{etf_code}] 不在 dim_etf"
    name, cat, mgr, mfee, cfee, mv, idx_c, idx_n, inc = prof
    if cat not in ("equity",):
        out.append(f"⚠️ {etf_code} 类型为 {cat}，本脚本仅支持 equity-track，"
                   "以下骨架可能不完整。\n")
    mv_yi = f"{mv/1e8:.1f}亿" if mv else "—"
    out.append(f"# {name}（{etf_code}） ETF 透视骨架\n")
    out.append("## Profile")
    out.append(f"- 类型: {cat} | 管理人: {mgr} | 规模: {mv_yi}")
    out.append(f"- 管理费: {mfee}% | 托管费: {cfee}% | 成立: {inc}")
    out.append(f"- 跟踪指数: {idx_n}（{idx_c}）")

    etf_1m = _ret(con, "fact_etf_daily", "etf_code", etf_code, days=30)
    etf_3m = _ret(con, "fact_etf_daily", "etf_code", etf_code, days=90)
    last_dt = con.execute(
        "SELECT max(trade_date) FROM fact_etf_daily WHERE etf_code=?", [etf_code]
    ).fetchone()[0]
    ytd_start = pd.Timestamp(last_dt.year, 1, 1) if last_dt else None
    etf_ytd = _ret(con, "fact_etf_daily", "etf_code", etf_code, since=ytd_start)
    out.append(f"\n## Performance（截至 {last_dt}）")
    out.append(f"- ETF 近1月 {_fmt(etf_1m)} | 近3月 {_fmt(etf_3m)} | "
               f"年初至今 {_fmt(etf_ytd)}")

    q = con.execute(
        "SELECT max(report_quarter) FROM fact_etf_holding WHERE etf_code=?",
        [etf_code]).fetchone()[0]
    if q is None:
        out.append("\n## Holdings\n- ⚠️ 无持仓数据")
        return "\n".join(out)
    prev_q = con.execute(
        "SELECT max(report_quarter) FROM fact_etf_holding "
        "WHERE etf_code=? AND report_quarter<?", [etf_code, q]).fetchone()[0]
    prev_set = set() if prev_q is None else {
        r[0] for r in con.execute(
            "SELECT stock_code FROM fact_etf_holding WHERE etf_code=? AND report_quarter=?",
            [etf_code, prev_q]).fetchall()}
    h = con.execute(
        "SELECT h.rank, h.stock_code, h.stock_name, h.weight_pct, "
        "e.sw_l1, e.sw_l3, e.northbound_ratio, e.fund_count, e.inst_hold_pct "
        "FROM fact_etf_holding h LEFT JOIN dim_stock_enrich e "
        "  ON h.stock_code=e.stock_code "
        "WHERE h.etf_code=? AND h.report_quarter=? AND h.rank<=10 "
        "ORDER BY h.rank", [etf_code, q]
    ).fetch_df()

    out.append(f"\n## Top 10 Holdings（报告期 {q}"
               + (f"，对比上期 {prev_q}" if prev_q else "") + "）")
    w = []
    for _, r in h.iterrows():
        s1m = _ret(con, "fact_stock_daily", "stock_code", r.stock_code, days=30)
        w.append(r.weight_pct)
        new = "🆕" if r.stock_code not in prev_set and prev_set else "  "
        nm = str(r.stock_name or r.stock_code or "—")
        out.append(f"{int(r['rank']):>2} {new} {nm:<7} "
                   f"{r.weight_pct:>5.2f}%  {str(r.sw_l3 or '—'):<9} "
                   f"近1月 {_fmt(s1m):>7}")

    w = [x for x in w if pd.notna(x)]
    top5, top10 = sum(w[:5]), sum(w)
    hhi_norm = sum((x / top10) ** 2 for x in w) if top10 else 0
    effn = 1 / hhi_norm if hhi_norm else 0
    out.append("\n## Concentration（仅基于 Top10）")
    out.append(f"- Top5 {top5:.1f}% | Top10 {top10:.1f}% | 最大单一 {max(w):.1f}%")
    out.append(f"- Effective N(Top10内) {effn:.1f}/10（越接近10越均衡）")

    grp = h.groupby("sw_l3")["weight_pct"].sum().sort_values(ascending=False)
    out.append("\n## Sub-theme（申万三级，仅 Top10）")
    for theme, wt in grp.items():
        out.append(f"- {theme or '未分类'}: {wt:.1f}%")

    top5_perf = [_ret(con, "fact_stock_daily", "stock_code", c, days=30)
                 for c in h["stock_code"].head(5)]
    top5_perf = [x for x in top5_perf if x is not None]
    if top5_perf and etf_1m is not None:
        mean5 = sum(top5_perf) / len(top5_perf)
        dev = abs(etf_1m - mean5)
        out.append("\n## Performance Overlay")
        out.append(f"- Top5 近1月均值 {_fmt(mean5)} vs ETF {_fmt(etf_1m)} "
                   f"| 偏离 {dev:.1f}pp → "
                   + ("尾部贡献显著" if dev > 5 else "与 Top5 方向基本一致"))

    out.append("\n## Smart-Money（A股，北向已剔除出机构%避免重复）")
    for _, r in h.iterrows():
        nb = _fmt(r.northbound_ratio, sign=False)
        fc = int(r.fund_count) if pd.notna(r.fund_count) else "—"
        inst = _fmt(r.inst_hold_pct, sign=False)
        nm = str(r.stock_name or r.stock_code or "—")
        out.append(f"- {nm:<7} 北向 {nb:>6} | 公募 {fc:>5}家 | "
                   f"主动机构 {inst:>6}")

    out.append("\n## Data Notes")
    out.append(f"- 持仓口径: {q} | HHI/EffN 仅基于 Top10")
    out.append("- 北向自2024年日度披露收窄，比例为各股最新可得值")
    out.append("- 主动机构%已剔除一般法人/控股股东与陆股通")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="ETF 透视数字骨架")
    ap.add_argument("etf_code", help="6 位 ETF 代码")
    ap.add_argument("--db", default=os.environ.get("MINE_DATA_DB"),
                    help="market.duckdb 路径（或设环境变量 MINE_DATA_DB）")
    args = ap.parse_args()
    if not args.db:
        print("错误: 需要 --db 路径或环境变量 MINE_DATA_DB", file=sys.stderr)
        sys.exit(2)
    if not os.path.exists(args.db):
        print(f"错误: DB 文件不存在: {args.db}", file=sys.stderr)
        sys.exit(2)
    con = duckdb.connect(args.db, read_only=True)
    try:
        print(report(con, args.etf_code))
    finally:
        con.close()


if __name__ == "__main__":
    main()
