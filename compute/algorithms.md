# 缠论核心算法伪代码汇编

> 本文件整合6份调研报告中的核心算法，按流水线顺序排列。
> 供 AI 执行具体缠论计算时读取。配合 `SKILL.md` 使用。

---

## §1 K线包含处理

```python
class KLine:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

def is_contain(k1: KLine, k2: KLine) -> bool:
    """两根K线是否存在包含关系"""
    return (k1.high >= k2.high and k1.low <= k2.low) or \
           (k1.high <= k2.high and k1.low >= k2.low)

def determine_direction(k_prev: KLine, k_curr: KLine) -> int:
    """
    方向判定：由包含对左侧的非包含K线决定
    返回: 1=向上, -1=向下
    """
    if k_curr.high > k_prev.high:
        return 1   # 向上
    elif k_curr.low < k_prev.low:
        return -1  # 向下
    else:
        raise ValueError("无法判定方向（两K线有包含关系）")

def merge_klines(k1: KLine, k2: KLine, direction: int) -> KLine:
    """合并两根K线"""
    if direction == 1:  # 向上 - 高高原则
        new_high = max(k1.high, k2.high)
        new_low = max(k1.low, k2.low)
    else:               # 向下 - 低低原则
        new_high = min(k1.high, k2.high)
        new_low = min(k1.low, k2.low)
    return KLine(
        timestamp=k1.timestamp,
        open=k1.open,
        high=new_high,
        low=new_low,
        close=k2.close
    )

def process_inclusion(klines: list[KLine]) -> list[KLine]:
    """
    处理K线序列中的所有包含关系（从左到右逐根处理）
    """
    if len(klines) <= 1:
        return klines.copy()
    
    result = [klines[0]]
    
    for i in range(1, len(klines)):
        prev = result[-1]
        curr = klines[i]
        
        if is_contain(prev, curr):
            # 向前找非包含K线判定方向
            direction = find_direction(result[:-1], prev)
            merged = merge_klines(prev, curr, direction)
            result[-1] = merged
            # 合并后可能与后续K线仍有包含，继续比较
            while len(result) >= 2 and is_contain(result[-2], result[-1]):
                direction = find_direction(result[:-2], result[-2])
                merged = merge_klines(result[-2], result[-1], direction)
                result.pop()
                result[-1] = merged
        else:
            result.append(curr)
    
    return result

def find_direction(processed: list[KLine], current: KLine) -> int:
    """在已处理序列中向前找非包含K线来判定方向"""
    if len(processed) == 0:
        return 1  # 默认向上
    for idx in range(len(processed) - 1, -1, -1):
        if not is_contain(processed[idx], current):
            return determine_direction(processed[idx], current)
    return determine_direction(processed[0], current)
```

---

## §2 分型识别

```python
def find_fractals(merged_klines: list[KLine]) -> list[dict]:
    """
    在包含处理后的K线序列上识别顶底分型
    返回: [{index, type, value, high, low}, ...]
    """
    fractals = []
    for i in range(1, len(merged_klines) - 1):
        g1, d1 = merged_klines[i-1].high, merged_klines[i-1].low
        g2, d2 = merged_klines[i].high, merged_klines[i].low
        g3, d3 = merged_klines[i+1].high, merged_klines[i+1].low
        
        if g2 > g1 and g2 > g3 and d2 > d1 and d2 > d3:
            fractals.append({
                'index': i,
                'type': 'top',
                'value': g2,       # 顶 = 最高价
                'high': g2,
                'low': d2
            })
        elif d2 < d1 and d2 < d3 and g2 < g1 and g2 < g3:
            fractals.append({
                'index': i,
                'type': 'bottom',
                'value': d2,       # 底 = 最低价
                'high': g2,
                'low': d2
            })
    
    return fractals
```

---

## §3 笔（Bi/Stroke）划分

