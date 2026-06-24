# 05 - 背驰（BeiChi / Divergence）精确定义与判定算法

> **信息源**: 缠中说禅新浪博客原文《教你炒股票》第24、25、27、29、61课。
> 聚焦可编程伪代码，控制算法精度到可实现程度。

---

## 1. 背驰的本质定义

**原文核心**（第24课）：背驰是力度衰竭的表现。两段同向趋势之间由一个盘整或反向趋势连接（记为A、B、C），当C段力度小于A段时，构成背驰。

**力学本质**：进入中枢的推动力度不足以维持原趋势，表现为价格创新高/低但动量指标无法同步创新高/低。

**关键公理**（第24课）：
> "缠中说禅背驰-买卖点定理：任一背驰都必然制造某级别的买卖点，任一级别的买卖点都必然源自某级别走势的背驰。"

---

## 2. 趋势背驰的判定

### 2.1 前提条件

原文（第24课）明确：

1. A、B、C段在一个**大的趋势**里
2. A之前已有一个中枢（Z₁），B是同级别的另一个中枢（Z₂）
3. B中枢一般会将MACD黄白线回拉到0轴附近
4. **趋势至少有两个同级别中枢**（第27课：第二个中枢后才可能产生背驰）

### 2.2 走势结构

```
标准上涨趋势: a + Z₁ + A + Z₂ + C
其中:
  Z₁ = 第一个同级别中枢（A之前）
  A  = 离开Z₁的次级别走势（第一段趋势段）
  Z₂ = 第二个同级别中枢（B段）
  C  = 离开Z₂的次级别走势（第二段趋势段，被比较段）
```

### 2.3 趋势背驰判定算法（伪代码）

```python
def detect_trend_divergence(trend, level):
    """
    trend: 已识别的趋势走势类型对象（含至少2个同级别中枢）
    level: 当前分析级别
    返回: DivergenceResult { is_divergent, type, segment_A, segment_C, strength }
    """
    # Step 1: 验证趋势结构
    pivots = trend.get_pivots_of_level(level)  # 获取同级别中枢列表
    if len(pivots) < 2:
        return DivergenceResult(is_divergent=False, reason="中枢数量不足2个")
    
    Z_last = pivots[-1]     # 最后一个中枢
    Z_prev = pivots[-2]     # 倒数第二个中枢
    
    # Step 2: 提取比较段
    # A段 = 进入最后一个中枢之前的同向趋势段
    # C段 = 离开最后一个中枢的同向趋势段（必须是已完成的走势类型）
    segment_A = trend.get_segment_entering_pivot(Z_last)  # Z_prev后的离开段
    segment_C = trend.get_segment_leaving_pivot(Z_last)   # Z_last后的离开段
    
    if segment_C is None or not segment_C.is_complete():
        return DivergenceResult(is_divergent=False, reason="C段未完成")
    
    # Step 3: 价格创新极值检查
    if trend.direction == UP:
        if not (segment_C.end_price > segment_A.end_price):
            return DivergenceResult(is_divergent=False, reason="C段未创新高")
    else:  # DOWN
        if not (segment_C.end_price < segment_A.end_price):
            return DivergenceResult(is_divergent=False, reason="C段未创新低")
    
    # Step 4: 力度比较（核心）
    return compare_force(segment_A, segment_C, trend.direction)
```

---

## 3. 盘整背驰的判定

### 3.1 定义

原文（第27课）：在**第一个中枢**就出现的背驰不算标准背驰，只能算盘整背驰。其本质是一个企图脱离中枢的运动力度有限，被阻止而回到中枢内。

**结构**: 只有一个中枢Z，围绕Z的两段离开走势a和c进行力度比较。

### 3.2 盘整背驰判定算法

