# 缠论三类买卖点精确定义与判定算法

> 信息源：缠中说禅新浪博客原文（第17、20、21课及回复），辅助以缠论定理体系
> 核心原文索引：第17课《走势终完美》、第20课《走势中枢级别扩张及第三类买卖点》、第21课《买卖点分析的完备性》

---

## 一、三类买卖点的原文定义

### 1.1 第一类买点（Buy1）

> 第17课原文：一旦能把握下跌走势转化的关节点买入，就在市场中占据了一个最有利的位置，而这个买点，就是前面反复强调的"第一类买点"。
>
> 第21课原文：只有在下跌确立后的中枢下方才可能出现买点。这就是第一类买点。

**精确定义**：某级别下跌趋势中，最后一个中枢之后的次级别走势（c段）发生趋势背驰，该背驰段结束的最低点即第一类买点。

**数学表达**：
- 走势结构：`a + A + b + B + c`（下跌趋势，A、B同级别中枢）
- c段创新低且发生趋势背驰
- 第一类买点 = c段结束点

### 1.2 第二类买点（Buy2）

> 第17课原文：在第一类买点出现后第一次次级别回调制造的低点，是市场中第二有利的位置。
>
> 第21课原文：第一买点出现后的第二段次级别走势低点就构成第二类买点。

**精确定义**：第一类买点出现后，必然出现盘整或上涨走势。该走势的第一段次级别向上结束后，第二段次级别向下回调的低点，构成第二类买点。

**关键性质**：
- 第二类买点不必然出现在中枢上或下，可在任何位置
- 中枢下出现→力度弱，中枢扩张可能大
- 中枢中出现→扩张与新生对半
- 中枢上出现→中枢新生可能大（最强，此时可与第三类买点重合）

**买卖点定律一**（第17课）：任何级别的第二类买卖点都由次级别相应走势的第一类买卖点构成。

### 1.3 第三类买点（Buy3）

> 第20课原文定理：一个次级别走势类型向上离开缠中说禅走势中枢，然后以一个次级别走势类型回试，其低点不跌破ZG（中枢破坏），则构成第三类买点。

**精确定义**：某级别中枢中，一个次级别走势向上离开该中枢后，以一个次级别走势回抽，其低点不低于中枢上沿ZG，该回抽低点即第三类买点。

**中枢破坏判定**（第20课定理）：走势中枢的破坏，当且仅当一个次级别走势离开该中枢后，其后的次级别回抽走势不重新回到该中枢区间内。

### 1.4 三类卖点的镜像定义

| 类型 | 卖点定义 | 买点的镜像 |
|------|---------|-----------|
| **Sell1** | 上涨趋势中最后一个中枢后，c段创新高且趋势背驰，该高点 | Buy1镜像 |
| **Sell2** | Sell1后第一段次级别向下结束，第二段次级别向上不创新高或盘整背驰 | Buy2镜像 |
| **Sell3** | 次级别走势向下离开中枢后，次级别回抽高点不升破ZD | Buy3镜像 |

### 1.5 买卖点完备性定理

> 第21课原文：市场必然产生赢利的买卖点，只有第一、二、三类。

**升跌完备性定理**：市场中的任何向上与下跌，都必然从三类缠中说禅买卖点中的某一类开始以及结束。

---

## 二、买卖点位置与中枢关系总结

```
价格轴
  ↑
  │     ┌───┐
  │     │ZG │ ← 第三类买点区间（回抽低点≥ZG）
  │     │   │
  │     │中枢│ ← 第二类买点可出现在中枢上/中/下任意位置
  │     │   │
  │     │ZD │ ← 第三类卖点区间（回抽高点≤ZD）
  │     └───┘
  │
  │  ─── ★ 第一类买点（背驰最低点，中枢之下）
  │
```

---

## 三、判定算法伪代码

### 3.1 数据结构定义

```python
@dataclass
class Pivot:
    """中枢"""
    level: str          # 级别 (1F/5F/30F/D/W/M)
    ZG: float           # 中枢上沿 = min(g1, g2)
    ZD: float           # 中枢下沿 = max(d1, d2)
    GG: float           # 中枢最高点 = max(gn)
    DD: float           # 中枢最低点 = min(dn)
    start_idx: int      # 起始位置
    end_idx: int        # 结束位置
    direction: str      # 'up' | 'down'

@dataclass  
class MoveType:
    """次级别走势段"""
    start_idx: int
    end_idx: int
    direction: str      # 'up' | 'down'
    high: float
    low: float
    level: str

@dataclass
class BuySellPoint:
    """买卖点"""
    type: int           # 1, 2, 3
    side: str           # 'buy' | 'sell'
    level: str          # 操作级别
    price: float        # 价格
    idx: int            # 位置索引
    pivot_ref: Pivot    # 关联中枢
    confidence: float   # 置信度
```