```python
def determine_pens(raw_klines: list, merged_klines: list, 
                   fractals: list, mode: str = 'new') -> list[dict]:
    """
    笔划分完整算法
    mode: 'old'(旧笔,≥1处理后独立K线) 或 'new'(新笔,≥3原始K线)
    返回: [{start_idx, end_idx, direction, start_price, end_price}, ...]
    """
    
    # Step 1: 过滤同性质分型
    filtered = filter_same_type_fractals(fractals)
    
    # Step 2: 构造笔
    pens = []
    i = 0
    while i < len(filtered) - 1:
        curr = filtered[i]
        nxt = filtered[i + 1]
        
        # 跳过同性质
        if curr['type'] == nxt['type']:
            i += 1
            continue
        
        # 检查不共用K线
        if shares_kline(curr, nxt, merged_klines):
            i += 1
            continue
        
        # 检查独立K线条件
        if mode == 'old':
            if not has_independent_kline_old(curr, nxt, merged_klines):
                i += 1
                continue
        else:
            if not has_independent_kline_new(curr, nxt, raw_klines):
                i += 1
                continue
        
        # 空间约束：顶必须高于底
        top = curr if curr['type'] == 'top' else nxt
        bottom = nxt if curr['type'] == 'top' else curr
        if top['value'] <= bottom['value']:
            i += 1
            continue
        
        # 成笔
        direction = 'up' if curr['type'] == 'bottom' else 'down'
        pens.append({
            'start_index': curr['index'],
            'end_index': nxt['index'],
            'direction': direction,
            'start_price': curr['value'],
            'end_price': nxt['value']
        })
        i += 1
    
    # Step 3: 处理连续同性质残留
    pens = resolve_consecutive_same_type(pens, filtered)
    
    return pens


def filter_same_type_fractals(fractals: list) -> list:
    """
    同性质分型过滤
    - 连续两顶：前低后高 → 保留后者
    - 连续两底：前高后低 → 保留后者
    """
    if not fractals:
        return []
    result = [fractals[0]]
    for f in fractals[1:]:
        prev = result[-1]
        if f['type'] == prev['type']:
            if f['type'] == 'top' and f['value'] > prev['value']:
                result[-1] = f
            elif f['type'] == 'bottom' and f['value'] < prev['value']:
                result[-1] = f
            else:
                result.append(f)
        else:
            result.append(f)
    return result


def has_independent_kline_old(f1, f2, merged_klines) -> bool:
    """旧笔：包含处理后两分型之间至少1根独立K线"""
    return abs(f2['index'] - f1['index']) >= 3


def has_independent_kline_new(f1, f2, raw_klines) -> bool:
    """新笔：原始K线中两分型极值K线之间至少3根（不考虑包含）"""
    raw_idx1 = get_raw_index_of_extreme(f1, raw_klines)
    raw_idx2 = get_raw_index_of_extreme(f2, raw_klines)
    return abs(raw_idx2 - raw_idx1) >= 4


def shares_kline(f1, f2, merged_klines) -> bool:
    """检查两分型是否共用K线（结合律）"""
    # 分型各占3根中间一根，不共用 = idx差≥2
    return abs(f2['index'] - f1['index']) < 2


def resolve_consecutive_same_type(pens, fractals):
    """处理连续同性质：连续顶后出底 → 首顶+底成笔"""
    if len(fractals) < 2:
        return pens
    result = []
    i = 0
    while i < len(fractals):
        if i + 1 >= len(fractals):
            break
        curr = fractals[i]
        j = i + 1
        while j < len(fractals) and fractals[j]['type'] == curr['type']:
            j += 1
        if j >= len(fractals):
            break
        opposite = fractals[j]
        if can_form_pen(curr, opposite):
            direction = 'up' if curr['type'] == 'bottom' else 'down'
            result.append({
                'start_index': curr['index'],
                'end_index': opposite['index'],
                'direction': direction,
                'start_price': curr['value'],
                'end_price': opposite['value']
            })
        i = j
    return result if result else pens
```

---

## §4 线段（Segment）划分

