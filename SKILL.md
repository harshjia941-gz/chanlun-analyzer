---
name: chanlun-analyzer
description: >
  缠论（缠中说禅理论）全栈分析系统 — 三层架构（Compute → Audit → Decide），
  四模式（strict / standard / quick / backtest），8 道自检门控。
  用于 A 股/港股/ETF/指数/期货的技术面走势分析与策略回测。
  触发词：缠论、chanlun、笔、线段、中枢、背驰、买卖点、分型、区间套、
  趋势背驰、盘整背驰、第一/二/三类买点、走势终完美、中枢扩张。
  Research and study only; never issues stock tips or promises returns.
license: MIT (skill files) · 缠论 theory © 缠中说禅, used for study/commentary
---

# Chanlun Analyzer（缠论全栈分析 Skill）

> 融合版 v2.0 — 计算引擎 × 审计门控 × 决策框架

---

## 架构总览

```
COMPUTE 层           AUDIT 层            DECIDE 层
(数据→结构)          (结构→验证)          (验证→动作)

K线包含处理    →    级别门         →    结构过滤器
分型识别       →    结构门         →    技术过滤器
笔划分         →    类型门         →    风险过滤器
线段划分       →    比较门         →    动作生成
中枢识别       →    买卖点门       →
趋势判定       →    触发门         →    wait / observe
背驰检测       →    风险门         →    buy_probe / buy_confirmed
买卖点标注     →    降级门         →    hold / reduce / sell_exit / reject
```

---

## 四种运行模式（必须先声明用的是哪种）

| 模式 | Compute | Audit | Decide | 用途 |
|------|---------|-------|--------|------|
| `strict` | 完整流水线 | 8门全过 | 全过滤器 | 深度分析单个标的 |
| `standard` | 完整流水线 | 过1-5门 | 核心过滤器 | 日常看盘 |
| `quick` | 笔+中枢代理 | 过1-3门 | 无过滤器 | 快速扫描 |
| `backtest` | 完整流水线 | 8门全过+信号列 | 仅标记不决策 | 策略回测 |

默认姿态：从 `strict` 起步，仅在点名缺了哪一步结构之后才降级。

---

## COMPUTE 层（计算引擎）

**来源**：chanlun-technical

**入口**：读取 `compute/algorithms.md` 获取伪代码，执行 `scripts/chanlun_engine.py` 或按伪代码手动走流水线。

### 流水线

```
[1] K线包含处理 → [2] 分型识别 → [3] 笔划分 → [4] 线段划分
→ [5] 中枢识别 → [6] 趋势判定 → [7] 背驰检测 → [8] 买卖点标注
```

每步输出必须添加 `compute_status` 字段：

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
    "warnings": ["last_segment_unconfirmed", "second_case_gap_not_verified"],
    "data_quality": {
      "klines_count": 240,
      "missing_sessions": 0,
      "sufficient": true
    }
  }
}
```

### 数据要求
- 最少 30 根 K 线（建议 ≥100 根）
- 必须包含：date, open, high, low, close, volume
- 数据按时间升序排列

### 引擎已知简化
1. 线段第二种情况（有缺口）：当前直接确认，严格版需第二特征序列分型验证
2. 第一根 K 线方向：默认向上
3. 未完成走势：最后一笔/线段未标记 `confirmed: false`

**详细算法**：→ `compute/algorithms.md`  
**理论研究**：→ `compute/research/0X-*.md`

---

## AUDIT 层（审计门控）

**来源**：chanlun-trading

**入口**：接收 Layer 1 JSON → 逐门检查 → 产生审计报告

### 8 道自检门

#### GATE 1: level_gate
检查 `trade_level / confirm_level / trigger_level` 是否全部指定。
**不过**：整份分析退回，要求先定级别。

#### GATE 2: structure_gate
检查 `compute_status` 是否按顺序完成 [1]-[6]。
- 缺分型/笔：→ `proxy_research`
- 缺线段：→ `structure_proxy`

#### GATE 3: type_gate
检查当前同级别状态是否归类。有效标签：
`center_oscillation / center_extension / center_breakout / uptrend / downtrend / transition_zhongyin / first|second|third_buy_candidate / untradable_unclear`
**"不明"** → `untradable_unclear`

#### GATE 4: comparison_gate
背驰声明是否点名被比较的两段同向走势、确认同级别。
**没点名** → 背驰声明无效，`indicator_proxy`

#### GATE 5: buy_sell_gate
买卖点是否符合严格定义：
- 一买：前一个同级别下跌趋势？c 段新低？背驰？
- 二买：一买候选存在？第一次回抽？
- 三买：中枢边界点名？离开+回拉+不回全部确认？
**不过** → `signal_proxy`

#### GATE 6: trigger_gate
低级别触发是否确认。
**未确认** → 标注 `trigger_missing`，动作上限 `observe`

#### GATE 7: risk_gate
失效点是否先于信号声明。
**失效点未写** → 拒绝输出任何动作

#### GATE 8: downgrade_gate
汇总：任一门不过 → 输出 `definition_mode` + `approximation_loss`

### 审计报告格式

```json
{
  "audit": {
    "definition_mode": "strict_chanlun | structure_proxy | signal_proxy | indicator_proxy | untradable_unclear",
    "approximation_loss": "none | low | medium | high",
    "gates_passed": [1, 2, 3, 4, 5, 6, 7, 8],
    "gates_failed": [],
    "downgrade_reason": null,
    "shortcuts_blocked": [],
    "requires_lower_level": false,
    "trigger_status": "confirmed | missing | pending"
  }
}
```

**详细审计规则**：→ `audit/strict-original-system.md`  
**概念定义/冲突**：→ `audit/concepts.md`  
**假阳性自检**：→ `audit/self-test-cases.md`

---

## DECIDE 层（决策框架）

**来源**：chanlun-trading

**入口**：基于审计通过的信号 + 过滤器 → 产生动作

### 过滤器叠加顺序

1. **结构过滤器**：`definition_mode < signal_proxy` → 动作上限 `observe`；`trigger_missing` → 动作上限 `observe`
2. **技术过滤器**：MACD/RSI 调信心；成交量/换手 确认/否决；均线/趋势线 方向确认；筹码分布 压力/支撑
3. **风险过滤器**：仓位上限、止损距离、市场环境、流动性

### 动作空间

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

**买卖点详细流程**：→ `decide/buy-sell-playbooks.md`  
**多级别递归/区间套**：→ `decide/multi-level-recursion.md`  
**结构引擎细节**：→ `decide/structure-engine.md`  
**技术过滤器**：→ `decide/filters.md`  
**量/换手/资金流**：→ `decide/volume-turnover-money.md`  
**失效/止损/仓位**：→ `decide/invalidation-risk.md`  
**读图方法**：→ `decide/visual-reading.md`  
**回测代理规则**：→ `decide/backtest-proxies.md`

---

## 不可妥协的规则（跨层通用）

1. 永远先定**操作级别**，没有级别就没有有效的买卖点
2. 区分 `original_definition / segment_proxy / swing_proxy / kline_proxy / indicator_proxy` 五种定义口径
3. 结构优先：走势类型 → 级别 → 中枢 → 背驰/力度 → 买卖点 → 过滤器
4. 不把小级别背驰直接当成大级别反转，除非检验了"小转大"条件
5. 每个入场都要写明：依据、触发、失效点、下一个观察点
6. MACD/RSI/成交量/换手/资金流/趋势线/均线/筹码等技术过滤器**只调整信心、等待纪律或仓位**，不定义缠论买卖点
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

## 输出格式

### Markdown 报告（给人看）

```markdown
## <标的> · 缠论分析