### 3.2 第一类买点判定算法

```python
def detect_buy1(klines, level, segments, pivots):
    """
    第一类买点判定
    
    前提条件：
    1. 当前处于某级别下跌趋势中（至少两个同级别中枢）
    2. 最后一个中枢之后存在背驰
    
    判定步骤：
    Step1: 确认下跌趋势
    Step2: 定位最后两个同级别中枢 A, B
    Step3: 验证 c段（B中枢之后的走势）是否存在趋势背驰
    Step4: 定位 c段结束点即为 Buy1
    """
    results = []
    
    # Step 1: 寻找下跌趋势中的中枢序列
    downtrend_pivots = find_downtrend_pivots(pivots, level)
    
    if len(downtrend_pivots) < 2:
        return results  # 不构成下跌趋势，无Buy1
    
    B = downtrend_pivots[-1]   # 最后一个中枢
    A = downtrend_pivots[-2]   # 倒数第二个中枢
    
    # Step 2: 确认 A, B 同级别且依次向下
    if A.level != B.level:
        return results
    if A.ZG >= B.ZG:  # 不是依次向下的
        return results
    
    # Step 3: 获取 c段（B中枢之后的次级别走势）
    c_segment = get_segment_after_pivot(segments, B, level)
    if c_segment is None:
        return results
    
    # Step 4: 验证 c段创新低
    if c_segment.low >= B.DD:
        return results  # 未创新低，不构成背驰前提
    
    # Step 5: 趋势背驰判定（调用05-divergence.md的算法）
    is_div, div_confidence = check_trend_divergence(
        klines, A, B, c_segment, direction='down'
    )
    
    if is_div:
        # Step 6: 精确定位背驰段结束点
        buy1_idx = find_divergence_endpoint(c_segment, direction='down')
        
        results.append(BuySellPoint(
            type=1,
            side='buy',
            level=level,
            price=klines[buy1_idx].low,
            idx=buy1_idx,
            pivot_ref=B,
            confidence=div_confidence
        ))
    
    return results


def check_trend_divergence(klines, pivot_A, pivot_B, seg_c, direction):
    """
    趋势背驰判定核心
    
    MACD辅助判断：
    1. B中枢期间黄白线回拉0轴附近
    2. c段MACD面积 < a段MACD面积
    3. c段创出新高/新低
    """
    # a段：A中枢之前的连接段
    seg_a = get_connection_before_pivot(klines, pivot_A, direction)
    
    # 获取各段的MACD柱子面积
    macd_a = calc_macd_area(klines, seg_a, direction)
    macd_c = calc_macd_area(klines, seg_c, direction)
    
    # B中枢期间MACD回拉0轴检测
    macd_B = get_macd_during_pivot(klines, pivot_B)
    near_zero = is_macd_near_zero_axis(macd_B)
    
    # 面积比较
    if direction == 'down':
        area_a = macd_a['green_area']   # 绿柱面积
        area_c = macd_c['green_area']
        new_extreme = seg_c.low < pivot_B.DD  # 创新低
    else:
        area_a = macd_a['red_area']     # 红柱面积
        area_c = macd_c['red_area']
        new_extreme = seg_c.high > pivot_B.GG  # 创新高
    
    # 综合判定
    is_div = (near_zero and 
              area_c < area_a * 0.9 and  # c段力度明显弱于a段
              new_extreme)
    
    confidence = 1.0 if is_div else 0.0
    if is_div:
        ratio = area_c / area_a if area_a > 0 else 0
        if ratio < 0.5:
            confidence = 0.95
        elif ratio < 0.7:
            confidence = 0.85
        elif ratio < 0.9:
            confidence = 0.7
    
    return is_div, confidence
```

### 3.3 第二类买点判定算法