```python
class Segment:
    start_index: int
    end_index: int
    direction: str     # 'up' | 'down'
    high: float
    low: float
    pens: list         # 构成线段的笔列表

def extract_feature_sequence(segment: Segment, all_pens: list) -> list:
    """
    提取特征序列
    向上线段 → 特征序列 = 向下笔序列
    向下线段 → 特征序列 = 向上笔序列
    """
    direction = segment.direction
    feature = []
    for pen in segment.pens:
        if direction == 'up' and pen['direction'] == 'down':
            feature.append(pen)
        elif direction == 'down' and pen['direction'] == 'up':
            feature.append(pen)
    return feature

def process_feature_inclusion(feature_seq: list, direction: str) -> list:
    """
    特征序列包含处理
    direction: 线段方向（'up' 或 'down'）
    """
    if len(feature_seq) <= 1:
        return feature_seq
    
    result = [feature_seq[0]]
    for i in range(1, len(feature_seq)):
        prev = result[-1]
        curr = feature_seq[i]
        
        # 包含判定
        prev_high = prev.get('high', max(prev['start_price'], prev['end_price']))
        prev_low = prev.get('low', min(prev['start_price'], prev['end_price']))
        curr_high = curr.get('high', max(curr['start_price'], curr['end_price']))
        curr_low = curr.get('low', min(curr['start_price'], curr['end_price']))
        
        if (prev_high >= curr_high and prev_low <= curr_low) or \
           (prev_high <= curr_high and prev_low >= curr_low):
            # 包含，合并
            if direction == 'up':
                new_high = max(prev_high, curr_high)
                new_low = max(prev_low, curr_low)
            else:
                new_high = min(prev_high, curr_high)
                new_low = min(prev_low, curr_low)
            merged = {**prev, 'high': new_high, 'low': new_low}
            result[-1] = merged
        else:
            result.append(curr)
    
    return result

def elements_overlap(a, b) -> bool:
    """两元素是否有重叠区间"""
    a_high = a.get('high', max(a['start_price'], a['end_price']))
    a_low = a.get('low', min(a['start_price'], a['end_price']))
    b_high = b.get('high', max(b['start_price'], b['end_price']))
    b_low = b.get('low', min(b['start_price'], b['end_price']))
    return not (a_high < b_low or b_high < a_low)

def check_segment_destruction(segment, feature_seq, direction):
    """
    线段破坏判定（两种情况）
    返回: ('broken_type1', end_idx) | ('broken_type2', end_idx) | ('continue', None)
    """
    standard_seq = process_feature_inclusion(feature_seq, direction)
    
    if len(standard_seq) < 3:
        return ('continue', None)
    
    # 检查最后三个元素是否形成分型
    e1, e2, e3 = standard_seq[-3], standard_seq[-2], standard_seq[-1]
    e1_h = e1.get('high', max(e1['start_price'], e1['end_price']))
    e1_l = e1.get('low', min(e1['start_price'], e1['end_price']))
    e2_h = e2.get('high', max(e2['start_price'], e2['end_price']))
    e2_l = e2.get('low', min(e2['start_price'], e2['end_price']))
    e3_h = e3.get('high', max(e3['start_price'], e3['end_price']))
    e3_l = e3.get('low', min(e3['start_price'], e3['end_price']))
    
    # 向上线段检查特征序列顶分型
    is_top_form = (e2_h >= e1_h and e2_h >= e3_h)
    # 向下线段检查特征序列底分型
    is_bottom_form = (e2_l <= e1_l and e2_l <= e3_l)
    
    if direction == 'up' and is_top_form:
        has_gap = not elements_overlap(e1, e2)
        if not has_gap:
            return ('broken_type1', e2.get('end_index', e2['end_index']))
        else:
            # 第二种情况：检查第二特征序列
            # 需要从 e2 对应位置开始的新走势中提取第二特征序列
            return ('need_type2_check', e2.get('end_index', e2['end_index']))
    
    if direction == 'down' and is_bottom_form:
        has_gap = not elements_overlap(e1, e2)
        if not has_gap:
            return ('broken_type1', e2.get('end_index', e2['end_index']))
        else:
            return ('need_type2_check', e2.get('end_index', e2['end_index']))
    
    return ('continue', None)

def segment_division(pens: list) -> list[Segment]:
    """
    完整线段划分算法
    输入: 笔列表
    输出: 线段列表
    """
    if len(pens) < 3:
        return []
    
    segments = []
    # 初始化第一个线段候选
    current_dir = pens[0]['direction']
    current_pens = [pens[0]]
    
    for i in range(1, len(pens)):
        current_pens.append(pens[i])
        
        if len(current_pens) >= 3:
            feature_seq = extract_feature_sequence_from_pens(current_pens, current_dir)
            result, end_idx = check_segment_destruction(None, feature_seq, current_dir)
            
            if result in ('broken_type1', 'broken_type2'):
                # 线段结束
                seg = Segment(
                    start_index=current_pens[0]['start_index'],
                    end_index=end_idx,
                    direction=current_dir,
                    high=max(p.get('end_price', p.get('start_price')) for p in current_pens),
                    low=min(p.get('end_price', p.get('start_price')) for p in current_pens),
                    pens=current_pens[:]
                )
                segments.append(seg)
                # 开始新线段
                current_dir = 'down' if current_dir == 'up' else 'up'
                current_pens = [pens[i]]
    
    # 未完成线段
    if current_pens:
        seg = Segment(
            start_index=current_pens[0]['start_index'],
            end_index=current_pens[-1]['end_index'],
            direction=current_dir,
            high=max(p.get('end_price', p.get('start_price')) for p in current_pens),
            low=min(p.get('end_price', p.get('start_price')) for p in current_pens),
            pens=current_pens[:]
        )
        segments.append(seg)
    
    return segments
```

