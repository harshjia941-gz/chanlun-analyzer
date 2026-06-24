# 笔（Bi/Stroke）的精确定义与判定算法

> 信息源：缠中说禅《教你炒股票》第62、65、77、81课原文（新浪博客 chzhshch）
> 整理日期：2026-04-18

---

## 一、前置处理：K线包含关系

### 1.1 包含关系定义

相邻两根K线 `[d_i, g_i]` 和 `[d_{i+1}, g_{i+1}]`（d=最低价, g=最高价），若满足：

```
(d_i <= d_{i+1} 且 g_i >= g_{i+1})  或  (d_i >= d_{i+1} 且 g_i <= g_{i+1})
```

即一根K线的高低点完全在另一根的范围内，则称两K线有**包含关系**。

### 1.2 包含处理规则（原文第62、65课）

根据当前趋势方向合并：

```
若当前方向为"向上"（g_n > g_{n-1} 或趋势判定为向上）：
    新高 = max(g_i, g_{i+1})
    新低 = max(d_i, d_{i+1})    // 取较高低点
    
若当前方向为"向下"（d_n < d_{n-1} 或趋势判定为向下）：
    新低 = min(d_i, d_{i+1})
    新高 = min(g_i, g_{i+1})    // 取较低高点
```

合并后的K线替代原来的两根，继续与下一根比较（遵守顺序原则，从左到右依次处理）。

### 1.3 方向判定（原文第65课）

当第n根与第n-1根**不是**包含关系，而第n根与第n+1根是包含关系时：

```
若 g_n > g_{n-1}，则当前方向为"向上"
若 d_n < d_{n-1}，则当前方向为"向下"
```

> 注：两者不可能同时不成立（否则第n根与第n-1根也是包含关系，与假设矛盾）。

### 1.4 伪代码：包含处理

```python
def process_inclusion(klines):
    """
    klines: list of (high, low) tuples
    returns: list of merged (high, low) tuples, no adjacent inclusion
    """
    if len(klines) <= 1:
        return klines
    
    result = [klines[0]]
    
    for i in range(1, len(klines)):
        prev = result[-1]
        curr = klines[i]
        
        # 检查是否有包含关系
        if is_inclusive(prev, curr):
            # 确定方向：向前找非包含的K线
            direction = determine_direction(result, len(result) - 1)
            
            if direction == 'up':
                merged = (max(prev[0], curr[0]), max(prev[1], curr[1]))
            else:  # down
                merged = (min(prev[0], curr[0]), min(prev[1], curr[1]))
            
            result[-1] = merged
        else:
            result.append(curr)
    
    return result

def is_inclusive(a, b):
    """检查两根K线是否有包含关系"""
    return (a[0] <= b[0] and a[1] >= b[1]) or \
           (a[0] >= b[0] and a[1] <= b[1])

def determine_direction(result, idx):
    """确定当前方向：向回找非包含的K线来判定"""
    if idx == 0:
        return 'up'  # 默认
    # 比较与前一元素的关系
    prev = result[idx - 1]
    curr = result[idx]
    if curr[1] > prev[1]:  # g_n > g_{n-1}
        return 'up'
    else:
        return 'down'
```

---

## 二、分型（Fractal）定义

### 2.1 顶分型（原文第62课）

经过包含处理后的三根相邻K线 K1, K2, K3：

```
顶分型条件：
    g2 > g1 且 g2 > g3   （K2高点为三者最高）
    d2 > d1 且 d2 > d3   （K2低点为三者最高）
```

K2的最高点称为该顶分型的**顶**（Top）。

### 2.2 底分型（原文第62课）

```
底分型条件：
    d2 < d1 且 d2 < d3   （K2低点为三者最低）
    g2 < g1 且 g2 < g3   （K2高点为三者最低）
```

K2的最低点称为该底分型的**底**（Bottom）。

### 2.3 分型标记伪代码