**模式**: strict · definition_mode: strict_chanlun

### 级别
trade_level / confirm_level / trigger_level / definition_mode / approximation_loss

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

### JSON 输出（给程序用）

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

## 如何加载 reference

| 场景 | 读取文件 |
|------|---------|
| 需要执行计算 | `compute/algorithms.md` |
| 需要深入某个环节理论 | `compute/research/0X-*.md` |
| 需要过审计门 | `audit/strict-original-system.md` |
| 概念冲突/术语 | `audit/concepts.md` |
| 需要判断买卖点流程 | `decide/buy-sell-playbooks.md` |
| 多级别联立 | `decide/multi-level-recursion.md` |
| 叠加技术过滤器 | `decide/filters.md` |
| 量价分析 | `decide/volume-turnover-money.md` |
| 风险管理 | `decide/invalidation-risk.md` |
| 读图分析 | `decide/visual-reading.md` |
| 做回测 | `decide/backtest-proxies.md` |
| 自检假阳性 | `audit/self-test-cases.md` |

---

## 执行引擎

```bash
# 数据获取 + 完整分析
python scripts/chanlun_engine.py --symbol NVDA --levels 30F,5F,1F -o result.json

# CSV 输入
python scripts/chanlun_engine.py --csv data.csv -o result.json

# 旧笔模式
python scripts/chanlun_engine.py --sample --pen-mode old
```

---

## 使用边界与局限

### 适用
- 有足够流动性的股票/期货/外汇
- 数据量充足（≥100 根 K 线）
- 已确定操作级别

### 不适用
- 流动性极差的标的（K 线形态失真）
- 新股上市初期（连续一字涨停）
- 极短线秒级/Tick 级（噪音过大）

### 重要提醒
1. 缠论不是预测工具，买卖点基于已完成走势的几何结构
2. 级别必须统一，混淆级别是最常见错误
3. MACD 是辅助，最终判定应基于中枢结构本身
4. 背驰段进入 ≠ 背驰确认，需等待 C 段走势类型完成
5. 建议配合基本面分析、仓位管理、风险控制一起使用

---

## 来源与致谢

- 缠论（缠中说禅技术分析体系）原创归属 **缠中说禅**，本 Skill 是对其公开理论的操作化整理与研究性解读
- 本 Skill 由 `chanlun-technical`（计算引擎）和 `chanlun-trading`（审计决策框架）融合而成
- 源仓库归档地址：`~/Documents/chanlun-archive/`

---

⚠️ **免责声明**：本 Skill 仅用于技术研究与学习。不构成投资建议，不给具体买卖指令，不承诺任何收益。缠论存在主观性与失效风险，任何据此产生的盈亏由使用者自负。