---

## §5 中枢（Pivot）识别

```python
class Pivot:
    ZG: float           # 中枢上沿 = min(线段高点)
    ZD: float           # 中枢下沿 = max(线段低点)
    GG: float           # 最高点
    DD: float           # 最低点
    level: str          # 级别
    direction: str      # '上涨中枢' | '下跌中枢'
    start_index: int
    end_index: int
    segments: list      # 构成中枢的线段
    extension_count: int # 延伸段数

def calculate_pivot(segments: list, level: str) -> Pivot:
    """
    从至少3个连续线段计算中枢区间
    ZG = min(highs), ZD = max(lows)
    """
    if len(segments) < 3:
        raise ValueError("至少需要3个线段")
    
    seg3 = segments[:3]
    highs = [s.high for s in seg3]
    lows = [s.low for s in seg3]
    
    ZG = min(highs)
    ZD = max(lows)
    
    if ZD >= ZG:
        raise ValueError(f"无重叠区间: ZD={ZD} >= ZG={ZG}")
    
    direction = '上涨中枢' if seg3[0].direction == 'up' else '下跌中枢'
    
    return Pivot(
        ZG=ZG, ZD=ZD,
        GG=max(highs), DD=min(lows),
        level=level, direction=direction,
        start_index=seg3[0].start_index,
        end_index=seg3[-1].end_index,
        segments=seg3,
        extension_count=0
    )

def identify_pivots(segments: list, level: str) -> list[Pivot]:
    """
    从线段序列中识别所有中枢
    """
    pivots = []
    i = 0
    
    while i <= len(segments) - 3:
        # 尝试用 segments[i:i+3] 构建中枢
        window = segments[i:i+3]
        try:
            pivot = calculate_pivot(window, level)
            # 检查后续线段是否构成延伸
            j = i + 3
            while j < len(segments):
                seg = segments[j]
                if seg.high > pivot.ZD and seg.low < pivot.ZG:
                    pivot.extension_count += 1
                    pivot.end_index = seg.end_index
                    pivot.GG = max(pivot.GG, seg.high)
                    pivot.DD = min(pivot.DD, seg.low)
                    j += 1
                else:
                    break
            
            pivots.append(pivot)
            i = j  # 跳过已处理的线段
        except ValueError:
            i += 1
    
    return pivots

def check_pivot_upgrade(pivot: Pivot) -> bool:
    """9段及以上延伸 → 中枢升级"""
    return pivot.extension_count >= 6  # 3基础段 + 6延伸段 = 9段
```

---

## §6 背驰（Divergence）检测