```python
def find_fractals(merged_klines):
    """
    merged_klines: 包含处理后的K线列表 [(high, low), ...]
    returns: list of {index, type: 'top'|'bottom', value, raw_range}
    """
    fractals = []
    for i in range(1, len(merged_klines) - 1):
        g1, d1 = merged_klines[i-1]
        g2, d2 = merged_klines[i]
        g3, d3 = merged_klines[i+1]
        
        if g2 > g1 and g2 > g3 and d2 > d1 and d2 > d3:
            fractals.append({
                'index': i,
                'type': 'top',
                'value': g2,      # 顶 = 最高价
                'low': d2
            })
        elif d2 < d1 and d2 < d3 and g2 < g1 and g2 < g3:
            fractals.append({
                'index': i,
                'type': 'bottom',
                'value': d2,      # 底 = 最低价
                'high': g2
            })
    
    return fractals
```

---

## 三、笔（Bi/Stroke）定义

### 3.1 基本定义（原文第62、65、77课）

**笔**是连接相邻的顶和底（或底和顶）的线段。具体规则：

1. **一顶一底交替**：笔必须由一个顶分型和一个底分型构成，不能两个同性质分型构成笔
2. **不共用K线**：顶分型和底分型经过包含处理后，不允许共用K线（结合律要求）
3. **独立K线**：顶底之间至少有1根不属于顶底分型的独立K线
4. **空间约束**（原文第77课）：顶分型中最高K线的区间，至少要有一部分高于底分型中最低K线的区间。即**顶必须在底的上方**，否则不能成笔

### 3.2 旧笔定义（第62课原始定义）

> 顶和底之间还有一根K线。在实际分析中，都必须要求顶和底之间都至少有一K线当成一笔的最基本要求。

旧笔条件：
- 顶底分型不共用K线
- **经过包含处理后**，顶底分型之间存在至少1根独立K线

### 3.3 新笔定义（第81课修订，2007-09-24）

缠师原文：

> 1. 顶分型与底分型经过包含处理后，不允许共用K线（与旧笔相同）
> 2. 在满足1的前提下，顶分型中最高K线和底分型的最低K线之间（**不包括这两K线**），**不考虑包含关系**，至少有**3根（含）以上**原始K线

**新旧笔区别核心**：

| 条件 | 旧笔 | 新笔 |
|------|------|------|
| 分型不共用K线 | ✅ 必须 | ✅ 必须 |
| 独立K线判定范围 | 包含处理后 | **不考虑包含关系**（看原始K线） |
| 独立K线数量 | ≥1根（处理后） | ≥3根原始K线（处理前） |
| 宽严程度 | 较严 | 略松 |

新笔的实质放松点：两根被包含处理合并掉的K线，在新笔定义中仍然各算一根。

### 3.4 笔的划分步骤（原文第77课）

**步骤一**：确定所有符合标准的分型

**步骤二**：处理同性质分型
- 如果前后两分型同性质：
  - 两个顶：前面的低于后面的 → X掉前面的，保留后面的
  - 两个底：前面的高于后面的 → X掉前面的，保留后面的
  - 相等的：先保留

**步骤三**：检查相邻分型
- 相邻为顶和底 → 构成一笔
- 相邻为同性质 → 继续处理：
  - 连续的顶后出现新底 → 第一个顶与新底连线成笔，中间顶X掉
  - 连续的底后出现新顶 → 第一个底与新顶连线成笔，中间底X掉

### 3.5 完整伪代码：笔的判定