```python
def detect_buy2(klines, level, segments, pivots, buy1_points):
    """
    第二类买点判定
    
    前提条件：
    1. 已确认第一类买点 Buy1
    2. Buy1 之后的走势分解：第一段次级别向上 + 第二段次级别向下
    
    判定步骤：
    Step1: 从Buy1出发，确定次级别走势分解
    Step2: 找到第一段次级别向上走势（段1）
    Step3: 找到第二段次级别向下走势（段2）的结束低点
    Step4: 该低点 = Buy2
    Step5: 验证该低点不破Buy1（否则结构破坏）
    """
    results = []
    
    for buy1 in buy1_points:
        if buy1.side != 'buy' or buy1.type != 1:
            continue
        
        sub_level = get_sub_level(level)  # 次级别
        
        # Step 1: 从Buy1位置开始的次级别走势分解
        sub_moves = get_sub_level_moves_after(
            segments, buy1.idx, sub_level
        )
        
        if len(sub_moves) < 2:
            continue
        
        # Step 2: 第一段次级别走势（必须向上）
        move1 = sub_moves[0]
        if move1.direction != 'up':
            continue
        
        # Step 3: 第二段次级别走势（必须向下）
        move2 = sub_moves[1]
        if move2.direction != 'down':
            continue
        
        # Step 4: Buy2 = move2的最低点
        buy2_idx = move2.end_idx
        buy2_price = move2.low
        
        # Step 5: 验证不破Buy1低点
        if buy2_price <= buy1.price:
            continue  # 跌破Buy1，结构可能破坏
        
        # Step 6: 计算Buy2与关联中枢的位置关系
        last_pivot = buy1.pivot_ref  # 下跌趋势最后一个中枢
        position = classify_position(buy2_price, last_pivot)
        # position: 'above_pivot' | 'in_pivot' | 'below_pivot'
        
        confidence = {
            'above_pivot': 0.9,   # 最强
            'in_pivot': 0.75,
            'below_pivot': 0.6    # 较弱
        }[position]
        
        results.append(BuySellPoint(
            type=2,
            side='buy',
            level=level,
            price=buy2_price,
            idx=buy2_idx,
            pivot_ref=last_pivot,
            confidence=confidence
        ))
    
    return results
```

### 3.4 第三类买点判定算法

```python
def detect_buy3(klines, level, segments, pivots):
    """
    第三类买点判定（基于第20课定理）
    
    定义：次级别走势向上离开中枢后，次级别回抽低点不跌破ZG
    
    判定步骤：
    Step1: 遍历所有本级别中枢
    Step2: 对每个中枢，寻找次级别走势向上离开（段L）
    Step3: 寻找离开后的次级别回抽走势（段R）
    Step4: 验证 R.low >= 中枢.ZG
    Step5: R的最低点 = Buy3
    """
    results = []
    sub_level = get_sub_level(level)
    
    for pivot in pivots:
        if pivot.level != level:
            continue
        
        # Step 2: 找到离开中枢的次级别走势
        leaving_moves = find_leaving_moves(segments, pivot, sub_level, 'up')
        
        for leave_move in leaving_moves:
            # 验证：离开走势的低点在中枢之上或中枢区间内
            # (即确实是"离开"而非中枢延伸)
            if leave_move.low < pivot.ZD:
                continue  # 穿越中枢，可能不是有效离开
            
            # Step 3: 找到回抽走势
            pullback = find_pullback_after(segments, leave_move, sub_level, 'down')
            
            if pullback is None:
                continue
            
            # Step 4: 核心判定——回抽低点不跌破ZG
            if pullback.low >= pivot.ZG:
                # Step 5: 确认中枢被破坏（不再回入中枢区间）
                # 中枢破坏 = 回抽走势不触及中枢区间[ZD, ZG]
                # 注意：第20课要求"不跌破ZG"即为第三类买点
                buy3_idx = pullback.end_idx
                
                results.append(BuySellPoint(
                    type=3,
                    side='buy',
                    level=level,
                    price=pullback.low,
                    idx=buy3_idx,
                    pivot_ref=pivot,
                    confidence=0.85
                ))
    
    return results
```

### 3.5 三类卖点判定算法（镜像）

