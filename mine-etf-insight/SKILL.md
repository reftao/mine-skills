---
name: mine-etf-insight
description: A 股 ETF 持仓透视 - 把一只 ETF 从「产品标签」拆回「真实持仓暴露」。覆盖股票宽基 / 行业主题 / 因子 / QDII / 港股通 / 含债 ETF。输出 ETF Holdings Insight Brief，包含 Profile / Top Holdings / Concentration / Exposure Breakdown / Performance Overlay / Smart-Money Crosscheck / Data Quality Notes。当用户提到分析 ETF 持仓、ETF 透视、ETF overlap、ETF 真实暴露、512xxx/510xxx/513xxx/511xxx 等场景使用。
---

# mine-etf-insight

## 何时触发

用户提到以下任一场景：
- 「分析 XXX ETF」「ETF 持仓透视」「ETF 真实暴露」「ETF 透视报告」
- ETF 代码（6 位数字，常见前缀 `510/511/512/513/515/516/159/588/562/563`）
- 「我已经持有 X，再买 Y ETF 会不会重复暴露」（v2，本版未实现）

## 核心思路

把 ETF 名字 → 真实持仓 → 风险与暴露。**不做推荐**，**不做买卖建议**。

## 数据源（按优先级）

**主数据源：`wind-mcp-skill`**（需要 WIND_API_KEY，由该 skill 的 config 自行管理；本 skill 调用时不要手动传 key、不要在命令里出现 key 明文，依赖环境配置）

- `fund_data.get_fund_info` — ETF 档案（必调）
- `fund_data.get_fund_holdings` — 持仓（必调）
- `fund_data.get_fund_kline` — ETF 近 3 月日 K（必调）
- `analytics_data.get_financial_data` — 成分股表现 / 行业 / smart-money（按需）
- `bond_data.get_bond_basicinfo` — 可转债 → 正股映射（仅可转债 ETF）

**Fallback：akshare**（无 key）
- `fund_portfolio_hold_em(symbol, date)` — 股票型基金重仓
- `fund_portfolio_bond_hold_em(symbol, date)` — 债券型基金持仓（多季度历史）

调用 akshare 时**必须先清空代理**（macOS 系统代理会拦 IPv6 流量），见 references/akshare-bypass-proxy.md。

## 工作流（高层）

```
1. 输入 ETF code (6 位数字，自动补 .SH/.SZ 后缀)
2. 调 get_fund_info → 拿到「投资类型_二级分类」，立刻分支：
   ├─ "被动指数型债券基金"     → 走 [bond-track]
   ├─ "国际(QDII)股票型基金"   → 走 [qdii-track]
   └─ 其他股票型              → 走 [equity-track]
3. 按 track 调对应 wind 接口，拿 holdings + ETF kline
4. 按 ticker 后缀解析持仓代码 (.SH/.SZ/.HK/.O/.N/.IB/转债代码) → 路由不同的成分股增强 API
5. 计算集中度、sub-theme、performance overlay
6. 按对应 track 的模板渲染 brief
```

详细工作流见 `references/workflow.md`。

## ETF 类型分支表

| 投资类型_二级分类 | Track | 适用模板 | 说明 |
|---|---|---|---|
| 被动指数型股票型基金 / 增强指数型股票型基金 | **[equity-track]** | 完整 8 节 brief | 510/512/515/516/159 类 |
| 国际(QDII)股票型基金 | **[qdii-track]** | 8 节，第 5/7 节适配 | 513/159 部分；含港股通 ETF |
| 被动指数型债券基金 | **[bond-track]** | 5 节 brief | 511/513XX 含债类 |
| 其他 / 货币型 / 商品型 | 不支持 | 提示用户切回 wind 直接查询 | v2 再扩展 |

## 持仓代码后缀路由

| 后缀 | 标的类型 | smart-money 路径 | 行业归类 |
|---|---|---|---|
| `.SH` / `.SZ`（6/0/3 开头）| A 股股票 | `analytics_data`: 北向 + 公募重仓家数 | 申万三级 + 主营业务 |
| `.HK` | 港股 | `analytics_data`: 内地公募持有家数（**港股通持股 license 缺）| WIND 行业明细 |
| `.O` / `.N` / `.K` | 美股 | `analytics_data`: 13F 持有家数 + 持仓总市值 | WIND 行业明细 |
| `.IB` | 银行间债券 | N/A | N/A |
| 转债代码（1XXXXX / 1XXXXX.SZ）| 可转债 | 先 `bond_data` 拿正股代码，再走 A 股路径 | 正股的申万三级 |
| 国债代码（0XXXXX）| 利率债 | N/A | 标"利率债" |

## Brief 模板入口

- A 股股票型 / QDII：见 `references/template-equity.md`
- 含债型：见 `references/template-bond.md`

## Robustness Handlers

35 条已识别的边界情况见 `references/robustness.md`。**调用前必读**，避免重复踩坑。

## 输出要求

1. **明确披露报告期**：不要写"最新一期"，要写具体季度（推断自最早重仓时间 max，或 akshare 季度标签）
2. **不做买卖建议**：brief 末尾必须有「本 brief 不是 ETF 推荐工具，也不是买卖建议」
3. **数据缺口必须显式标注**：null 字段、API 失败、license 限制都要在 Data Quality Notes 中说明
4. **集中度 / Effective N 必须注明仅基于 Top 10**：避免误以为是全组合分散度
5. **货币 / 单位口径必须标注**：QDII 表现是本币 / ETF 是人民币 / 债券单位是"张"

## 关键 don'ts

- ❌ 不要在 Bash 命令里出现 `WIND_API_KEY=ak_...` 明文
- ❌ 不要为债券 ETF 跑 Top 5 成分股 perf overlay（概念失效）
- ❌ 不要为债券 ETF 跑 smart-money（概念失效）
- ❌ 不要把"前十大重仓股"权重当成全组合 HHI
- ❌ 不要假设 holdings 必然返回 10 行（国债 ETF 通常 5 行）
- ❌ 不要假设字段名跨 ETF 一致（A 股版 vs QDII 版 vs 债券版字段名都不同）