```python
def detect_consolidation_divergence(consolidation, level):
    """
    consolidation: 盘整走势（含1个同级别中枢Z）
    level: 当前分析级别
    """
    Z = consolidation.get_single_pivot(level)
    if Z is None:
        return DivergenceResult(is_divergent=False, reason="无中枢")
    
    # 获取围绕中枢的各段次级别走势
    segments = consolidation.get_sub_segments_around_pivot(Z)
    
    # 比较相邻同向段
    results = []
    for i in range(0, len(segments) - 2, 2):
        seg_a = segments[i]       # 前一段离开
        seg_c = segments[i + 2]   # 后一段离开（同向）
        
        if seg_a is None or seg_c is None:
            continue
        
        div_result = compare_force(seg_a, seg_c, seg_a.direction)
        if div_result.is_divergent:
            # 判断是否突破中枢
            if not seg_c.breaks_pivot(Z):
                # 情况1: C段不破中枢 → 必定回跌
                div_result.outcome = "MUST_FALLBACK"
            else:
                # 情况2: C段突破中枢但力度不足 → 先出，观察回跌
                div_result.outcome = "BREAK_THEN_WATCH"
            results.append(div_result)
    
    return results
```

### 3.3 盘整背驰三种情况（原文第24、25课）

| 情况 | C段与中枢关系 | 力度比较 | 后果 |
|------|-------------|---------|------|
| ① | C段不破中枢 | C力度 < A力度 | **必定回跌**，继续盘整 |
| ② | C段突破中枢 | C力度 < A力度 | 先出；回跌不回中枢 → **第三类买点** |
| ③ | C段突破中枢 | C力度 < A力度 | 先出；回跌回中枢 → **继续盘整** |

---

## 4. MACD辅助判断背驰的精确规则

### 4.1 MACD计算基础

```python
def calc_macd(close_prices, fast=12, slow=26, signal=9):
    """
    标准MACD计算
    返回: { dif, dea, histogram }
    """
    ema_fast = EMA(close_prices, fast)
    ema_slow = EMA(close_prices, slow)
    dif = ema_fast - ema_slow
    dea = EMA(dif, signal)
    histogram = 2 * (dif - dea)  # 柱子 = 2*(DIF-DEA)
    return { dif, dea, histogram }
```

### 4.2 黄白线（DIF/DEA）位置关系

**规则**（原文第24课）：

```
B中枢（最后一个同级别中枢）形成期间:
  → DIF线被回拉到0轴附近（0轴 = 红绿柱分界线）
  → DEA线也随之靠近0轴

标准上涨背驰的MACD特征:
  1. A段上涨时: DIF和DEA在0轴上方，DIF > DEA，红柱放大
  2. B段中枢形成: DIF和DEA回拉靠近0轴
  3. C段上涨时: DIF和DEA再次上扬，但红柱面积 < A段

标准下跌背驰（反向）:
  1. A段下跌时: DIF和DEA在0轴下方
  2. B段中枢形成: DIF和DEA回拉靠近0轴
  3. C段下跌时: 绿柱面积 < A段绿柱面积
```

### 4.3 柱子面积的定量比较（核心算法）

