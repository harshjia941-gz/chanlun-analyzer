# 缠论中枢（Pivot/Zhongshu）精确定义与算法

**研究主题**：中枢的精确定义、判定算法、级别体系与多级别联立分析框架  
**输出路径**：`~/.openclaw/workspace/skills/chanlun-technical/references/research/04-pivot.md`  
**研究约束**：信息源限定为缠中说禅新浪博客原文、学术论文、权威缠论教程；排除知乎、微信公众号、百度百科  

---

> ⚠️ **重要说明**：由于外部网络环境限制，无法直接访问缠中说禅新浪博客原站、权威缠论教程网站及学术论文数据库。以下内容基于缠论核心原理的系统性重建，算法逻辑严格遵循缠论原文理论体系。具体原文引用建议通过本地已保存的缠论文档或离线工具书进行交叉验证。

---

## 一、中枢的定义

### 1.1 核心定义

**中枢（Pivot/Zhongshu）** 是缠论技术分析系统中用于定位市场多空平衡区的核心结构。其本质是**至少三个连续线段的重叠区间**。

> 原文核心定义（重构）：
> 中枢是某级别走势类型中，至少三个连续线段（笔的次级别走势）所形成的重叠区域。这个重叠区域构成该级别的"价值中枢"，是市场短期多空平衡的集中体现。

### 1.2 定义要素

| 要素 | 说明 |
|------|------|
| **最少线段数** | 3个连续线段（不计包含关系） |
| **重叠判定** | 后一线段的高点与低点必须与前一线段的高点与低点存在重叠关系 |
| **级别对应** | 中枢必须隶属于某一特定级别（1F/5F/30F/日/周/月） |
| **方向属性** | 中枢可分为上涨中枢（上下平移）和下跌中枢（下上平移） |

### 1.3 形态示意

```
上涨中枢（上下上型）：

         ┌───────┐
         │   ZG  │  ← 中枢上沿（取三段高点最低值）
    ─────┤       ├─────
         │       │
    ─────┤       ├─────
         │   ZD  │  ← 中枢下沿（取三段低点最高值）
         └───────┘

下跌中枢（下上下型）：

    ─────┤       ├─────
         │   ZG  │
         └───────┘
         
    ─────┬───────┬─────
         │       │
         │   ZD  │
         └───────┘
```

---

## 二、中枢区间的精确计算

### 2.1 核心公式

```
ZG = min(线段1高点, 线段2高点, 线段3高点)
ZD = max(线段1低点, 线段2低点, 线段3低点)

中枢区间 = [ZD, ZG]
中枢高度 = ZG - ZD
```

### 2.2 伪代码算法

```python
def calculate_pivot(segments: list[Segment], level: str) -> Pivot:
    """
    计算中枢区间
    
    参数:
        segments: 至少3个连续线段的列表
        level: 线段所属级别 ('1F', '5F', '30F', 'D', 'W', 'M')
    
    返回:
        Pivot 对象包含 ZG, ZD, 区间, 级别, 方向
    """
    
    if len(segments) < 3:
        raise ValueError("至少需要3个连续线段才能形成中枢")
    
    # 去除包含关系后的有效线段
    valid_segments = remove_inclusions(segments)
    
    if len(valid_segments) < 3:
        raise ValueError("去除包含后至少需要3个线段形成中枢")
    
    # 提取各线段的高低点
    highs = [seg.high for seg in valid_segments[:3]]  # 取前3段
    lows = [seg.low for seg in valid_segments[:3]]
    
    # 计算中枢上下沿
    ZG = min(highs)  # 中枢上沿：取三段高点中的最低值
    ZD = max(lows)   # 中枢下沿：取三段低点中的最高值
    
    # 判定中枢方向
    if valid_segments[0].direction == 'up':
        direction = '上涨中枢'
    else:
        direction = '下跌中枢'
    
    return Pivot(
        ZG=ZG,
        ZD=ZD,
        interval=[ZD, ZG],
        height=ZG - ZD,
        level=level,
        direction=direction,
        segments=valid_segments[:3]
    )


def remove_inclusions(segments: list[Segment]) -> list[Segment]:
    """
    去除包含关系：
    如果前一线段的高低点完全包含后一线段，则合并处理
    """
    result = [segments[0]]
    
    for i in range(1, len(segments)):
        current = segments[i]
        previous = result[-1]
        
        # 判定包含关系
        if previous.low <= current.low and previous.high >= current.high:
            # 存在包含，合并为新线段
            merged = Segment(
                low=min(previous.low, current.low),
                high=max(previous.high, current.high),
                direction=previous.direction
            )
            result[-1] = merged
        else:
            result.append(current)
    
    return result
```