```python
def calc_macd(close_prices: list, fast=12, slow=26, signal=9) -> dict:
    """标准MACD计算"""
    ema_fast = EMA(close_prices, fast)
    ema_slow = EMA(close_prices, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = EMA(dif, signal)
    histogram = [2 * (d - e) for d, e in zip(dif, dea)]
    return {'dif': dif, 'dea': dea, 'histogram': histogram}

def calc_histogram_area(macd_data: dict, start: int, end: int, 
                        direction: str) -> float:
    """
    计算MACD柱子累积面积
    direction='up' 取正值(红柱), 'down' 取负值的绝对值(绿柱)
    """
    total = 0.0
    for i in range(start, end + 1):
        bar = macd_data['histogram'][i]
        if direction == 'up' and bar > 0:
            total += bar
        elif direction == 'down' and bar < 0:
            total += abs(bar)
    return total

def is_macd_near_zero_axis(macd_data: dict, start: int, end: int,
                           threshold: float = 0.1) -> bool:
    """B中枢期间DIF是否回拉到0轴附近"""
    dif_values = macd_data['dif'][start:end+1]
    return all(abs(d) < threshold for d in dif_values)

def compare_force(macd_data: dict, seg_a_range: tuple, seg_c_range: tuple,
                  direction: str) -> dict:
    """
    核心力比较：MACD柱子面积
    seg_a_range = (start_idx, end_idx) of A段
    seg_c_range = (start_idx, end_idx) of C段
    """
    area_a = calc_histogram_area(macd_data, seg_a_range[0], seg_a_range[1], direction)
    area_c = calc_histogram_area(macd_data, seg_c_range[0], seg_c_range[1], direction)
    
    is_divergent = area_c < area_a
    ratio = area_c / area_a if area_a > 0 else 0
    
    strength = 'STRONG' if ratio < 0.5 else 'NORMAL' if ratio < 0.7 else 'NONE'
    
    return {
        'is_divergent': is_divergent,
        'area_a': area_a,
        'area_c': area_c,
        'area_ratio': ratio,
        'strength': strength if is_divergent else 'NONE'
    }

def detect_trend_divergence(macd_data: dict, pivots: list, 
                            segments: list, direction: str) -> list:
    """
    趋势背驰检测
    前提：至少2个同级别中枢
    """
    results = []
    
    if len(pivots) < 2:
        return results
    
    for i in range(len(pivots) - 1):
        Z_prev = pivots[i]
        Z_last = pivots[i + 1]
        
        # A段：离开 Z_prev 的走势
        seg_a = get_segment_between_pivots(segments, Z_prev, Z_last)
        # C段：离开 Z_last 的走势
        seg_c = get_segment_after_pivot(segments, Z_last)
        
        if seg_a is None or seg_c is None:
            continue
        
        # 检查创新极值
        if direction == 'up':
            new_extreme = seg_c.high > seg_a.high
        else:
            new_extreme = seg_c.low < seg_a.low
        
        if not new_extreme:
            continue
        
        # 检查 MACD 回拉0轴
        near_zero = is_macd_near_zero_axis(
            macd_data, Z_last.start_index, Z_last.end_index)
        
        # 力度比较
        force = compare_force(
            macd_data,
            (seg_a.start_index, seg_a.end_index),
            (seg_c.start_index, seg_c.end_index),
            direction
        )
        
        if force['is_divergent'] and near_zero:
            results.append({
                'type': 'trend_divergence',
                'direction': direction,
                'pivot_A': Z_prev,
                'pivot_B': Z_last,
                'segment_a': seg_a,
                'segment_c': seg_c,
                **force
            })
    
    return results

def interval_squaring(macd_data_by_level: dict, levels: list, 
                      direction: str) -> dict:
    """
    区间套定位：从大级别到小级别逐级收缩转折点区间
    """
    bounds = None
    levels_confirmed = 0
    
    for level in levels:
        pivots = identify_pivots_for_level(macd_data_by_level[level], level)
        divs = detect_trend_divergence(macd_data_by_level[level], pivots, 
                                        ..., direction)
        
        if divs:
            last_div = divs[-1]
            if bounds is None:
                bounds = [last_div['segment_c'].start_index,
                          last_div['segment_c'].end_index]
            else:
                # 收缩到次级别背驰段范围
                new_start = max(bounds[0], last_div['segment_c'].start_index)
                new_end = min(bounds[1], last_div['segment_c'].end_index)
                if new_start < new_end:
                    bounds = [new_start, new_end]
            levels_confirmed += 1
        elif bounds:
            break  # 次级别无背驰，停止收缩
    
    return {
        'turning_point_range': bounds,
        'levels_confirmed': levels_confirmed
    }
```

---

## §7 三类买卖点标注