```python
def calc_histogram_area(macd_data, start_idx, end_idx, direction):
    """
    计算指定区间内MACD柱子的累积面积
    direction: UP时取正值(红柱)，DOWN时取负值(绿柱)
    """
    total_area = 0.0
    for i in range(start_idx, end_idx + 1):
        bar = macd_data.histogram[i]
        if direction == UP:
            if bar > 0:
                total_area += bar
        else:  # DOWN
            if bar < 0:
                total_area += abs(bar)
    return total_area


def calc_histogram_area_realtime(macd_data, start_idx, current_idx, direction):
    """
    实时估算面积（原文技巧）：
    "一般柱子伸长的力度变慢时，把已经出现的面积乘2，就可以当成是该段的面积"
    """
    appeared_area = calc_histogram_area(macd_data, start_idx, current_idx, direction)
    
    # 检测柱子伸长力度是否变慢
    recent_bars = [macd_data.histogram[i] for i in range(max(start_idx, current_idx-3), current_idx+1)]
    if is_bar_growth_slowing(recent_bars, direction):
        return appeared_area * 2  # 原文：已出面积×2
    else:
        return appeared_area  # 仍在加速，暂不估算


def is_bar_growth_slowing(bars, direction):
    """
    判断柱子伸长是否变慢（一阶导数递减）
    """
    if len(bars) < 2:
        return False
    diffs = [bars[i+1] - bars[i] for i in range(len(bars)-1)]
    if direction == UP:
        return all(d < diffs[0] for d in diffs[1:])  # 增量递减
    else:
        return all(d > diffs[0] for d in diffs[1:])  # 负增量递减（绝对值减小）


def compare_force(segment_A, segment_C, direction):
    """
    核心力比较函数: 使用MACD柱子面积比较两段走势的力度
    """
    macd_A = calc_histogram_area(get_macd_data(), segment_A.start, segment_A.end, direction)
    macd_C = calc_histogram_area(get_macd_data(), segment_C.start, segment_C.end, direction)
    
    # 原文: C段面积 < A段面积 → 背驰
    is_divergent = macd_C < macd_A
    
    # 辅助判断: DIF/DEA高度
    dif_peak_A = max(abs(macd_data.dif[segment_A.start:segment_A.end])) if direction == UP else \
                 min(macd_data.dif[segment_A.start:segment_A.end])
    dif_peak_C = max(abs(macd_data.dif[segment_C.start:segment_C.end])) if direction == UP else \
                 min(macd_data.dif[segment_C.start:segment_C.end])
    
    # 价格创新极值 but 指标未创新极值 → 强化背驰信号
    price_new_extreme = True  # 由调用者保证
    indicator_no_new_extreme = abs(dif_peak_C) < abs(dif_peak_A)
    
    strength = "STRONG" if (is_divergent and indicator_no_new_extreme) else \
               "NORMAL" if is_divergent else "NONE"
    
    return DivergenceResult(
        is_divergent=is_divergent,
        strength=strength,
        area_A=macd_A,
        area_C=macd_C,
        ratio=macd_C / macd_A if macd_A > 0 else 0
    )
```

### 4.4 零轴的含义

```
零轴上方（DIF > 0）:
  → 多头区域，短线多头主导
  → 上涨趋势段中DIF应在零轴上方
  
零轴下方（DIF < 0）:
  → 空头区域，短线空头主导
  → 下跌趋势段中DIF应在零轴下方

零轴附近（DIF ≈ 0）:
  → 多空平衡，中枢形成区域的标志
  → B中枢将DIF/DEA回拉到0轴附近，这是标准背驰结构的特征
```

---

## 5. 区间套：多级别联立精确定位

### 5.1 原理

原文（第27课、第61课）：类似数学分析中的**区间套定理**。大级别确认背驰段存在后，在次级别中找到该背驰段内部的背驰段，逐级收缩，直到最低级别，精确定位转折点。

**定理**（第27课）：
> "缠中说禅精确大转折点寻找程序定理：某大级别的转折点，可以通过不同级别背驰段的逐级收缩范围而确定。"

### 5.2 区间套算法

```python
def interval_squaring_find_turning_point(price_data, levels, direction):
    """
    区间套定位算法
    levels: 从大到小的级别列表，如 ["monthly", "weekly", "daily", "30min", "5min", "1min"]
    direction: UP(找顶) 或 DOWN(找底)
    
    返回: 精确的转折点区间 [left_bound, right_bound]
    """
    # 第一重: 在最大级别找背驰段
    current_level = levels[0]
    chart = get_chart(price_data, current_level)
    trend = identify_trend(chart, direction)
    
    # 在最大级别识别背驰段（不一定已确认背驰）
    div_result = detect_trend_divergence(trend, current_level)
    
    if not div_result.is_divergent:
        # 检查是否进入背驰段（可能尚未确认但已进入候选区域）
        if not is_entering_divergence_zone(trend, current_level, direction):
            return None  # 尚未进入任何背驰段
    
    # 背驰段的区间范围
    pivot_Z_last = trend.get_last_pivot(current_level)
    div_segment_start = pivot_Z_last.exit_point  # 离开最后中枢的起点
    div_segment_end = chart.current_position      # 当前位置
    
    bounds = [div_segment_start, div_segment_end]
    
    # 逐级下钻
    for i in range(1, len(levels)):
        sub_level = levels[i]
        sub_chart = get_chart(price_data, sub_level)
        
        # 在次级别中，找到对应上级背驰段区域的走势
        sub_trend = identify_trend_in_range(sub_chart, bounds[0], bounds[1], direction)
        
        if sub_trend is None:
            break
        
        # 在次级别找背驰段
        sub_div = detect_trend_divergence(sub_trend, sub_level)
        if not sub_div.is_divergent:
            # 检查盘整背驰
            sub_div = detect_consolidation_divergence(sub_trend, sub_level)
        
        if sub_div.is_divergent:
            # 收缩区间到次级别背驰段的范围
            sub_pivot = sub_trend.get_last_pivot(sub_level)
            bounds = [sub_pivot.exit_point, sub_div.segment_C.end_point]
        else:
            # 次级别尚未确认，继续等待
            # 但区间已缩小到最后一个次级别中枢离开段
            if sub_trend.get_last_pivot(sub_level):
                sub_pivot = sub_trend.get_last_pivot(sub_level)
                bounds = [sub_pivot.exit_point, sub_chart.current_position]
    
    return bounds  # 最终精确定位的转折点区间
```