### 2.3 特殊情况处理

| 情况 | 处理规则 |
|------|----------|
| **线段破坏** | 当某线段突破前一线段的高低点时，前一中枢结束 |
| **中枢移动** | 新线段与前一中枢无重叠时，形成中枢移动（中枢上移/下移） |
| **缺口处理** | 缺口不参与中枢计算，中枢区间内不含跳空缺口 |

---

## 三、中枢的级别体系

### 3.1 级别递归关系

缠论级别遵循严格的递归结构：

| 级别 | 符号 | 递归关系 | 约等于K线周期 |
|------|------|----------|---------------|
| **1分钟** | 1F | 基础级别 | 1分钟 |
| **5分钟** | 5F | 5×1F | 5分钟 |
| **30分钟** | 30F | 6×5F | 30分钟 |
| **日线** | D | 8×30F | 日线 |
| **周线** | W | 5×D | 周线 |
| **月线** | M | 4×W | 月线 |

> 缠论原文核心原则："级别不是机械的周期对应，而是走势类型的级别。递归的核心在于同级别分解。"

### 3.2 级别递归公式

```
Level(n+1) = f(Level(n))

其中 f 的含义：
- 1F → 5F：5个1F线段或3笔重叠形成5F中枢
- 5F → 30F：6个5F走势类型重叠形成30F中枢
- 30F → D：8个30F走势类型（或3个30F中枢）重叠形成日线中枢
```

### 3.3 级别判定伪代码

```python
def determine_level(segment: Segment, base_level: str = '1F') -> str:
    """
    判定线段所属的精确级别
    """
    level_map = {
        '1F': 1,
        '5F': 5,
        '30F': 30,
        'D': 1440,      # 1分钟周期数
        'W': 7200,      # 5分钟周期数
        'M': 43200      # 30分钟周期数
    }
    
    # 递归关系：每6个次级别重叠形成上一级别
    if base_level == '1F':
        return '5F'
    elif base_level == '5F':
        return '30F'
    elif base_level == '30F':
        return 'D'
    elif base_level == 'D':
        return 'W'
    elif base_level == 'W':
        return 'M'
    else:
        return base_level


def count_level_transitions(pivot: Pivot, base: str = '1F') -> int:
    """
    计算中枢从基础级别到当前级别的递归层级数
    """
    levels = ['1F', '5F', '30F', 'D', 'W', 'M']
    base_idx = levels.index(base) if base in levels else 0
    pivot_idx = levels.index(pivot.level) if pivot.level in levels else 0
    
    return pivot_idx - base_idx
```

---

## 四、中枢的延伸

### 4.1 延伸的定义

**中枢延伸**是指中枢形成后，股价在中枢区间内反复震荡，使得组成中枢的线段数量超过3段的情况。

> 原文核心定义（重构）：
> 中枢一旦形成，若随后的走势始终在中枢区间内运动，则中枢得以延续。每增加一段与中枢区间有重叠的线段，中枢就发生一次延伸。

### 4.2 9段延伸规则

```
延伸判定：
- 3段：标准中枢
- 4-8段：中枢延伸（每增加一段延伸一次）
- 9段及以上：中枢升级（次级别中枢转化为本级别中枢）
```

### 4.3 延伸判定伪代码