```python
def detect_sell1(klines, level, segments, pivots):
    """第一类卖点 = 上涨趋势中最后一个中枢后c段趋势背驰"""
    # 完全镜像 Buy1
    uptrend_pivots = find_uptrend_pivots(pivots, level)
    if len(uptrend_pivots) < 2:
        return []
    B = uptrend_pivots[-1]
    A = uptrend_pivots[-2]
    if A.level != B.level or A.ZD <= B.ZD:
        return []
    c_segment = get_segment_after_pivot(segments, B, level)
    if c_segment is None or c_segment.high <= B.GG:
        return []
    is_div, conf = check_trend_divergence(
        klines, A, B, c_segment, direction='up'
    )
    if is_div:
        sell1_idx = find_divergence_endpoint(c_segment, direction='up')
        return [BuySellPoint(1, 'sell', level, klines[sell1_idx].high,
                             sell1_idx, B, conf)]
    return []


def detect_sell2(klines, level, segments, pivots, sell1_points):
    """第二类卖点 = Sell1后第一段向下结束，第二段向上不创新高或盘整背驰"""
    results = []
    for sell1 in sell1_points:
        sub_level = get_sub_level(level)
        sub_moves = get_sub_level_moves_after(segments, sell1.idx, sub_level)
        if len(sub_moves) < 2:
            continue
        move1 = sub_moves[0]
        move2 = sub_moves[1]
        if move1.direction != 'down' or move2.direction != 'up':
            continue
        sell2_price = move2.high
        sell2_idx = move2.end_idx
        # 验证不破Sell1高点
        if sell2_price >= sell1.price:
            continue
        position = classify_position(sell2_price, sell1.pivot_ref)
        confidence = {'below_pivot': 0.9, 'in_pivot': 0.75, 'above_pivot': 0.6}[position]
        results.append(BuySellPoint(2, 'sell', level, sell2_price,
                                    sell2_idx, sell1.pivot_ref, confidence))
    return results


def detect_sell3(klines, level, segments, pivots):
    """第三类卖点 = 次级别向下离开中枢后，次级别回抽高点不升破ZD"""
    results = []
    sub_level = get_sub_level(level)
    for pivot in pivots:
        if pivot.level != level:
            continue
        leaving_moves = find_leaving_moves(segments, pivot, sub_level, 'down')
        for leave_move in leaving_moves:
            if leave_move.high > pivot.ZG:
                continue
            pullback = find_pullback_after(segments, leave_move, sub_level, 'up')
            if pullback is None:
                continue
            if pullback.high <= pivot.ZD:
                results.append(BuySellPoint(
                    3, 'sell', level, pullback.high,
                    pullback.end_idx, pivot, 0.85))
    return results
```

---

## 四、统一检测入口

```python
def detect_all_buy_sell_points(klines, level):
    """
    某级别全量买卖点检测
    
    检测顺序：Buy1 → Sell2 → Buy2 → Buy3 → Sell1 → Sell2 → Sell3
    （存在依赖关系）
    """
    # 前置处理：笔、线段、中枢识别
    strokes = identify_strokes(klines)
    segments = identify_segments(strokes)
    pivots = identify_pivots(segments, level)
    
    # 买点检测
    buy1_list = detect_buy1(klines, level, segments, pivots)
    buy2_list = detect_buy2(klines, level, segments, pivots, buy1_list)
    buy3_list = detect_buy3(klines, level, segments, pivots)
    
    # 卖点检测
    sell1_list = detect_sell1(klines, level, segments, pivots)
    sell2_list = detect_sell2(klines, level, segments, pivots, sell1_list)
    sell3_list = detect_sell3(klines, level, segments, pivots)
    
    # 合并排序
    all_points = buy1_list + buy2_list + buy3_list + \
                 sell1_list + sell2_list + sell3_list
    all_points.sort(key=lambda p: p.idx)
    
    return all_points
```

---

## 五、级别对应关系

### 5.1 买卖点级别定理

> 第17课定理：大级别的买卖点必然是次级别以下某一级别的买卖点。

| 操作级别 | Buy1 对应 | Buy2 对应 | Buy3 对应 |
|---------|----------|----------|----------|
| 30F | 5F趋势背驰点 | 5F走势的Buy1 | 5F回抽不破30F中枢ZG |
| 日线 | 30F趋势背驰点 | 30F走势的Buy1 | 30F回抽不破日线中枢ZG |
| 周线 | 日线趋势背驰点 | 日线走势的Buy1 | 日线回抽不破周线中枢ZG |

### 5.2 区间套精确定位