### 5.3 原文案例（第61课）的四重背驰段

```
65开始的走势 = 第一重背驰段（围绕60-69这个5分钟中枢的离开段）
  └─ 69开始的走势 = 第二重（65背驰段内的背驰段）
       └─ 71开始的走势 = 第三重（背驰段的背驰段的背驰段）
            └─ 71内部走势 = 第四重（最终精确定位到72点）

72点 = 背驰段的背驰段的背驰段的背驰段 → 四重区间套定位
```

---

## 6. 背驰后的三种走势分类

原文（第29课）——**缠中说禅背驰-转折定理**：
> "某级别趋势的背驰将导致该趋势最后一个中枢的级别扩展、该级别更大级别的盘整或该级别以上级别的反趋势。"

### 6.1 三种分类详解

```
假设: 5分钟级别下跌趋势发生背驰（a + A + b + B + c，A、B为5分钟中枢）

┌─────────────────────────────────────────────────────┐
│ 分类一: 最后一个中枢的级别扩展                          │
│ ─────────────────────────────────                    │
│ 反弹只触及最后中枢B的DD=min(dn)                       │
│ → B扩展为30分钟甚至更大中枢                            │
│ → 仍在原走势类型中（未完成），不是独立走势类型的连接      │
│ → 最弱情况                                            │
│                                                       │
│ 判别: 反弹第一波（1分钟级别）不能回到最后中枢B内部       │
├─────────────────────────────────────────────────────┤
│ 分类二: 该级别更大级别的盘整                            │
│ ─────────────────────────────────                    │
│ 下跌(5分钟) + 盘整(≥30分钟)                           │
│ → 两个完成的走势类型连接                               │
│ → 盘整中枢级别 > 原趋势中枢级别                        │
│                                                       │
│ 判别: 反弹回到最后中枢B内部，但形成的新中枢级别更大      │
├─────────────────────────────────────────────────────┤
│ 分类三: 该级别以上级别的反趋势                          │
│ ─────────────────────────────────                    │
│ 下跌(5分钟) + 上涨(≥5分钟)                            │
│ → 两个完成的走势类型连接                               │
│ → 反趋势中枢级别 ≥ 原趋势中枢级别（可以同级）           │
│                                                       │
│ 判别: 反弹回到最后中枢B内部并形成第三类买点后持续上涨    │
└─────────────────────────────────────────────────────┘
```

### 6.2 分类判定算法