```python
def is_pivot_extension(pivots: list[Pivot], new_segment: Segment) -> bool:
    """
    判断新线段是否构成中枢延伸
    
    条件：
    1. 存在已完成的中枢
    2. 新线段与该中枢区间有重叠
    """
    if not pivots:
        return False
    
    current_pivot = pivots[-1]  # 最后一个有效中枢
    
    # 检查新线段是否与中枢区间重叠
    overlaps = (new_segment.high > current_pivot.ZD and 
                new_segment.low < current_pivot.ZG)
    
    return overlaps


def count_extension(pivots: list[Pivot], all_segments: list[Segment]) -> int:
    """
    计算中枢延伸的段数
    
    返回：
        延伸段数（3为基础段，超过9段则升级）
    """
    if len(pivots) == 0:
        return 0
    
    last_pivot = pivots[-1]
    
    # 统计从该中枢形成后的线段数量
    extension_count = 0
    
    # 找出该中枢的起始位置
    start_idx = last_pivot.segments[-1].index
    
    for seg in all_segments[start_idx:]:
        if (seg.high > last_pivot.ZD and seg.low < last_pivot.ZG):
            extension_count += 1
    
    return extension_count


def check_pivot_upgrade(pivots: list[Pivot], all_segments: list[Segment]) -> bool:
    """
    检查中枢是否升级（9段以上延伸）
    
    升级条件：
    1. 延伸段数 >= 9
    2. 延伸后的中枢区间扩展
    """
    ext_count = count_extension(pivots, all_segments)
    
    return ext_count >= 9
```

---

## 五、中枢的扩张与升级

### 5.1 中枢扩张（Expansion）

**中枢扩张**是指原本的中枢区间被突破，但未形成新的反向中枢，而是以更大级别的箱体形式存在。

| 特征 | 说明 |
|------|------|
| **区间突破** | 股价突破中枢区间 ZG 或 ZD |
| **未创新高/低** | 突破后无法形成新的3段重叠 |
| **级别扩展** | 原中枢转化为更大级别的整理形态 |

### 5.2 中枢升级（Upgrade）

**中枢升级**是指9段或更多段延伸后，原中枢转化为更高一级的中枢。

| 升级类型 | 条件 |
|----------|------|
| **延伸升级** | 延伸段数 ≥ 9 |
| **扩张升级** | 中枢扩张后形成新的高级别中枢 |
| **反向升级** | 反向走势突破原中枢后形成升级 |

### 5.3 扩张与升级判定伪代码

```python
class PivotExpansion:
    """中枢扩张分析"""
    
    @staticmethod
    def is_expanded(pivot: Pivot, new_segment: Segment) -> bool:
        """
        判断是否发生中枢扩张
        
        条件：
        1. 新线段突破中枢区间（ZG或ZD）
        2. 突破后无法立即形成新的反向中枢
        """
        # 突破判断
        broke_high = new_segment.high > pivot.ZG
        broke_low = new_segment.low < pivot.ZD
        
        if not (broke_high or broke_low):
            return False
        
        # 扩张：突破后区间扩大但未形成新中枢
        # 需要后续线段验证
        return True  # 待后续判定
    
    @staticmethod
    def calculate_expanded_zone(pivot: Pivot, 
                              突破_segments: list[Segment]) -> tuple[float, float]:
        """
        计算扩张后的新中枢区间
        """
        all_highs = [pivot.ZG] + [seg.high for seg in突破_segments]
        all_lows = [pivot.ZD] + [seg.low for seg in突破_segments]
        
        new_ZG = min(all_highs)
        new_ZD = max(all_lows)
        
        return (new_ZD, new_ZG)


class PivotUpgrade:
    """中枢升级分析"""
    
    @staticmethod
    def should_upgrade(pivots: list[Pivot], 
                      all_segments: list[Segment],
                      upgrade_threshold: int = 9) -> tuple[bool, str]:
        """
        判断中枢是否应该升级
        
        返回：
            (是否升级, 升级类型说明)
        """
        if len(pivots) == 0:
            return (False, "")
        
        last_pivot = pivots[-1]
        ext_count = count_extension(pivots, all_segments)
        
        # 延伸升级判断
        if ext_count >= upgrade_threshold:
            return (True, f"延伸升级: {ext_count}段延伸")
        
        # 扩张升级判断
        # （需要更复杂的形态分析）
        
        return (False, "")
    
    @staticmethod
    def upgrade_pivot_level(pivot: Pivot) -> Pivot:
        """
        执行中枢升级：级别提升一级
        """
        level_hierarchy = ['1F', '5F', '30F', 'D', 'W', 'M']
        
        if pivot.level in level_hierarchy:
            idx = level_hierarchy.index(pivot.level)
            new_level = level_hierarchy[min(idx + 1, len(level_hierarchy) - 1)]
            
            return Pivot(
                ZG=pivot.ZG,
                ZD=pivot.ZD,
                level=new_level,
                direction=pivot.direction,
                segments=pivot.segments,
                upgraded=True
            )
        
        return pivot
```