```python
def precise_locate_buy1(klines, target_level='30F'):
    """
    区间套定位：从大级别到小级别逐级收缩
    
    第14课定理：某大级别的转折点，可以通过不同级别
    背驰段的逐级收缩范围而确定。
    """
    level_chain = get_level_chain(target_level)
    # e.g., ['W', 'D', '30F', '5F', '1F']
    
    candidate_range = None
    
    for lvl in level_chain:
        pivots = identify_pivots(klines, lvl)
        buy1_list = detect_buy1(klines, lvl, segments, pivots)
        
        if buy1_list:
            pt = buy1_list[0]
            if candidate_range is None:
                candidate_range = (pt.idx, pt.price)
            else:
                # 收缩范围
                candidate_range = (
                    max(candidate_range[0], pt.idx - tolerance),
                    pt.price
                )
    
    return candidate_range
```

### 5.3 小转大定理

> 第22课回复中小背驰-大转折定理：
> 小级别顶背驰引发大级别向下的**必要条件**是：该级别走势的最后一个次级别中枢出现第三类卖点。
> 小级别底背驰引发大级别向上的**必要条件**是：该级别走势的最后一个次级别中枢出现第三类买点。

```python
def check_small_to_large(klines, small_level, large_level):
    """
    小转大判定
    
    小级别背驰引发大级别转折的必要条件：
    最后一个次级别中枢出现第三类买卖点
    """
    # 在小级别中找背驰
    small_buy1 = detect_buy1(klines, small_level, ...)
    
    if small_buy1:
        # 检查大级别最后一个次级别中枢是否出现第三类买点
        large_pivots = identify_pivots(klines, large_level)
        last_sub_pivot = get_last_sub_pivot(large_pivots)
        buy3_near = detect_buy3_near(klines, small_level, last_sub_pivot)
        
        if buy3_near:
            return True  # 小转大概率较大
    
    return False
```

---

## 六、常见误判与假买卖点识别

### 6.1 假第一类买点

| 误判类型 | 特征 | 识别方法 |
|---------|------|---------|
| **盘整背驰误判为趋势背驰** | 只有一个中枢，非趋势 | 验证至少两个同级别中枢 |
| **c段未创新低** | c段低点≥B.DD | 严格要求 c.low < B.DD |
| **MACD黄白线未回拉0轴** | B中枢形成时DIF/DEA远离0轴 | 检查B中枢期间MACD位置 |
| **中枢级别不等** | A、B非同级别 | 验证 A.level == B.level |

```python
def validate_buy1(klines, pivot_A, pivot_B, seg_c):
    """假Buy1过滤器"""
    errors = []
    
    # 检查1：趋势前提
    if pivot_A.level != pivot_B.level:
        errors.append("中枢级别不等，非趋势背驰")
    
    # 检查2：创新低
    if seg_c.low >= pivot_B.DD:
        errors.append("c段未创新低")
    
    # 检查3：MACD回拉0轴
    macd_B = get_macd_during_pivot(klines, pivot_B)
    if abs(macd_B.dif_mean) > ZERO_AXIS_THRESHOLD:
        errors.append("黄白线未回拉0轴附近")
    
    # 检查4：面积比较
    area_a = calc_macd_area(klines, seg_a, 'down')
    area_c = calc_macd_area(klines, seg_c, 'down')
    if area_c >= area_a:
        errors.append("MACD面积未缩小，无背驰")
    
    return len(errors) == 0, errors
```

### 6.2 假第二类买点

| 误判类型 | 特征 | 识别方法 |
|---------|------|---------|
| **跌破Buy1** | Buy2价格 ≤ Buy1价格 | 严格要求 Buy2.price > Buy1.price |
| **次级别结构不完整** | 向上段或向下段未完成 | 确认次级别走势类型已完成 |
| **与Buy1重合** | 理论上不可能，实盘需检查 | Buy1和Buy2在时间上有先后 |

### 6.3 假第三类买点

| 误判类型 | 特征 | 识别方法 |
|---------|------|---------|
| **回抽触及中枢区间** | 回抽低点 < ZG | 严格验证 pullback.low ≥ ZG |
| **中枢延伸误判为离开** | 离开段未真正脱离中枢 | 验证离开段起点与中枢的关系 |
| **次级别走势不完整** | 回抽未完成即判定 | 确认次级别走势类型完成 |
| **中枢扩张而非新生** | 回抽进入更大级别中枢形成 | 区分中枢新生与扩张 |