```python
def determine_pens(raw_klines, mode='new'):
    """
    raw_klines: 原始K线列表 [(high, low, open, close), ...]
    mode: 'old' 或 'new'
    returns: list of pen endpoints [(start_idx, end_idx, direction), ...]
    """
    
    # ====== Step 1: 包含处理 ======
    merged = process_inclusion(raw_klines)
    
    # ====== Step 2: 找分型 ======
    fractals = find_fractals(merged)
    
    # ====== Step 3: 处理同性质分型（步骤二） ======
    filtered = filter_same_type_fractals(fractals)
    
    # ====== Step 4: 构造笔 ======
    pens = []
    i = 0
    while i < len(filtered) - 1:
        curr = filtered[i]
        nxt = filtered[i + 1]
        
        # 跳过同性质
        if curr['type'] == nxt['type']:
            i += 1
            continue
        
        # 检查不共用K线（结合律）
        if not shares_kline(curr, nxt, merged):
            # 检查独立K线条件
            if mode == 'old':
                if has_independent_kline_old(curr, nxt, merged):
                    pens.append(make_pen(curr, nxt))
                    i += 1
                    continue
            else:  # new
                if has_independent_kline_new(curr, nxt, raw_klines):
                    # 检查空间约束：顶必须高于底
                    if space_constraint_satisfied(curr, nxt):
                        pens.append(make_pen(curr, nxt))
                        i += 1
                        continue
        
        i += 1
    
    # ====== Step 5: 处理连续同性质（步骤三） ======
    pens = resolve_consecutive_same_type(pens, filtered)
    
    return pens


def has_independent_kline_old(top_or_bottom1, top_or_bottom2, merged):
    """
    旧笔：包含处理后，两个分型之间至少1根独立K线
    """
    idx1 = top_or_bottom1['index']
    idx2 = top_or_bottom2['index']
    # 分型各占3根中的中间一根，不共用K线意味着 idx2 >= idx1 + 2
    # 独立K线：idx1+1 到 idx2-1 之间至少有1根
    return (idx2 - idx1) >= 3  # 即中间至少1根


def has_independent_kline_new(top_or_bottom1, top_or_bottom2, raw_klines):
    """
    新笔：原始K线中，两个分型最高/最低K线之间至少3根
    不考虑包含关系
    """
    # 找到顶分型最高K线和底分型最低K线在原始K线中的位置
    raw_idx1 = get_raw_index_of_extreme(top_or_bottom1, raw_klines)
    raw_idx2 = get_raw_index_of_extreme(top_or_bottom2, raw_klines)
    
    # 之间（不包括这两根）至少3根
    return abs(raw_idx2 - raw_idx1) >= 4  # 即中间至少3根


def space_constraint_satisfied(f1, f2):
    """
    空间约束：顶分型最高K线区间 必须高于 底分型最低K线区间
    """
    if f1['type'] == 'top':
        top, bottom = f1, f2
    else:
        top, bottom = f2, f1
    
    # 顶的最高价 > 底的最低价
    return top['value'] > bottom['value']


def filter_same_type_fractals(fractals):
    """
    步骤二：处理同性质分型
    - 两个顶：前低后高，保留后者
    - 两个底：前高后低，保留后者
    """
    result = [fractals[0]]
    for f in fractals[1:]:
        prev = result[-1]
        if f['type'] == prev['type']:
            if f['type'] == 'top' and f['value'] > prev['value']:
                result[-1] = f  # 替换
            elif f['type'] == 'bottom' and f['value'] < prev['value']:
                result[-1] = f  # 替换
            # else: 保留两者（相等或其他情况）
            else:
                result.append(f)
        else:
            result.append(f)
    return result


def resolve_consecutive_same_type(pens, fractals):
    """
    步骤三：处理连续同性质
    - 连续顶后出现底 → 第一个顶与底连线
    - 连续底后出现顶 → 第一个底与顶连线
    """
    # 遍历分型序列，按第77课规则处理
    if len(fractals) < 2:
        return pens
    
    result_pens = []
    i = 0
    while i < len(fractals):
        if i + 1 >= len(fractals):
            break
        
        curr = fractals[i]
        
        # 收集连续同性质分型
        j = i + 1
        while j < len(fractals) and fractals[j]['type'] == curr['type']:
            j += 1
        
        if j >= len(fractals):
            break
        
        # curr..fractals[j-1] 同性质，fractals[j] 是不同性质
        # 连续顶 → 第一个顶与j位置的底连线
        # 连续底 → 第一个底与j位置的顶连线
        opposite = fractals[j]
        
        # 验证成笔条件
        if can_form_pen(curr, opposite):
            result_pens.append(make_pen(curr, opposite))
        
        i = j  # 跳到不同性质的分型
    
    return result_pens
```

---

## 四、特殊情况处理

### 4.1 一字涨停/跌停

一字板（开盘=收盘=最高=最低）在K线上表现为一根没有实体的线。

**处理方法**：
- 一字板本身高=低，它与其他K线的包含关系判断正常进行
- 若一字板与前一根K线完全重叠（价格相同），视为包含关系，按规则合并
- **连续一字涨停**：多根一字板会因包含关系被合并为一根，这会减少可用于构造分型的K线数量
- 在极端情况下（如上市首日连续一字涨停），该时间段内可能无法形成任何分型，自然也无法形成笔

**算法处理**：
```python
def handle_limit_bar(kline):
    """
    一字板：high == low
    正常纳入包含处理流程，不特殊排除
    """
    pass  # 包含处理自然覆盖此场景
```

