# 缠论K线包含处理算法研究报告

> 调研目标：K线包含关系的精确算法  
> 信息源：缠中说禅新浪博客原文、权威缠论教程  
> 排除：知乎、微信公众号、百度百科

---

## 一、K线包含关系的定义

### 1.1 基本定义

**包含关系**：相邻的两根K线，其中一根K线的高低点（全）被另一根K线的高低点范围所覆盖。

设第 $n$ 根K线为 $K_n$，其高点为 $g_n$，低点为 $d_n$。  
则 $K_n$ 与 $K_{n+1}$ 存在包含关系，当且仅当：

$$
(g_n \geq g_{n+1} \land d_n \leq d_{n+1}) \quad \text{或} \quad (g_n \leq g_{n+1} \land d_n \geq d_{n+1})
$$

换言之：两根K线中，一方的高点比另一方高，且低点比另一方低。

### 1.2 关键要点

- **只看高低点**：判断包含关系时，不区分阳线阴线，只看最高价和最低价
- **必须是相邻**：包含关系只存在于紧邻的两根K线之间，不能隔空判断

---

## 二、方向判定规则

### 2.1 方向的数学定义

根据缠中说禅《教你炒股票65：再说说分型、笔、线段》原文：

> 假设，第n根K线满足"第n根与第n+1根有包含关系，而第n根与第n-1根不是包含关系"，则：
> - 当 $g_n \geq g_{n-1}$ 时，称"第n-1、n、n+1根K线是向上的"
> - 当 $d_n \leq d_{n-1}$ 时，称"第n-1、n、n+1根K线是向下的"

**注**：部分学者（如刘宏宇）认为等于号应去掉，因为 $g_n = g_{n-1}$ 或 $d_n = d_{n-1}$ 时必然构成包含关系，违反"第n根与第n-1根不是包含关系"的前提。

### 2.2 判定流程

1. 找到第一对存在包含关系的相邻K线（设其为 $K_n$ 与 $K_{n+1}$）
2. 检查 $K_{n-1}$ 与 $K_n$ 是否存在包含关系
3. 若不存在包含关系，则用 $K_{n-1}$ 与 $K_n$ 的相对位置判定方向：
   - 若 $g_n > g_{n-1}$ → **向上**
   - 若 $d_n < d_{n-1}$ → **向下**
4. 该方向将用于后续所有包含关系的处理

---

## 三、包含处理规则

### 3.1 向上处理（高高原则）

当方向为**向上**时：
- 新K线的高点 = $\max(g_n, g_{n+1})$ （取高的）
- 新K线的低点 = $\max(d_n, d_{n+1})$ （取高的）

### 3.2 向下处理（低低原则）

当方向为**向下**时：
- 新K线的低点 = $\min(d_n, d_{n+1})$ （取低的）
- 新K线的高点 = $\min(g_n, g_{n+1})$ （取低的）

---

## 四、处理顺序原则

### 4.1 顺序原则（从左到右）

缠论K线包含处理**不符合传递律**，但**符合结合律**。

处理顺序必须遵循：
1. 从第一根**不存在包含关系**的K线开始
2. 依次向右处理每对包含关系
3. 每处理一次，产生的新K线继续与后续K线比较
4. 若仍有包含关系，则继续合并

### 4.2 结合律的应用

> 向上时，顺次n个包含关系的K线组，等价于 $[ \max(d_i), \max(g_i) ]$ 的区间对应的K线  
> 向下时，顺次n个包含关系的K线组，等价于 $[ \min(d_i), \min(g_i) ]$ 的区间对应的K线

这意味着多条顺次包含的K线，可以一次性合并：
- 向上：取所有高点中的**最大值**，低点中的**最大值**
- 向下：取所有低点中的**最小值**，高点中的**最小值**

---

## 五、合并后的四值确定

### 5.1 开高低收的确定

合并后新K线的四值：

| 要素 | 确定方法 |
|------|----------|
| **开盘价** | 保留被包含的第一根K线的开盘价 |
| **收盘价** | 保留被包含的最后一根K线的收盘价 |
| **最高价** | 根据方向：向上取max，向下取min |
| **最低价** | 根据方向：向上取max，向下取min |