```python
def classify_post_divergence(divergence_point, last_pivot, level):
    """
    背驰后走势分类判定
    在背驰点之后，观察反弹第一波来预判分类
    """
    sub_level = get_sub_level(level)  # 次级别
    
    # Step 1: 等待背驰后的第一波反弹（次级别走势）
    first_bounce = wait_for_sub_level_move(divergence_point, sub_level, reverse_direction)
    
    # Step 2: 判断反弹是否回到最后中枢
    dd = last_pivot.get_min_oscillation_low()   # DD = min(dn)
    zg = last_pivot.get_upper_bound()           # ZG
    
    if first_bounce.highest_price < dd:
        # 反弹连DD都触及不了 → 分类一：最后中枢级别扩展
        # （理论上应在下方形成新的同级别中枢，与"最后一个中枢"矛盾，极罕见）
        return "EXTENSION"  # 最弱
    
    if first_bounce.highest_price >= dd and first_bounce.highest_price < zg:
        # 反弹触及DD但未突破ZG → 倾向分类一或分类二
        # 需继续观察后续走势完成情况
        return "EXTENSION_OR_LARGER_CONSOLIDATION"
    
    if first_bounce.highest_price >= zg:
        # 反弹突破ZG → 至少分类二或三
        # 关键看后续：
        # - 形成第三类买点后继续 → 分类三（反趋势）
        # - 形成更大级别中枢震荡 → 分类二（更大级别盘整）
        
        # 等待第一次回试
        first_pullback = wait_for_sub_level_move(first_bounce.end, sub_level, original_direction)
        
        if first_pullback.lowest_price >= zg:
            # 回试不破ZG → 第三类买点成立 → 分类三（反趋势）
            return "REVERSAL"
        else:
            # 回试跌破ZG → 继续中枢震荡
            return "LARGER_CONSOLIDATION"
    
    return "UNDETERMINED"
```

---

## 7. 综合判定主流程

```python
def full_divergence_analysis(price_data, levels, direction):
    """
    背驰综合分析主流程
    """
    results = {}
    
    for level in levels:
        chart = get_chart(price_data, level)
        trends = identify_all_trends(chart, level)
        
        for trend in trends:
            pivots = trend.get_pivots(level)
            
            if len(pivots) >= 2:
                # 趋势背驰检测
                div = detect_trend_divergence(trend, level)
                if div.is_divergent:
                    results[level] = {
                        "type": "TREND_DIVERGENCE",
                        "level": level,
                        "strength": div.strength,
                        "area_ratio": div.ratio,
                        "post_classification": "PENDING"  # 需后续观察
                    }
            elif len(pivots) == 1:
                # 盘整背驰检测
                div_list = detect_consolidation_divergence(trend, level)
                if div_list:
                    results[level] = {
                        "type": "CONSOLIDATION_DIVERGENCE",
                        "level": level,
                        "outcomes": [d.outcome for d in div_list]
                    }
    
    # 区间套精确定位（跨级别）
    turning_point = interval_squaring_find_turning_point(price_data, levels, direction)
    
    return {
        "divergences": results,
        "turning_point_range": turning_point,
        "recommendation": generate_recommendation(results, turning_point)
    }
```

---

## 8. 关键注意事项

### 8.1 "背了又背"问题

原文（第24课）暗示：趋势中背驰只产生一次。所谓"背了又背"，是因为判断的不是标准背驰——要么中枢数量不足，要么C段未创新高/低，要么是盘整背驰误判为趋势背驰。

### 8.2 背驰段的确认

背驰段不等于背驰。背驰段是"可能产生背驰的区间"，只有当C段走势类型完成且力度确认小于A段时，背驰才被确认。在未确认前，只标记为"进入背驰段"，需用区间套逐级观察。

### 8.3 MACD的局限性

原文（第24课）明确：
> "由于MACD本身的局限性，要精确地判断背驰与盘整背驰，还是要从中枢本身出发。"

MACD是**辅助工具**，精确判断应基于中枢结构和力度本质。配合中枢使用时准确率可达100%（纯数学可证）。

### 8.4 力度的本质定义

力度比较的严格定义不仅限于MACD面积。更精确的做法是比较两段走势内部的**中枢数量、走势级别和空间幅度**的综合力度。MACD面积是最实用的量化替代指标。

---

## 附录：关键原文索引

| 课题 | 标题 | 核心内容 |
|------|------|---------|
| 第24课 | MACD对背弛的辅助判断 | MACD面积比较法、标准背驰结构A+B+C |
| 第25课 | 吻，MACD、背弛、中枢 | 背驰与中枢关系、盘整背驰三种情况 |
| 第27课 | 盘整背驰与历史性底部 | 区间套原理、精确大转折点寻找程序定理 |
| 第29课 | 转折的力度与级别 | 背驰-转折定理、三种分类 |
| 第61课 | 区间套定位标准图解 | 四重背驰段实例、区间套当下定位 |