```python
def validate_buy3(pivot, leave_move, pullback):
    """假Buy3过滤器"""
    errors = []
    
    # 检查1：离开方向正确
    if leave_move.direction != 'up':
        errors.append("离开方向非向上")
    
    # 检查2：回抽方向正确
    if pullback.direction != 'down':
        errors.append("回抽方向非向下")
    
    # 检查3：核心条件——不破ZG
    if pullback.low < pivot.ZG:
        errors.append(f"回抽低点{pullback.low}跌破ZG{pivot.ZG}")
    
    # 检查4：离开段确实离开中枢（非中枢延伸）
    if leave_move.low >= pivot.ZG:
        pass  # 从中枢上方离开，有效
    elif leave_move.low >= pivot.ZD:
        errors.append("离开段未真正脱离中枢，可能是中枢延伸")
    
    return len(errors) == 0, errors
```

### 6.4 二三买重合的特殊情况

> 第21课原文：第一类买点出现后，一个次级别的走势凌厉地直接上破前面下跌的最后一个中枢，然后在其上产生一个次级别的回抽不触及该中枢，这时候，就会出现第二类买点与第三类买点重合的情况。

```python
def detect_buy2_buy3_overlap(klines, level, buy1, last_pivot):
    """
    二三买重合检测
    
    条件：Buy1后次级别走势直接突破下跌最后一个中枢，
    回抽不触及该中枢
    """
    sub_level = get_sub_level(level)
    sub_moves = get_sub_level_moves_after(segments, buy1.idx, sub_level)
    
    if len(sub_moves) < 2:
        return None
    
    move1 = sub_moves[0]  # 向上突破
    move2 = sub_moves[1]  # 回抽
    
    # 条件1：move1 直接突破 last_pivot 的 ZG
    if move1.high <= last_pivot.ZG:
        return None
    
    # 条件2：move2 回抽低点不触及 last_pivot 的 ZG（即不回入中枢）
    if move2.low >= last_pivot.ZG:
        return BuySellPoint(
            type=23,  # 二三买重合标记
            side='buy',
            level=level,
            price=move2.low,
            idx=move2.end_idx,
            pivot_ref=last_pivot,
            confidence=0.95  # 高置信度
        )
    
    return None
```

---

## 七、完整判定流程图

```
输入：K线数据 + 操作级别 L
         │
    ┌────▼────┐
    │ 笔识别   │  K线包含处理 → 顶底分型 → 笔
    └────┬────┘
         │
    ┌────▼────┐
    │ 线段识别 │  笔 → 特征序列 → 线段
    └────┬────┘
         │
    ┌────▼────┐
    │ 中枢识别 │  线段 → L级别中枢（ZG/ZD/GG/DD）
    └────┬────┘
         │
    ┌────▼──────────────────┐
    │ 趋势判定               │
    │ ≥2个同级别中枢 = 趋势  │
    │ 1个中枢 = 盘整         │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────┐
    │ 下跌趋势？             │
    │ ├─ 是 → 检测Buy1      │
    │ │   └─ 背驰？→ Buy1    │
    │ │       └─ Buy1后检测Buy2
    │ │           └─ 次级别回调低点
    │ └─ 否                  │
    │     上涨趋势？          │
    │     ├─ 是 → 检测Sell1  │
    │     │   └─ 背驰？→ Sell1│
    │     │       └─ Sell1后检测Sell2
    │     └─ 否 → 跳过        │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────┐
    │ 逐中枢检测Buy3/Sell3   │
    │ 次级别离开+回抽        │
    │ vs ZG/ZD判定          │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────┐
    │ 假买卖点过滤           │
    │ ├─ 级别验证            │
    │ ├─ 创新高低验证        │
    │ ├─ MACD辅助验证        │
    │ └─ 中枢关系验证        │
    └────┬──────────────────┘
         │
    输出：BuySellPoint列表（类型/方向/级别/价格/位置/置信度）
```

---

## 八、关键约束与注意事项

1. **同一级别原则**（第21课后回复）：三类买卖点必须在同一级别上研究，不能混淆级别
2. **次级别显微镜切换**：检测第三类买卖点时需切换到次级别观察，但操作级别不变
3. **走势必完美**保证：所有买卖点由"走势终完美"原理严格保证安全性
4. **第一类买卖点是根基**：三类买卖点归根结底都可归到不同级别的第一类买卖点
5. **盘整中无第一类买卖点**：只有趋势确立后才存在第一类买卖点
6. **第三类买点后的两种演化**：中枢扩张（更大级别中枢）或中枢新生（上涨趋势），两者都保证赢利