### 4.2 缺口（Gap）

缠师定义缺口为：**前一根K线的收盘价与后一根K线的开盘价之间的距离**（比传统定义略宽）。

- 缺口K线正常参与包含处理和分型判定
- 新笔定义下，若顶底之间只有缺口没有实体K线：缠师在回复中明确表示**缺口不算K线**，因此纯缺口不满足独立K线要求
- 新笔要求3根原始K线，缺口不计数

### 4.3 顶底分型在同一价位

原文第77课明确：

> 顶分型中最高那K线的区间至少要有一部分高于底分型中最低那K线的区间

若顶的最高价 ≤ 底的最低价，则不能成笔。这在算法中由 `space_constraint_satisfied()` 函数保障。

---

## 五、笔的延伸与结束

### 5.1 延伸规则

- 笔产生后，若未产生新的反方向笔，则原笔继续延伸
- 笔的延伸可能创出新高/新低，分型的顶/底位置随之更新
- 同一方向的连续分型（如上升中不断创新高的顶分型），取最高点作为笔的终点

### 5.2 结束判定

**唯一条件**：新笔产生时，原笔结束。

```
向上笔结束 ⇔ 产生新的向下笔（新的有效顶分型出现，且与后续底分型构成向下笔）
向下笔结束 ⇔ 产生新的向上笔（新的有效底分型出现，且与后续顶分型构成向上笔）
```

### 5.3 当下状态分类

任何当下走势在笔的维度下只有四种状态：

| 状态编码 | 含义 | 操作建议 |
|---------|------|---------|
| (1, 1) | 向上笔延伸中 | 持股 |
| (1, 0) | 向上笔出现顶分型构造 | 考虑卖出 |
| (-1, 1) | 向下笔延伸中 | 持币 |
| (-1, 0) | 向下笔出现底分型构造 | 考虑买入 |

状态转换规则：
- (1,1) → 只能到 (1,0)
- (-1,1) → 只能到 (-1,0)
- (1,0) → (1,1) 中继分型，或 (-1,1) 新笔产生
- (-1,0) → (-1,1) 中继分型，或 (1,1) 新笔产生

---

## 六、完整算法流程总结

```
输入: 原始K线序列 [(high, low), ...]
输出: 笔序列 [(起点index, 终点index, 方向), ...]

Step 1: 包含处理
    按方向合并包含K线 → 得到无包含的K线序列

Step 2: 识别分型
    三根一组扫描 → 标记顶分型和底分型

Step 3: 过滤同性质分型
    同顶：低→高，保留高
    同底：高→低，保留低

Step 4: 构造成笔
    对相邻异性质分型，检查：
    (a) 不共用K线（结合律）
    (b) 独立K线条件（旧笔≥1处理后 / 新笔≥3原始）
    (c) 空间约束（顶>底）

Step 5: 处理连续同性质
    连续顶 → 首顶+新底 成笔
    连续底 → 首底+新顶 成笔

Step 6: 笔的延伸与确认
    最新笔可能仍在延伸中
    当新笔产生时确认原笔结束
```

---

## 七、参考文献

1. **第62课**《分型、笔与线段》(2007-06-30) — 分型定义、包含处理、笔基本概念
2. **第65课**《再说说分型、笔、线段》(2007-07-16) — 包含关系细则、方向判定、笔的唯一性
3. **第77课**《一些概念的再分辨》(2007-09-05) — 笔划分三步骤、空间约束、唯一性证明
4. **第81课回复** (2007-09-24) — 新笔定义：独立K线不考虑包含、至少3根原始K线

---

## 附录：关键判定要点速查

| 要点 | 规则 |
|------|------|
| 包含处理方向 | 向上取高高，向下取低低 |
| 顶分型 | 中间K线高点、低点均为三者最高 |
| 底分型 | 中间K线高点、低点均为三者最低 |
| 分型不共用K线 | 必须满足（结合律） |
| 旧笔独立K线 | 包含处理后 ≥1根 |
| 新笔独立K线 | 原始K线 ≥3根（不考虑包含） |
| 空间约束 | 顶最高 > 底最低 |
| 同性质过滤 | 顶保高、底保低 |
| 笔结束条件 | 反方向新笔产生 |
