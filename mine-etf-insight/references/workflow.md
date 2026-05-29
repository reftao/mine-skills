# Workflow — 详细调用流程

## 通用准备

调用 wind-mcp-skill 时使用以下命令格式（**不要在命令里写 key**，依赖 `~/.wind-aifinmarket/config` 自动加载）：

```bash
WIND_DIR=$(ls -d \
  ~/.claude/skills/wind-mcp-skill \
  ~/.agents/skills/wind-mcp-skill \
  ./.claude/skills/wind-mcp-skill \
  2>/dev/null | head -1)
cd "$WIND_DIR" && node scripts/cli.mjs call <server> <tool> '<json>'
```

> 上面 `WIND_DIR=...` 这一段会自动探测 `wind-mcp-skill` 的安装位置（兼容用户级 / 全局 / 项目级三种装法）。下文所有 `node scripts/cli.mjs ...` 命令都假定已经在 `wind-mcp-skill` 目录下，按需复用上面的 `cd "$WIND_DIR"`。若 `WIND_DIR` 为空，说明 `wind-mcp-skill` 没装好，先回头按 mine-skills README 安装。

如果命中 `KEY_MISSING`，按 wind-mcp-skill 的提示执行 `setup-key`，**不要把 key 写到任何文件或脚本中**。

## ETF 代码补全规则

输入 6 位数字代码，按前缀补后缀：
- `5xxxxx` / `6xxxxx` / `588xxx` → `.SH`
- `1xxxxx` / `0xxxxx` / `3xxxxx` → `.SZ`

## Step 1: Profile（所有 track 共享）

```bash
node scripts/cli.mjs call fund_data get_fund_info \
  '{"question":"<code>.SH基金基本档案 发行方 管理费率 托管费率 基金规模 跟踪指数 成立日期 投资类型"}'
```

**关键提取**：`投资类型_二级分类` 字段 → 决定分支

## Step 2: Holdings（按 track 不同）

### [equity-track] / [qdii-track]

```bash
node scripts/cli.mjs call fund_data get_fund_holdings \
  '{"question":"<code>.SH最新一期前十大重仓股 证券代码 简称 持仓权重 持仓市值 持仓占流通股比例 最早重仓时间"}'
```

### [bond-track]

```bash
node scripts/cli.mjs call fund_data get_fund_holdings \
  '{"question":"<code>.SH最新一期前十大持仓 包括债券 证券代码 简称 持仓权重 持仓市值 持仓数量"}'
```

**关键提取**：从「最早重仓时间」max 推断报告期；若该字段不存在（QDII/债券常见），改为"最新披露口径"并在 Data Quality 中标注。

## Step 3: ETF Kline（所有 track）

取最近 ~3 个月日 K（用 today − 90d）：

```bash
node scripts/cli.mjs call fund_data get_fund_kline \
  '{"windcode":"<code>.SH","begin_date":"YYYYMMDD","end_date":"YYYYMMDD"}'
```

提取 1M / 3M 区间收益率。

## Step 4: 持仓增强（按后缀路由）

### A 股股票（.SH / .SZ）—— equity-track 主路径

**Top 5 表现 + 行业一次性获取**：

```bash
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<stock1.SH> <stock2.SH> ... 近1月 近3月 年初至今 涨跌幅 最新收盘价 申万三级行业 主营业务"}'
```

**Smart-money（公募 + 北向 + 机构）—— 措辞降级链**：

1. 首选措辞：`"<codes> 最新一期 北向资金持股比例 持有基金数量 机构持股比例合计"`
2. 校验：返回的「持有基金数量」单位必须是「个」。如果单位是「%」（说明字段被错误解析为"基金持股比例"），换措辞重试
3. 重试措辞：`"<codes> 最新报告期 持有基金数量"` （单独跑一次）
4. 极端 fallback：单 ticker 跑 `"<single_code> 最新报告期 公募基金重仓家数 持有基金数量"`

### 港股（.HK）—— qdii-track 港股分支

```bash
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<hk_codes> 近1月 近3月 年初至今 涨跌幅 最新收盘价 WIND行业明细"}'
```

**Smart-money（**港股通持股 license 缺**，用内地公募作 fallback）**：

```bash
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<hk_codes> 最新报告期 持有该股票的内地公募基金数量"}'
```

### 美股（.O / .N / .K）—— qdii-track 美股分支

```bash
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<us_codes> 近1月 近3月 年初至今 涨跌幅 最新收盘价 WIND行业明细"}'

# 13F
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<us_codes> 最新报告期 13F机构持有家数 13F机构持仓总市值"}'
```

### 可转债（持仓代码为转债）—— bond-track 可转债分支

**两跳映射**：

```bash
# 1. 转债 → 正股
node scripts/cli.mjs call bond_data get_bond_basicinfo \
  '{"question":"<bond_codes> 正股代码 正股简称 申万行业"}'

# 2. 正股代码 → 申万行业
node scripts/cli.mjs call analytics_data get_financial_data \
  '{"question":"<underlying_stock_codes> 申万一级行业 申万三级行业"}'
```

### 利率债（持仓代码全为国债 / 政金 / 地方债）—— bond-track 利率债分支

**跳过 Step 4 的所有增强**。直接进入模板渲染。

## Step 5: 计算

### Concentration（用 Top 10 权重列表 `w[]`）

```python
top5 = sum(w[:5])
top10 = sum(w)
hhi_top10 = sum(x*x for x in w) / 10000   # 权重以 % 输入，除以 10000 归一
eff_n_top10 = 1 / hhi_top10
max_pos = max(w)
```

**输出时必须标注**：「仅基于 Top 10 持仓，全组合分散度高于该数值」

### Sub-theme（基于行业一次申万 + 三级 + 主营业务字段分组）

不预设主题词典，按以下规则动态分组：

1. 取所有 Top N 持仓的「申万三级行业」
2. 同三级行业 → 合并为一组
3. 同申万一级但不同三级 → 标注"同一级不同子行业"
4. 主营业务 > 80% 集中在某一产品线 → 在分组里标注主要业务

例：半导体 ETF 的「数字芯片设计」三级行业下，按主营拆为「算力 / 存储 / 内存接口」子组。

### Performance overlay 偏离判断

```python
top5_perf_mean = mean([s.近1月涨跌幅 for s in top5_stocks])
deviation = abs(etf.1M_return - top5_perf_mean)

if deviation > 5:  # 5个百分点
    # 触发"尾部贡献为主"叙事
    narrative = "ETF 表现与 Top 5 简单均值偏离 X%，尾部持仓贡献显著"
else:
    narrative = "ETF 表现与 Top 5 持仓方向基本一致"
```

## Step 6: 渲染 Brief

按 track 选模板：
- equity / qdii → `template-equity.md`
- bond → `template-bond.md`
