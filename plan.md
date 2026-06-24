# Chanlun Analyzer v2.0 — 融合架构详细计划

> 项目负责人：AI Agent 首席架构师  
> 日期：2026-06-24  
> Repo：[github.com/harshjia941-gz/chanlun-analyzer](https://github.com/harshjia941-gz/chanlun-analyzer)  
> Linear：[Chanlun Analyzer Project](https://linear.app/ruoshuiai/project/chanlun-analyzer-b2d30009263b)

---

## 一、背景

### 问题

工作空间中同时存在两个缠论 Skill：

| Skill | 位置 | 角色 |
|-------|------|------|
| `chanlun-technical` | `skills/chanlun-technical/` | 计算引擎（450 行 SKILL.md + Python 引擎） |
| `chanlun-trading` | `skills/chanlun-trading/` | 审计决策框架（111 行 SKILL.md + 11 篇 reference） |

两个 Skill 是**上下游关系**：

```
chanlun-technical         chanlun-trading
     │                         │
 数据 → 结构               结构 → 决策
 K线 → 笔/线段/中枢/背驰   门控 → 降级 → 动作 → 失效点
     │                         │
 计算层（Compute）         决策层（Decide）
```

**核心问题**：两层之间没有标准接口。AI Agent 拿到计算结果后自己拍脑袋判断，没有规则约束。

### 目标

融合为一个统一 Skill：`chanlun-analyzer`，具备：
- 三层架构：Compute → Audit → Decide
- 四种运行模式：strict / standard / quick / backtest
- 清晰的分层契约（Layer Contract）
- 可被 AI Agent 和人直接使用

---

## 二、架构设计

### 2.1 总图

```
                    ┌──────────────────────────┐
                    │     chanlun-analyzer      │
                    │      (统一调度器)          │
                    └──────────┬───────────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
          ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
          │  COMPUTE   │  │  AUDIT  │  │  DECIDE   │
          │  (计算层)   │→│  (审计层)│→│  (决策层)  │
          └───────────┘  └─────────┘  └───────────┘
```

### 2.2 Layer 1: COMPUTE（计算层）

**来源**：chanlun-technical

**职责**：纯数据 → 纯结构，无决策逻辑

```
输入: OHLCV (yfinance / akshare / CSV / IB)
流水线:
  [1] K线包含处理
  [2] 分型识别
  [3] 笔划分
  [4] 线段划分
  [5] 中枢识别 (ZG/ZD/GG/DD)
  [6] 趋势判定 (趋势/盘整/不明)
  [7] 背驰检测 (area_ratio, strength)
  [8] 买卖点标注 (1/2/3类, confidence)

输出: 结构化 JSON + compute_status
```

**compute_status 字段**：

```json
{
  "compute_status": {
    "pipeline_version": "2.0",
    "inclusion_done": true,
    "fractals_done": true,
    "strokes_done": true,
    "segments_done": true,
    "centers_done": true,
    "divergence_done": true,
    "buy_sell_points_done": true,
    "warnings": [],
    "data_quality": {
      "klines_count": 240,
      "missing_sessions": 0,
      "sufficient": true
    }
  }
}
```

### 2.3 Layer 2: AUDIT（审计层）

**来源**：chanlun-trading

**职责**：过 8 道门，决定 definition_mode，不允许跳过

```
接口契约：接收 Layer 1 JSON → 逐门检查 → 产生审计报告

GATE 1: level_gate
  检查: trade_level / confirm_level / trigger_level 是否都填写
  不过: 整份分析退回，要求先定级别

GATE 2: structure_gate
  检查: compute_status 是否按顺序完成 [1]-[6]
  缺分型/笔: → proxy_research
  缺线段:   → structure_proxy

GATE 3: type_gate
  检查: 当前同级别状态是否归类
  有效标签: center_oscillation / center_extension / center_breakout /
            uptrend / downtrend / transition_zhongyin /
            first|second|third_buy_candidate / untradable_unclear
  不明: → untradable_unclear

GATE 4: comparison_gate
  检查: 背驰声明是否点名被比较的两段同向走势、确认同级别
  没点名: → indicator_proxy

GATE 5: buy_sell_gate
  检查: 买卖点是否符合严格定义
  一买: 前一个同级别下跌趋势? c段新低? 背驰?
  二买: 一买候选存在? 第一次回抽?
  三买: 中枢边界点名? 离开+回拉+不回全部确认?
  不过: → signal_proxy

GATE 6: trigger_gate
  检查: 低级别触发是否确认
  未确认: → trigger_missing, 动作上限 observe

GATE 7: risk_gate
  检查: 失效点是否先于信号声明
  失效点未写: → 拒绝输出任何动作

GATE 8: downgrade_gate
  汇总: 任一门不过 → 输出 definition_mode + approximation_loss
```

**审计报告格式**：

```json
{
  "audit": {
    "definition_mode": "strict_chanlun | structure_proxy | signal_proxy | indicator_proxy | untradable_unclear",
    "approximation_loss": "none | low | medium | high",
    "gates_passed": [],
    "gates_failed": [],
    "downgrade_reason": null,
    "shortcuts_blocked": [],
    "requires_lower_level": false,
    "trigger_status": "confirmed | missing | pending"
  }
}
```

**4 层定义契约（Downgrade Matrix）**：

| 层级 | 名称 | 条件 | 置信度 |
|------|------|------|--------|
| L1 | `strict_chanlun` | 所有门通过，递归结构完整 | 最高 |
| L2 | `structure_proxy` | 包含/分型/笔/中枢可复现，线段/走势简化 | 中高 |
| L3 | `signal_proxy` | 日线信号类似买卖点但缺低级别递归证明 | 中 |
| L4 | `indicator_proxy` | 仅有指标或因子确认 | 低 |
| L0 | `untradable_unclear` | 结构无法命名 | 不可交易 |

### 2.4 Layer 3: DECIDE（决策层）

**来源**：chanlun-trading

**职责**：基于审计通过的信号 + 过滤器 → 产生动作

**三层过滤器**：

```
1. 结构过滤器
   definition_mode < signal_proxy → 动作上限 observe
   trigger_missing → 动作上限 observe

2. 技术过滤器
   MACD/RSI → 调整信心
   成交量/换手 → 确认/否决
   均线/趋势线 → 方向确认
   筹码分布 → 压力/支撑

3. 风险过滤器
   仓位上限检查
   止损距离可行性
   市场环境（大盘/板块）
   流动性检查
```

**动作空间**：

| 动作 | 含义 | 条件 |
|------|------|------|
| `wait` | 等待结构成型 | 结构未完成 |
| `observe` | 观察，不入场 | 信号出现但触发未确认 |
| `buy_probe` | 试探仓位 | 一买候选 + 弱触发 |
| `buy_confirmed` | 确认仓位 | 多门通过 + 触发确认 |
| `hold` | 继续持有 | 结构完好 |
| `reduce` | 减仓 | 背驰预警或失效接近 |
| `sell_exit` | 清仓离场 | 卖点触发或失效确认 |
| `rebuy` | 回补 | 卖点失效 + 结构恢复 |
| `reject` | 拒绝入场 | 假信号 |

---

## 三、四种运行模式

| 模式 | Compute | Audit | Decide | 用途 |
|------|---------|-------|--------|------|
| `strict` | 完整流水线 | 8门全过 | 全过滤器 | 深度分析单个标的 |
| `standard` | 完整流水线 | 过1-5门 | 核心过滤器 | 日常看盘 |
| `quick` | 笔+中枢代理 | 过1-3门 | 无过滤器 | 快速扫描 |
| `backtest` | 完整流水线 | 8门全过+信号列 | 仅标记不决策 | 策略回测 |

---

## 四、输出契约

### Markdown 报告（给人看）

```markdown
## <标的> · 缠论分析

**模式**: strict · definition_mode: strict_chanlun

### 级别
trade_level / confirm_level / trigger_level / approximation_loss

### 结构
current_state / center [ZG/ZD] / trend|oscillation / compared_movements

### 信号
buy|sell class / divergence / confirmation / lower_level_trigger

### 动作
action / basis / trigger / invalidation / next watch

### 审计
gates: ✓/✗ | downgrade_reason | shortcuts_blocked

> ⚠️ 本分析仅供技术研究与学习，不构成投资建议。
```

### JSON（给程序用）

```json
{
  "chanlun_analysis": {
    "symbol": "",
    "timestamp": "",
    "mode": "strict",
    "trade_level": "",
    "confirm_level": "",
    "trigger_level": "",
    "levels": { },
    "compute_status": { },
    "audit": { },
    "decision": {
      "action": "",
      "invalidation": null,
      "next_observe": "",
      "confidence": 0.0,
      "filters_applied": [],
      "filter_vetoes": []
    },
    "summary": ""
  }
}
```

---

## 五、不可妥协的跨层规则

1. 永远先定**操作级别**，没有级别就没有有效的买卖点
2. 区分 `original_definition / segment_proxy / swing_proxy / kline_proxy / indicator_proxy` 五种定义口径
3. 结构优先：走势类型 → 级别 → 中枢 → 背驰/力度 → 买卖点 → 过滤器
4. 不把小级别背驰直接当成大级别反转，除非检验了"小转大"条件
5. 每个入场都要写明：依据、触发、失效点、下一个观察点
6. MACD/RSI/成交量/换手/资金流/趋势线/均线/筹码等**只调整信心、仓位或等待纪律**，不定义缠论买卖点
7. 数据不足以做严格的分型/笔/线段/中枢时，明确降级
8. 结构不清时，宁可等待，不强行交易
9. 任何信号，先记录失效点，再讨论潜在收益
10. 没点名中枢边界+离开+回拉全部状态之前，不喊三买/三卖

### 禁止的捷径

- ❌ 指标背离 → 一买
- ❌ 突破 → 无回抽的三买
- ❌ 更高低点 → 无一买上下文的二买
- ❌ 30分钟均线/MACD → 当成30分钟结构
- ❌ 日线信号+30分钟指标 → 冒充严格多级别

---

## 六、文件结构

```
chanlun-analyzer/
├── plan.md                     ← 本文件
├── SKILL.md                    # 主入口：概述 + 运行模式 + 输出模板
│
├── compute/                    # 来自 chanlun-technical
│   ├── SKILL.md                # 计算层入口（待写）
│   ├── algorithms.md           # 算法伪代码
│   ├── chanlun_engine.py       # Python 执行引擎
│   └── research/               # 6 篇理论研究
│
├── audit/                      # 来自 chanlun-trading
│   ├── SKILL.md                # 审计层入口（待写）
│   ├── strict-original-system.md
│   ├── concepts.md
│   └── self-test-cases.md
│
├── decide/                     # 来自 chanlun-trading
│   ├── SKILL.md                # 决策层入口（待写）
│   ├── buy-sell-playbooks.md
│   ├── multi-level-recursion.md
│   ├── structure-engine.md
│   ├── filters.md
│   ├── volume-turnover-money.md
│   ├── invalidation-risk.md
│   ├── visual-reading.md
│   └── backtest-proxies.md
│
└── scripts/
    ├── standalone_analysis.py  # 单标的完整分析
    ├── batch_scan.py           # 批量扫描（待写）
    └── backtest_runner.py      # 回测（待写）
```

---

## 七、实施路线图

### Phase 1 — 归档 + 初始化 ✅ DONE

| 任务 | 状态 |
|------|------|
| 旧 skill 移至 `~/Documents/chanlun-archive/` | ✅ |
| GitHub repo 初始化 | ✅ |
| SKILL.md 统一初版 | ✅ |
| compute/ audit/ decide/ 目录结构 | ✅ |

### Phase 2 — compute 层 SKILL.md （RUO-373）

- [ ] 写 `compute/SKILL.md`：8步流水线完整伪代码引用
- [ ] `compute_status` 字段规范文档
- [ ] 数据质量检查规则（`data_quality`）
- [ ] 多级别并行计算指引
- [ ] 与 `scripts/chanlun_engine.py` 的接口契约

### Phase 3 — 改造 engine.py （RUO-374）

- [ ] 新增 `compute_status` 字段输出
- [ ] 新增 `data_quality` 检查（klines_count, missing_sessions, sufficient）
- [ ] 每步完成后标记 done flag
- [ ] 记录 warnings（segment unconfirmed, gap not verified 等）
- [ ] 保持向后兼容

### Phase 4 — audit 层 SKILL.md （RUO-375）

- [ ] 写 `audit/SKILL.md`：8道自检门可执行规则
- [ ] 每道门的输入/检查逻辑/失败后果
- [ ] `definition_mode` 降级矩阵
- [ ] 禁止的捷径清单（带检测逻辑）
- [ ] 审计报告 JSON schema
- [ ] 与 compute 输出的接口契约

### Phase 5 — decide 层 SKILL.md （RUO-376）

- [ ] 写 `decide/SKILL.md`：动作空间 + 过滤器组合
- [ ] 动作空间定义（wait/observe/probe/confirmed/hold/reduce/exit/reject）
- [ ] 三层过滤器叠加顺序
- [ ] 置信度计算规则
- [ ] 与 audit 输出的接口契约

### Phase 6 — 集成测试 （RUO-377）

- [ ] NVDA（美股）完整 strict 模式测试
- [ ] 2513.HK（港股）完整 strict 模式测试
- [ ] 验证三层串联：compute → audit → decide → 输出
- [ ] 对比旧 skill 输出一致性
- [ ] 性能测试（多级别并行 vs 串行）

### Phase 7 — 清理 + 安装 （RUO-378）

- [ ] 验证 workspace 中无残留旧 skill
- [ ] `chanlun-analyzer` 安装为 workspace skill
- [ ] 验证 AI Agent 可正确触发
- [ ] （可选）RedSkill 商店注册

---

## 八、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 计算引擎 | 保留 `chanlun_engine.py`，不重写 | 已验证，加 `compute_status` 不改逻辑 |
| 审计门 vs. 引擎 | 门控不打入引擎内部 | 引擎是"纯函数"，门控是"解释器"，职责分离 |
| 旧 Skill 处理 | 删除 workspace 引用，归档到 Documents | 避免 AI 在多个同名 Skill 间混淆 |
| 名称 | `chanlun-analyzer` | 清晰表达"分析器"角色，不是"交易系统" |
| 回测集成 | 独立脚本 + 信号列标准 | 回测需要批量模式，不适合放进 SKILL.md |
| 语言 | 英文为主，术语保留中文 | 英文给 AI 读，中文术语给缠论学习者识别 |
| 输出双格式 | Markdown + JSON | 人读 Markdown，程序消费 JSON |

---

## 九、AI Agent 调用流程

AI 收到"用缠论分析 NVDA"时的标准执行路径：

```
1. 读取 SKILL.md → 确定运行模式 + 操作级别
2. 数据获取 → yfinance/akshare/IB → OHLCV
3. 调用 compute/:
   - 读 algorithms.md 伪代码
   - 运行 chanlun_engine.py（或多级别并行调用）
   - 获取 Layer 1 JSON
4. 走 audit/ 门控:
   - 逐门检查，不过就打 downgrade 标签
   - 输出 AuditReport
5. 走 decide/ 过滤:
   - 检查 definition_mode → 决定动作上限
   - 叠加技术过滤器 → 调整置信度
   - 输出 action + invalidation + next_observe
6. 格式化输出:
   - Telegram/Discord: Markdown 报告
   - 程序调用: JSON
   - 回测: CSV 信号列
```

---

## 十、来源与致谢

- 缠论（缠中说禅技术分析体系）原创归属 **缠中说禅**
- 本 Skill 由 `chanlun-technical`（计算引擎）和 `chanlun-trading`（RedSkill 商店，审计决策框架）融合而成
- 源仓库归档地址：`~/Documents/chanlun-archive/`
- RedSkill 商店提供 chanlun-trading@1.0.0 原始包

---

⚠️ **免责声明**：本项目仅供技术研究与学习。不构成投资建议，不给具体买卖指令，不承诺任何收益。缠论存在主观性与失效风险，任何据此产生的盈亏由使用者自负。