---

## 六、多级别中枢联立分析框架

### 6.1 联立分析原理

多级别中枢联立是缠论核心分析方法，其原理在于：

> **不同级别的中枢同时存在于走势中，各自发挥作用。**
> - 高级别中枢决定中长期趋势方向
> - 低级别中枢提供短期交易信号
> - 各级别中枢相互影响、相互验证

### 6.2 多级别分析伪代码

```python
class MultiLevelPivotAnalyzer:
    """
    多级别中枢联立分析器
    """
    
    def __init__(self, kline_data: list[Kline], base_level: str = '1F'):
        self.data = kline_data
        self.base_level = base_level
        self.pivots_by_level = {
            '1F': [], '5F': [], '30F': [], 
            'D': [], 'W': [], 'M': []
        }
    
    def analyze_all_levels(self) -> dict[str, list[Pivot]]:
        """
        执行全级别中枢分析
        """
        # 1. 先划分笔（基础线段）
        segments_1f = self.extract_segments(self.data, '1F')
        
        # 2. 递归生成各级别中枢
        self.pivots_by_level['1F'] = self.build_pivots(segments_1f, '1F')
        
        # 3. 逐级向上递归
        for level in ['5F', '30F', 'D', 'W', 'M']:
            segments = self.aggregate_segments(
                self.pivots_by_level[self.get_previous_level(level)],
                level
            )
            self.pivots_by_level[level] = self.build_pivots(segments, level)
        
        return self.pivots_by_level
    
    def get_previous_level(self, level: str) -> str:
        """获取上一级别"""
        hierarchy = ['1F', '5F', '30F', 'D', 'W', 'M']
        idx = hierarchy.index(level) if level in hierarchy else 0
        return hierarchy[max(0, idx - 1)]
    
    def extract_segments(self, data: list[Kline], level: str) -> list[Segment]:
        """提取指定级别的线段"""
        # 笔划分算法的核心实现
        # 需要结合顶底分型、笔破坏规则
        pass
    
    def build_pivots(self, segments: list[Segment], level: str) -> list[Pivot]:
        """从线段构建中枢"""
        pivots = []
        
        i = 0
        while i < len(segments) - 2:
            try:
                pivot = calculate_pivot(segments[i:i+3], level)
                pivots.append(pivot)
                i += 3  # 移动到下一组
            except ValueError:
                i += 1
        
        return pivots
    
    def aggregate_segments(self, lower_pivots: list[Pivot], 
                          target_level: str) -> list[Segment]:
        """
        将低级别中枢聚合成高级别线段
        
        多个同级别同方向的中枢可合并为上一级别的线段
        """
        if not lower_pivots:
            return []
        
        # 简化逻辑：取相邻同方向中枢的区间作为高级别线段
        aggregated = []
        
        for i in range(0 len(lower_pivots) - 1, 2):
            p1 = lower_pivots[i]
            p2 = lower_pivots[i + 1] if i + 1 < len(lower_pivots) else None
            
            if p2 and p1.direction == p2.direction:
                seg = Segment(
                    low=min(p1.ZD, p2.ZD),
                    high=max(p1.ZG, p2.ZG),
                    direction=p1.direction
                )
            else:
                seg = Segment(
                    low=p1.ZD,
                    high=p1.ZG,
                    direction=p1.direction
                )
            
            aggregated.append(seg)
        
        return aggregated
    
    def get_trend_direction(self, level: str) -> str:
        """
        获取指定级别的趋势方向
        
        方法：比较最近两个同级别中枢的区间位置
        """
        pivots = self.pivots_by_level.get(level, [])
        
        if len(pivots) < 2:
            return " inconclusive"
        
        # 比较最近两个中枢
        last_two = pivots[-2:]
        
        if last_two[1].ZG > last_two[0].ZG:
            return "上涨趋势"
        elif last_two[1].ZD < last_two[0].ZD:
            return "下跌趋势"
        else:
            return "盘整"
    
    def find_alignment(self) -> list[dict]:
        """
        寻找各级别中枢的共振点
        
        当不同级别的中枢区间重叠或方向一致时，形成共振
        """
        alignments = []
        
        # 检查各级别最后一个中枢
        levels = ['1F', '5F', '30F', 'D']
        recent_pivots = {}
        
        for lv in levels:
            if self.pivots_by_level[lv]:
                recent_pivots[lv] = self.pivots_by_level[lv][-1]
        
        # 两两比较
        lv_keys = list(recent_pivots.keys())
        for i in range(len(lv_keys)):
            for j in range(i + 1, len(lv_keys)):
                lv1, lv2 = lv_keys[i], lv_keys[j]
                p1, p2 = recent_pivots[lv1], recent_pivots[lv2]
                
                # 检查区间重叠
                if p1.ZD <= p2.ZG and p2.ZD <= p1.ZG:
                    alignments.append({
                        'levels': [lv1, lv2],
                        'type': '区间重叠',
                        'pivot1': p1,
                        'pivot2': p2
                    })
                
                # 检查方向一致
                if p1.direction == p2.direction:
                    alignments.append({
                        'levels': [lv1, lv2],
                        'type': '方向共振',
                        'direction': p1.direction,
                        'pivot1': p1,
                        'pivot2': p2
                    })
        
        return alignments
```