**注**：部分实现采用简化方式，直接使用合并后的最高/最低作为收盘价。

### 5.2 时间戳的处理

**推荐保留原始时间戳**：使用被包含的第一根K线的时间戳。

理由：
- 符合"从左到右"的处理顺序原则
- 保留最早的时间信息
- 便于后续笔、线段的生成判断

---

## 六、边界情况处理

### 6.1 多根连续包含

```
处理前: [K1, K2, K3, K4, K5] (K2包含K3, K3包含K4, K4包含K5)
处理后: 根据方向一次性合并
- 向上: [K1, K']  其中 K' = [max(d2..d5), max(g2..g5)]
- 向下: [K1, K''] 其中 K'' = [min(d2..d5), min(g2..g5)]
```

### 6.2 十字星处理

十字星（开盘价≈收盘价）的处理与普通K线完全相同：
- 仍按包含关系定义判断
- 方向判定不受影响

### 6.3 跳空缺口的处理

跳空缺口本身不影响包含关系判断：
- 若缺口后的K线与缺口前K线存在包含，仍按规则处理
- 缺口不改变方向判定（方向由包含关系左侧的非包含K线决定）

### 6.4 精度问题

根据缠中说禅原文：
> "预设精度一旦确定，就一定要一路保持"
> "关键是要统一，不要变来变去"

建议：
- 采用小数点后两位精度
- 或采用整数（四舍五入）
- 全程保持一致

---

## 七、完整伪代码

```python
"""
K线包含处理算法 - 缠论基础
Chanlun K-line Inclusion Processing Algorithm
"""

# 数据结构定义
class KLine:
    timestamp: datetime      # 时间戳
    open: float            # 开盘价
    high: float            # 最高价
    low: float             # 最低价
    close: float           # 收盘价

def is_contain(k1: KLine, k2: KLine) -> bool:
    """
    判断两根K线是否存在包含关系
    """
    return (k1.high >= k2.high and k1.low <= k2.low) or \
           (k1.high <= k2.high and k1.low >= k2.low)

def determine_direction(k_prev: KLine, k_curr: KLine) -> int:
    """
    判定包含关系的方向
    返回: 1 = 向上, -1 = 向下
    """
    if k_curr.high > k_prev.high:
        return 1   # 向上
    elif k_curr.low < k_prev.low:
        return -1  # 向下
    else:
        # 这种情况说明两K线有包含关系，理论上不应到达这里
        raise ValueError("Direction cannot be determined")

def merge_klines(k1: KLine, k2: KLine, direction: int) -> KLine:
    """
    合并两根K线
    direction: 1 = 向上, -1 = 向下
    """
    if direction == 1:  # 向上处理 - 高高原则
        new_high = max(k1.high, k2.high)
        new_low = max(k1.low, k2.low)
    else:               # 向下处理 - 低低原则
        new_high = min(k1.high, k2.high)
        new_low = min(k1.low, k2.low)
    
    # 保留第一根K线的时间戳和开盘价，最后一根的收盘价
    return KLine(
        timestamp=k1.timestamp,
        open=k1.open,
        high=new_high,
        low=new_low,
        close=k2.close
    )

def process_inclusion(klines: list[KLine]) -> list[KLine]:
    """
    处理K线序列中的所有包含关系
    输入: 原始K线列表
    输出: 处理后的K线列表
    """
    if len(klines) <= 1:
        return klines.copy()
    
    result = []
    result.append(klines[0])
    
    i = 1
    while i < len(klines):
        curr = klines[i]
        prev = result[-1]
        
        if is_contain(prev, curr):
            # 前面已有非包含K线，判断方向
            # 需要找到最近的非包含K线来判定方向
            direction = find_direction(result[:-1], prev)
            
            # 合并
            merged = merge_klines(prev, curr, direction)
            result[-1] = merged
        else:
            result.append(curr)
        
        i += 1
    
    return result

def find_direction(processed: list[KLine], current: KLine) -> int:
    """
    在已处理的K线序列中，找到最近的非包含K线来判定方向
    """
    if len(processed) == 0:
        # 没有前驱K线，默认向上（或根据实际需求设定）
        return 1
    
    # 向前查找第一个非包含的K线
    idx = len(processed) - 1
    while idx >= 0:
        if not is_contain(processed[idx], current):
            break
        idx -= 1
    
    if idx < 0:
        # 所有前面的K线都被包含，使用第一个K线
        return determine_direction(processed[0], current)
    else:
        return determine_direction(processed[idx], current)

def process_inclusion_optimized(klines: list[KLine]) -> list[KLine]:
    """
    优化的K线包含处理算法（结合律版本）
    一次性处理多条连续包含的K线
    """
    if len(klines) <= 1:
        return klines.copy()
    
    result = []
    i = 0
    
    while i < len(klines):
        # 找到第一根非包含的K线（或第一根K线）
        if len(result) == 0:
            result.append(klines[i])
            i += 1
            continue
        
        # 检查当前K线与结果中最后一根是否有包含关系
        last = result[-1]
        
        if is_contain(last, klines[i]):
            # 确定方向
            direction = find_direction_for_merge(result[:-1], last)
            
            # 收集所有连续包含的K线
            merge_group = [last]
            j = i
            while j < len(klines) and is_contain(merge_group[-1], klines[j]):
                merge_group.append(klines[j])
                j += 1
            
            # 一次性合并（利用结合律）
            merged = merge_group_klines(merge_group, direction)
            result[-1] = merged
            
            i = j
        else:
            result.append(klines[i])
            i += 1
    
    return result

def merge_group_klines(kline_group: list[KLine], direction: int) -> KLine:
    """
    合并一组连续包含的K线（利用结合律）
    """
    if len(kline_group) == 1:
        return kline_group[0]
    
    if direction == 1:  # 向上 - 取max
        new_high = max(k.high for k in kline_group)
        new_low = max(k.low for k in kline_group)
    else:              # 向下 - 取min
        new_high = min(k.high for k in kline_group)
        new_low = min(k.low for k in kline_group)
    
    return KLine(
        timestamp=kline_group[0].timestamp,   # 保留第一根的时间戳
        open=kline_group[0].open,             # 保留第一根的开盘价
        high=new_high,
        low=new_low,
        close=kline_group[-1].close          # 保留最后一根的收盘价
    )

def find_direction_for_merge(processed: list[KLine], current: KLine) -> int:
    """
    为合并操作确定方向
    """
    if len(processed) == 0:
        return 1  # 默认向上
    
    # 找到最近的不包含K线
    for idx in range(len(processed) - 1, -1, -1):
        if not is_contain(processed[idx], current):
            return determine_direction(processed[idx], current)
    
    # 所有前面的都包含，使用第一个
    return determine_direction(processed[0], current)
```

