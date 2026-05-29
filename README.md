# mine-skills

一组可被 Claude Code（以及 Codex / OpenCode 等 40+ agent）直接调用的金融投资 Skill 集合。

## 安装

推荐使用 [`npx skills`](https://github.com/vercel-labs/skills)，一行命令搞定：

```bash
npx skills add reftao/mine-skills
```

不带 flag 时是**交互式**：会让你勾选要装的 skill、目标 agent（Claude Code / Codex / OpenCode / Cursor / Windsurf / Gemini CLI 等）、以及安装方式（软链 / 拷贝）。跟着提示走即可。

### 常用变体

```bash
# 看看仓库里有哪些 skill
npx skills add reftao/mine-skills --list

# 直装单个 skill 到 Claude Code，全局
npx skills add reftao/mine-skills --skill mine-etf-insight -g -a claude-code

# 同时装到多个 agent
npx skills add reftao/mine-skills --skill mine-etf-insight \
  -a claude-code -a codex -a opencode -g

# 装仓库里所有 skill，跳过所有确认
npx skills add reftao/mine-skills --all -y
```


## 当前可用 Skill

| 名称 | 简介 |
|---|---|
| [`mine-etf-insight`](./mine-etf-insight/) | A 股 ETF 持仓透视：从「产品标签」拆回「真实持仓暴露」，输出 ETF Holdings Insight Brief。 |

后续持续新增。

## 验证 & 卸载

```bash
npx skills list           # 列出已安装的 skill
npx skills remove <name>  # 卸载
```

或在 Claude Code 内执行 `/skills` 查看当前生效列表。

## 备选：手动安装（不想装 npx 时）

```bash
# 克隆到任意位置
git clone https://github.com/reftao/mine-skills.git ~/mine-skills

# 软链到 Claude Code 用户级 skills 目录（以 mine-etf-insight 为例）
mkdir -p ~/.claude/skills
ln -s ~/mine-skills/mine-etf-insight ~/.claude/skills/mine-etf-insight

# 更新：cd ~/mine-skills && git pull
```

项目级安装：把软链/拷贝目标换成 `<项目根>/.claude/skills/` 即可。

## 依赖说明

> ⚠️ 本仓库的 skill **强依赖 `wind-mcp-skill`** 作为主数据源（覆盖 A 股 / 港股 / 美股行情、ETF 持仓、财务等）。装本仓库之前请先安装并配置好 `wind-mcp-skill`：
>
> - 需要 `WIND_API_KEY`，到 [aifinmarket.wind.com.cn/#/user/overview](https://aifinmarket.wind.com.cn/#/user/overview) 开发者中心获取
> - key 由 `wind-mcp-skill` 自行管理，本仓库的 skill 调用时不要传 key、不要在命令里出现明文
>
> 没装 wind-mcp-skill，本仓库里的 skill 都无法正常工作。

各 Skill 的额外依赖见对应 `SKILL.md`：

- `mine-etf-insight`：主数据源 `wind-mcp-skill`；备用源依赖 `akshare`、`mootdx` 等 Python 包。详见 [`mine-etf-insight/SKILL.md`](./mine-etf-insight/SKILL.md)。