```python
def detect_buy1(macd_data: dict, pivots: list, segments: list,
                level: str) -> list:
    """
    第一类买点：下跌趋势中最后一个中枢后c段趋势背驰的最低点
    """
    results = []
    
    # 找下跌趋势（≥2个依次向下的同级别中枢）
    downtrend_pivots = [p for p in pivots if p.direction == '下跌中枢']
    downtrend_pivots = sorted(downtrend_pivots, key=lambda p: p.ZG)
    
    if len(downtrend_pivots) < 2:
        return results
    
    for i in range(len(downtrend_pivots) - 1):
        A = downtrend_pivots[i]
        B = downtrend_pivots[i + 1]
        
        if A.ZG <= B.ZG:  # 不是依次向下
            continue
        
        c_segment = get_segment_after_pivot(segments, B)
        if c_segment is None:
            continue
        
        # c段必须创新低
        if c_segment.low >= B.DD:
            continue
        
        # 趋势背驰判定
        a_segment = get_segment_between_pivots(segments, A, B)
        force = compare_force(
            macd_data,
            (a_segment.start_index, a_segment.end_index),
            (c_segment.start_index, c_segment.end_index),
            'down'
        )
        
        if force['is_divergent']:
            results.append({
                'type': 1, 'side': 'buy', 'level': level,
                'price': c_segment.low,
                'index': c_segment.end_index,
                'confidence': 0.95 if force['area_ratio'] < 0.5 else \
                              0.85 if force['area_ratio'] < 0.7 else 0.7,
                'pivot_ref_ZG': B.ZG,
                'pivot_ref_ZD': B.ZD,
                'note': f"趋势背驰，面积比={force['area_ratio']:.2f}"
            })
    
    return results

def detect_buy2(buy1_list: list, segments: list, level: str,
                pivots: list) -> list:
    """
    第二类买点：Buy1后第一次次级别回调的低点（不破Buy1）
    """
    results = []
    sub_level = get_sub_level(level)
    
    for buy1 in buy1_list:
        if buy1['side'] != 'buy' or buy1['type'] != 1:
            continue
        
        # Buy1之后的次级别走势分解
        sub_moves = get_sub_moves_after(segments, buy1['index'], sub_level)
        if len(sub_moves) < 2:
            continue
        
        move1 = sub_moves[0]  # 应向上
        move2 = sub_moves[1]  # 应向下
        
        if move1['direction'] != 'up' or move2['direction'] != 'down':
            continue
        
        buy2_price = move2['low']
        if buy2_price <= buy1['price']:  # 跌破Buy1
            continue
        
        # Buy2与关联中枢的位置关系
        last_pivot = find_pivot_at(pivots, buy1['index'])
        position = 'above_pivot' if buy2_price >= last_pivot.ZG else \
                   'in_pivot' if buy2_price >= last_pivot.ZD else 'below_pivot'
        
        confidence = {'above_pivot': 0.9, 'in_pivot': 0.75, 
                      'below_pivot': 0.6}[position]
        
        results.append({
            'type': 2, 'side': 'buy', 'level': level,
            'price': buy2_price,
            'index': move2['end_index'],
            'confidence': confidence,
            'pivot_ref_ZG': last_pivot.ZG,
            'pivot_ref_ZD': last_pivot.ZD,
            'note': f"Buy2在{position}"
        })
    
    return results

def detect_buy3(pivots: list, segments: list, level: str) -> list:
    """
    第三类买点：次级别向上离开中枢后，回抽低点≥ZG
    """
    results = []
    sub_level = get_sub_level(level)
    
    for pivot in pivots:
        leaving_moves = find_leaving_moves(segments, pivot, sub_level, 'up')
        
        for leave in leaving_moves:
            pullback = find_pullback_after(segments, leave, sub_level, 'down')
            if pullback is None:
                continue
            
            # 核心：回抽低点不跌破ZG
            if pullback['low'] >= pivot.ZG:
                results.append({
                    'type': 3, 'side': 'buy', 'level': level,
                    'price': pullback['low'],
                    'index': pullback['end_index'],
                    'confidence': 0.85,
                    'pivot_ref_ZG': pivot.ZG,
                    'pivot_ref_ZD': pivot.ZD,
                    'note': f"回抽不破ZG={pivot.ZG}"
                })
    
    return results

def detect_sell1(macd_data: dict, pivots: list, segments: list,
                 level: str) -> list:
    """第一类卖点：上涨趋势c段背驰（Buy1镜像）"""
    results = []
    uptrend_pivots = [p for p in pivots if p.direction == '上涨中枢']
    uptrend_pivots = sorted(uptrend_pivots, key=lambda p: p.ZD)
    
    if len(uptrend_pivots) < 2:
        return results
    
    for i in range(len(uptrend_pivots) - 1):
        A = uptrend_pivots[i]
        B = uptrend_pivots[i + 1]
        if A.ZD >= B.ZD:
            continue
        c_segment = get_segment_after_pivot(segments, B)
        if c_segment is None or c_segment.high <= B.GG:
            continue
        a_segment = get_segment_between_pivots(segments, A, B)
        force = compare_force(macd_data,
            (a_segment.start_index, a_segment.end_index),
            (c_segment.start_index, c_segment.end_index), 'up')
        if force['is_divergent']:
            results.append({
                'type': 1, 'side': 'sell', 'level': level,
                'price': c_segment.high,
                'index': c_segment.end_index,
                'confidence': 0.95 if force['area_ratio'] < 0.5 else 0.85,
                'pivot_ref_ZG': B.ZG, 'pivot_ref_ZD': B.ZD,
                'note': f"上涨背驰，面积比={force['area_ratio']:.2f}"
            })
    return results

def detect_sell3(pivots: list, segments: list, level: str) -> list:
    """第三类卖点：次级别向下离开后，回抽高点≤ZD"""
    results = []
    sub_level = get_sub_level(level)
    for pivot in pivots:
        leaving_moves = find_leaving_moves(segments, pivot, sub_level, 'down')
        for leave in leaving_moves:
            pullback = find_pullback_after(segments, leave, sub_level, 'up')
            if pullback is None:
                continue
            if pullback['high'] <= pivot.ZD:
                results.append({
                    'type': 3, 'side': 'sell', 'level': level,
                    'price': pullback['high'],
                    'index': pullback['end_index'],
                    'confidence': 0.85,
                    'pivot_ref_ZG': pivot.ZG, 'pivot_ref_ZD': pivot.ZD,
                    'note': f"回抽不破ZD={pivot.ZD}"
                })
    return results

def detect_all_buy_sell_points(klines, level):
    """全量买卖点检测（统一入口）"""
    # 前置处理
    merged = process_inclusion(klines)
    fractals = find_fractals(merged)
    pens = determine_pens(klines, merged, fractals)
    segments = segment_division(pens)
    pivots = identify_pivots(segments, level)
    macd_data = calc_macd([k.close for k in klines])
    
    # 买卖点检测（有依赖顺序）
    buy1 = detect_buy1(macd_data, pivots, segments, level)
    sell1 = detect_sell1(macd_data, pivots, segments, level)
    buy2 = detect_buy2(buy1, segments, level, pivots)
    sell2 = detect_sell2(sell1, segments, level, pivots)  # 镜像Buy2
    buy3 = detect_buy3(pivots, segments, level)
    sell3 = detect_sell3(pivots, segments, level)
    
    all_points = buy1 + buy2 + buy3 + sell1 + sell2 + sell3
    all_points.sort(key=lambda p: p['index'])
    
    return all_points
```