---

## 八、算法复杂度分析

| 算法版本 | 时间复杂度 | 空间复杂度 |
|----------|------------|------------|
| 基础版 | O(n) | O(n) |
| 优化版（结合律） | O(n) | O(n) |

两种版本实际性能相近，优化版在处理长串连续包含时代码更清晰。

---

## 九、参考文献

### 原文来源
1. 缠中说禅《教你炒股票65：再说说分型、笔、线段》- 新浪博客
2. 缠中说禅《教你炒股票62：分型、笔与线段》- 新浪博客

### 权威教程
3. 刘宏宇《感悟缠论（17）——K线的包含关系及处理》- 新浪博客
4. 观海岛主《缠论技术第一章：K线的包含关系处理》- 新浪博客

### 代码实现参考
5. CSDN: Python实现缠论：处理K线包含关系
6. 博客园: 龙哥量化：缠中说禅(缠论)K线包含处理

---

## 十、总结

K线包含处理是缠论的底层基础，其核心要点：

1. **定义**：相邻K线的高低点相互包含
2. **方向**：由包含关系左侧的非包含K线决定，"向上取高高，向下取低低"
3. **顺序**：从左到右逐根处理，利用结合律可一次性合并多条连续包含
4. **四值**：开盘价取第一根，收盘价取最后一根，高低价按方向取值
5. **时间戳**：保留第一根K线的时间戳

该算法是后续顶底分型、笔、线段识别的基础，必须严格按定义实现，保证精度的一致性。

---

*调研完成日期: 2026-04-18*  
*信息源: 缠中说禅新浪博客、权威缠论教程（排除知乎/微信公众号/百度百科）*