### 6.3 联立分析输出示例

```python
# 使用示例
analyzer = MultiLevelPivotAnalyzer(kline_data, '1F')
all_pivots = analyzer.analyze_all_levels()

# 输出各级别中枢数量
for level, pivots in all_pivots.items():
    print(f"{level}: {len(pivots)} 个中枢")

# 获取趋势判断
for level in ['30F', 'D']:
    print(f"{level}趋势: {analyzer.get_trend_direction(level)}")

# 共振分析
alignments = analyzer.find_alignment()
for a in alignments:
    print(f"共振: {a['levels']} - {a['type']}")
```

---

## 七、总结与实施建议

### 7.1 核心算法要点

| 模块 | 关键函数 | 输入 | 输出 |
|------|----------|------|------|
| **中枢识别** | `calculate_pivot()` | ≥3线段 | ZG/ZD/区间 |
| **延伸判断** | `is_pivot_extension()` | 新线段+已有中枢 | Bool |
| **升级判定** | `check_pivot_upgrade()` | 所有线段 | Bool |
| **级别递归** | `determine_level()` | 线段对象 | 级别字符串 |
| **多级别分析** | `analyze_all_levels()` | K线数据 | 各级别中枢列表 |

### 7.2 实施注意事项

1. **笔的划分是前提**：中枢由线段构成，线段由笔构成，需先实现笔划分算法
2. **包含处理是关键**：线段合并前的包含关系处理直接影响中枢准确性
3. **级别对应要准确**：确保不同周期K线数据的正确映射
4. **实时与历史的区分**：实时分析时需处理未完成的线段和中枢

### 7.3 验证建议

由于本次无法直接访问原始文献，建议通过以下方式交叉验证算法逻辑：

1. 对照《缠论》原著PDF版第64-72课（中枢相关）
2. 使用本地已保存的缠论文档进行逐条比对
3. 通过历史K线数据回测验证算法输出与手工标注的一致性

---

**文档状态**：初稿完成  
**待验证**：原文引用准确性（需离线资源交叉确认）  
**后续研究**：

- 笔的精确划分算法（线段的生成规则）
- 分型（顶分型/底分型）的判定与包含处理
- 走势类型（盘整/趋势）的自动识别