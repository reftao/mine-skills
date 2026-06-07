---
name: mine-etf-brief
description: ETF 透视报告（离线版）— 基于本地 DuckDB（mine-data 导出的 market.duckdb）生成一只 A 股股票型 ETF 的透视 Brief。确定性数字由 report.py 计算，叙事由 agent 撰写。覆盖 Profile / Top Holdings / Concentration / Sub-theme / Performance Overlay / Smart-Money。当用户要求「ETF 透视」「ETF 持仓分析」「分析某只 ETF」「每日 ETF 推送」，或给出 512xxx/510xxx/159xxx 等代码时使用。
---

# mine-etf-brief

## 何时触发

- 「分析 XXX ETF」「ETF 持仓透视」「ETF 真实暴露」「每日 ETF 报告」
- 给出 6 位 ETF 代码（510/512/515/516/159/588 等股票型）
- 定时任务随机选一只 ETF 出透视报告

## 与 mine-etf-insight 的区别

- `mine-etf-insight`：在线版，调 wind-mcp-skill，吃积分，适合人工交互即席分析。
- **`mine-etf-brief`（本 skill）**：离线版，只读本地 DuckDB，零积分、可无人值守，适合
  定时批量推送。**当前仅支持 equity-track（A 股股票型 ETF）**，债券/跨境/商品后续扩展。

## 强依赖（必须先就位）

1. **DuckDB 数据文件** `market.duckdb`：由 mine-data 项目 ETL 生成并拷贝到本机。
   必须含表：`dim_etf` / `fact_etf_daily` / `fact_etf_holding` / `fact_stock_daily` /
   `dim_stock_enrich`。
2. **Python 依赖**：`duckdb`、`pandas`。
3. DB 路径通过环境变量 `MINE_DATA_DB` 或 `--db` 参数传入，**不要硬编码**。

## 工作流

### Step 1 — 定位 DB + 脚本（不硬编码路径）

```bash
SKILL_DIR=$(ls -d ~/.claude/skills/mine-etf-brief ~/.agents/skills/mine-etf-brief \
  ./.claude/skills/mine-etf-brief 2>/dev/null | head -1)
# DB 路径：优先环境变量 MINE_DATA_DB，否则按下列候选探测（~ 自动展开到当前用户家目录，
# 不写死用户名）。mini/小龙虾 部署位置为 ~/Serve/mine-data/db/market.duckdb。
DB="${MINE_DATA_DB:-$(ls \
  ~/Serve/mine-data/db/market.duckdb \
  ~/mine-data/db/market.duckdb \
  ./db/market.duckdb \
  2>/dev/null | head -1)}"
```

若 `$DB` 为空，说明数据未就位，**停止并提示用户**：需先从 mine-data 拷贝 `market.duckdb`
到 `~/Serve/mine-data/db/`（或设环境变量 `MINE_DATA_DB`）。

### Step 1.5 — 选标的（仅「随机/每日推送」场景）

用户**没给具体代码**（如「随便推一只」「今日 ETF」「定时任务」）时，先随机选一只
流动性达标的 equity ETF：

```bash
python "$SKILL_DIR/scripts/pick.py" --db "$DB" \
  --history-file ~/.etf_push_history --verbose
```

- 默认池：equity-track、在市、有持仓、近 30 日均成交额 ≥ 5千万（约 400 只）
- `--history-file` 自动避开最近 30 次已推，实现每日不重样
- stdout 为纯代码，直接传给 Step 2

用户给了代码则跳过本步。

### Step 2 — 跑数字骨架

```bash
python "$SKILL_DIR/scripts/report.py" <etf_code> --db "$DB"
```

脚本输出确定性骨架（Profile/Performance/Holdings/Concentration/Sub-theme/Overlay/
Smart-Money/Data Notes）。**所有数字以脚本输出为准，agent 不得自行重算或改动数字。**

若脚本输出含 `⚠️ 类型为 ... 仅支持 equity-track`，说明该 ETF 非股票型，
告知用户当前版本不支持，不要硬编出报告。

### Step 3 — agent 撰写叙事，组装 Brief

读 `references/narrative-guide.md`，在骨架之上补写叙事段落，组装成最终 Brief。
叙事只做**解读**，不引入骨架之外的新数字。

## 关键 don'ts

- ❌ 不要自行重算 HHI/收益率/权重等任何数字——一律用 report.py 输出
- ❌ 不要硬编码 DB 路径或 skill 路径（用探测 / 环境变量）
- ❌ 不要给买卖建议；Brief 末尾必须有免责声明
- ❌ 非 equity-track 的 ETF 不要强行出报告
- ❌ 不要把"前十大权重"当成全组合分散度（脚本已用 Top10 内归一化的 Effective N）
