# mine-etf-insight

A 股 ETF 持仓透视 skill — 把一只 ETF 从「产品标签」拆回「真实持仓暴露」。

覆盖股票宽基 / 行业主题 / 因子 / QDII / 港股通 / 含债 ETF，输出 **ETF Holdings Insight Brief**：Profile / Top Holdings / Concentration / Exposure Breakdown / Performance Overlay / Smart-Money Crosscheck / Data Quality Notes。

## 何时触发

- 「分析 XXX ETF」「ETF 持仓透视」「ETF 真实暴露」
- 输入 6 位 ETF 代码（常见前缀 `510/511/512/513/515/516/159/588/562/563`）

## 依赖

| 数据源 | 角色 | 说明 |
| --- | --- | --- |
| [`wind-mcp-skill`](https://aifinmarket.wind.com.cn) | 主数据源（必需） | 需 `WIND_API_KEY`，由 wind-mcp-skill 自身的 `~/.wind-aifinmarket/config` 管理；本 skill **不**接触 key |
| `akshare` (Python) | Fallback | 无 key，覆盖股票型基金重仓；港股 / 债券 / QDII 覆盖受限 |

> `references/workflow.md` 中示例路径使用 `~/.claude/skills/wind-mcp-skill`，请按你本地 wind-mcp-skill 实际安装位置调整。

## 安装

把整个目录复制到 Claude Code 识别的 skills 路径之一即可，例如：

```bash
# 用户级
cp -r mine-etf-insight ~/.claude/skills/

# 或 openclaw / agents
cp -r mine-etf-insight ~/.openclaw/skills/
cp -r mine-etf-insight ~/.agents/skills/
```

安装后 `/mine-etf-insight` 会出现在 Skill 列表中。

## 目录结构

```
mine-etf-insight/
├── SKILL.md                          # skill 入口（含触发词、数据源路由、安全约定）
├── README.md                         # 本文件
├── .gitignore
└── references/
    ├── workflow.md                   # 详细调用流程（Profile → Holdings → Kline → 增强 → 计算 → 渲染）
    ├── template-equity.md            # 股票 / QDII 类 brief 模板
    ├── template-bond.md              # 债券 / 可转债类 brief 模板
    ├── robustness.md                 # 边界情况、降级链、单位校验
    └── akshare-bypass-proxy.md       # akshare fallback 网络配置
```

## 免责声明

本 skill 输出仅用于持仓结构透视与风险暴露分析，**不构成任何投资建议**，**不做买卖推荐**。数据可能存在延迟、缺失或口径差异，使用者自行承担决策风险。