---

## 辅助函数（桩函数，需根据数据结构实现）

```python
def EMA(data, period):
    """指数移动平均"""
    result = [data[0]]
    k = 2 / (period + 1)
    for i in range(1, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result

def get_sub_level(level: str) -> str:
    hierarchy = ['1F', '5F', '30F', 'D', 'W', 'M']
    idx = hierarchy.index(level) if level in hierarchy else 0
    return hierarchy[max(0, idx - 1)]

def get_segment_between_pivots(segments, pivot_a, pivot_b):
    """获取两个中枢之间的走势段"""
    for seg in segments:
        if seg.start_index >= pivot_a.end_index and seg.end_index <= pivot_b.start_index:
            return seg
    return None

def get_segment_after_pivot(segments, pivot):
    """获取中枢之后的走势段"""
    for seg in segments:
        if seg.start_index >= pivot.end_index:
            return seg
    return None

def find_leaving_moves(segments, pivot, sub_level, direction):
    """找到离开中枢的次级别走势"""
    results = []
    for seg in segments:
        if seg.start_index >= pivot.end_index and seg.direction == direction:
            if direction == 'up' and seg.low >= pivot.ZD:
                results.append(seg)
            elif direction == 'down' and seg.high <= pivot.ZG:
                results.append(seg)
    return results

def find_pullback_after(segments, leave_move, sub_level, direction):
    """找到离开走势后的回抽"""
    for seg in segments:
        if seg.start_index > leave_move.end_index and seg.direction == direction:
            return {
                'high': seg.high, 'low': seg.low,
                'end_index': seg.end_index
            }
    return None
```
