# akshare 调用 — 绕过系统代理

## 背景

macOS 系统级代理（Tailscale / Clash / 公司 VPN）会注入 IPv6 出口，拦截 akshare 的 HTTP 请求。

症状：
```
ERR: Failed to parse: http://<system-proxy-ipv6>:<port>
```

## 标准绕过代码

```python
import os
os.environ['no_proxy'] = '*'

import urllib.request
urllib.request.getproxies = lambda: {}

import requests
old_send = requests.adapters.HTTPAdapter.send
def new_send(self, request, **kwargs):
    kwargs['proxies'] = {}
    return old_send(self, request, **kwargs)
requests.adapters.HTTPAdapter.send = new_send

# 此后可安全调用 akshare
import akshare as ak
```

**关键**：必须先 patch `urllib.request.getproxies` 和 `requests.adapters.HTTPAdapter.send` 两处。仅设环境变量不够（系统代理是 macOS 内核级注入）。

## 常用 akshare 基金接口

| 接口 | 用途 | 参数 |
|---|---|---|
| `fund_portfolio_hold_em` | 股票型基金重仓股（A 股 ETF）| `symbol`, `date="2025"` |
| `fund_portfolio_bond_hold_em` | 债券型基金持仓（含债 ETF）| `symbol`, `date="2025"` |
| `fund_portfolio_industry_allocation_em` | 行业分布 | `symbol`, `date="2025"` |
| `fund_portfolio_change_em` | 持仓变动 | `symbol`, `date="2025"` |

返回的 `season` / `季度` 字段会含具体季度标签（如 "2025年4季度股票持仓明细"），用于对齐报告期。

## 与 Wind 的对比策略

- **首选 Wind**（更准、更全面、支持 NL 查询）
- **akshare 作 fallback**：
  - Wind license 限制时（如港股通持股）
  - 需要**多季度历史持仓**做轮换分析
  - 用户没有 Wind key 时（v2 增强）

## 何时不调 akshare

- ETF 已经 Wind 全字段拿到 → 不必重复
- 仅需要"最新一期"快照 → Wind 已足够
- 海外标的（港股 / 美股 fund 不在 akshare 覆盖）
