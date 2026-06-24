#!/usr/bin/env python3
"""
缠论核心计算引擎 (Chanlun Technical Analysis Engine)

实现完整的缠论分析流水线：
K线包含处理 → 分型识别 → 笔的划分 → 线段划分 → 中枢识别 → 背驰检测 → 买卖点标注

依赖: pandas, numpy
输入: DataFrame(columns: date, open, high, low, close, volume)
输出: 结构化 JSON

算法参考:
  - 缠中说禅《教你炒股票》第62、65、67、77、78、81课
  - 调研报告 01-kline-inclusion ~ 06-buy-sell-points

Version: 1.0.0
Date: 2026-04-18
"""

from __future__ import annotations

import json
import sys
import os
import argparse
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Fractal:
    """分型（顶分型 / 底分型）"""
    index: int          # 在包含处理后K线序列中的位置
    ftype: str          # 'top' | 'bottom'
    value: float        # 顶=最高价, 底=最低价
    high: float         # 分型中间K线的最高价
    low: float          # 分型中间K线的最低价


@dataclass
class Pen:
    """笔"""
    start_idx: int      # 起点在处理后K线中的index
    end_idx: int        # 终点在处理后K线中的index
    direction: int      # 1=向上笔, -1=向下笔
    start_value: float  # 起点价格
    end_value: float    # 终点价格
    start_frac: Fractal = field(repr=False, default=None)
    end_frac: Fractal = field(repr=False, default=None)
    orig_start: int = -1   # 笔起点对应的原始DataFrame行号
    orig_end: int = -1     # 笔终点对应的原始DataFrame行号


@dataclass
class Segment:
    """线段"""
    start_idx: int      # 起点笔序号
    end_idx: int        # 终点笔序号
    direction: int      # 1=向上线段, -1=向下线段
    high: float
    low: float


@dataclass
class Pivot:
    """中枢"""
    start_seg_idx: int  # 起始线段序号
    end_seg_idx: int    # 结束线段序号
    ZG: float           # 中枢上沿 = min(各线段高点)
    ZD: float           # 中枢下沿 = max(各线段低点)
    GG: float           # 中枢最高点
    DD: float           # 中枢最低点
    seg_count: int      # 组成中枢的线段数


@dataclass
class DivergenceInfo:
    """背驰信息"""
    pivot_idx: int          # 关联中枢序号
    direction: int          # 1=顶背驰(涨势衰竭), -1=底背驰(跌势衰竭)
    area_a: float           # A段MACD面积
    area_c: float           # C段MACD面积
    ratio: float            # area_c / area_a
    strength: str           # 'STRONG' | 'NORMAL' | 'WEAK'
    price_a_end: float      # A段末端价格
    price_c_end: float      # C段末端价格


@dataclass
class BuySellPoint:
    """买卖点"""
    point_type: int     # 1, 2, 3
    side: str           # 'buy' | 'sell'
    price: float        # 价格
    idx: int            # 在原始DataFrame中的行号
    confidence: float   # 置信度 [0, 1]
    pivot_ref: int      # 关联中枢序号 (-1 = 无)


# ═══════════════════════════════════════════════════════════════════════
# 1. K线包含处理
# ═══════════════════════════════════════════════════════════════════════

def _is_inclusive(h1: float, l1: float, h2: float, l2: float) -> bool:
    """判断两根K线是否存在包含关系。"""
    return (h1 >= h2 and l1 <= l2) or (h1 <= h2 and l1 >= l2)


def process_inclusion(df: pd.DataFrame) -> pd.DataFrame:
    """
    K线包含关系处理。

    根据缠论第62、65课：
    - 向上方向取高高原则 (max high, max low)
    - 向下方向取低低原则 (min high, min low)
    - 方向由左侧非包含K线的相对高低决定
    - 从左到右逐根处理，合并后继续与后续比较

    Parameters
    ----------
    df : DataFrame
        columns: date, open, high, low, close, volume

    Returns
    -------
    DataFrame
        包含处理后的K线，新增列:
        - _orig_start: 该合并K线对应的原始起始行号
        - _orig_end:   该合并K线对应的原始结束行号
    """
    if len(df) <= 1:
        out = df.copy()
        out["_orig_start"] = out.index
        out["_orig_end"] = out.index
        return out

    rows = df.to_dict("records")
    n = len(rows)

    # 用列表存放处理后的K线，每项:
    # (date, open, high, low, close, volume, orig_start, orig_end)
    result: list[tuple] = []

    # 先放入第一根
    r0 = rows[0]
    result.append((
        r0["date"], r0["open"], r0["high"], r0["low"],
        r0["close"], r0["volume"], 0, 0
    ))

    for i in range(1, n):
        ri = rows[i]
        prev = result[-1]

        h_prev, l_prev = prev[2], prev[3]
        h_curr, l_curr = ri["high"], ri["low"]

        if _is_inclusive(h_prev, l_prev, h_curr, l_curr):
            # 确定方向：向前找非包含K线
            direction = _determine_direction(result, len(result) - 1)

            if direction == 1:  # 向上: 高高原则
                new_h = max(h_prev, h_curr)
                new_l = max(l_prev, l_curr)
            else:  # 向下: 低低原则
                new_h = min(h_prev, h_curr)
                new_l = min(l_prev, l_curr)

            # 合并：保留第一根的date/open, 最后一根的close, 累加volume
            new_close = ri["close"]
            new_vol = prev[5] + ri["volume"]
            orig_start = prev[6]
            orig_end = i

            result[-1] = (
                prev[0], prev[1], new_h, new_l,
                new_close, new_vol, orig_start, orig_end
            )
        else:
            result.append((
                ri["date"], ri["open"], ri["high"], ri["low"],
                ri["close"], ri["volume"], i, i
            ))

    # 转回 DataFrame
    cols = ["date", "open", "high", "low", "close", "volume",
            "_orig_start", "_orig_end"]
    out_df = pd.DataFrame(result, columns=cols)
    return out_df


def _determine_direction(result: list[tuple], idx: int) -> int:
    """
    确定当前K线处理方向。

    Parameters
    ----------
    result : 已处理的K线列表
    idx : 当前K线在result中的位置

    Returns
    -------
    1=向上, -1=向下
    """
    if idx == 0:
        return 1  # 默认向上
    # 与前一根非包含K线比较
    for j in range(idx - 1, -1, -1):
        h_j, l_j = result[j][2], result[j][3]
        h_curr, l_curr = result[idx][2], result[idx][3]
        if not _is_inclusive(h_j, l_j, h_curr, l_curr):
            return 1 if h_curr > h_j else -1
    # 全部包含，默认向上
    return 1


# ═══════════════════════════════════════════════════════════════════════
# 2. 分型识别
# ═══════════════════════════════════════════════════════════════════════

def find_fractals(df_included: pd.DataFrame) -> list[Fractal]:
    """
    在包含处理后的K线序列中识别顶分型和底分型。

    顶分型: 中间K线的高点和低点均为三者最高。
    底分型: 中间K线的高点和低点均为三者最低。

    Parameters
    ----------
    df_included : 包含处理后的DataFrame

    Returns
    -------
    list[Fractal]
    """
    fractals: list[Fractal] = []
    n = len(df_included)
    if n < 3:
        return fractals

    highs = df_included["high"].values
    lows = df_included["low"].values

    for i in range(1, n - 1):
        h1, h2, h3 = highs[i - 1], highs[i], highs[i + 1]
        l1, l2, l3 = lows[i - 1], lows[i], lows[i + 1]

        if h2 > h1 and h2 > h3 and l2 > l1 and l2 > l3:
            fractals.append(Fractal(index=i, ftype="top",
                                    value=h2, high=h2, low=l2))
        elif l2 < l1 and l2 < l3 and h2 < h1 and h2 < h3:
            fractals.append(Fractal(index=i, ftype="bottom",
                                    value=l2, high=h2, low=l2))

    return fractals


# ═══════════════════════════════════════════════════════════════════════
# 3. 笔的划分
# ═══════════════════════════════════════════════════════════════════════

def _filter_same_type_fractals(fractals: list[Fractal]) -> list[Fractal]:
    """
    处理同性质分型 (第77课步骤二)。

    - 连续两个顶: 保留值更高的
    - 连续两个底: 保留值更低的
    """
    if not fractals:
        return []
    filtered = [fractals[0]]
    for f in fractals[1:]:
        prev = filtered[-1]
        if f.ftype == prev.ftype:
            if f.ftype == "top" and f.value > prev.value:
                filtered[-1] = f
            elif f.ftype == "bottom" and f.value < prev.value:
                filtered[-1] = f
            else:
                # 保留prev（已经更极端），跳过f
                pass
        else:
            filtered.append(f)
    return filtered


def build_pens(df_included: pd.DataFrame,
               fractals: list[Fractal] | None = None,
               mode: str = "new") -> list[Pen]:
    """
    从分型构造笔。

    笔的规则 (第62、65、77、81课):
    - 顶底分型交替出现
    - 不共用K线
    - 旧笔: 包含处理后至少1根独立K线
    - 新笔: 原始K线中至少3根独立K线（不考虑包含关系）
    - 空间约束: 顶的最高价 > 底的最低价

    Parameters
    ----------
    df_included : 包含处理后的DataFrame
    fractals : 分型列表 (None则自动识别)
    mode : 'new' (新笔) | 'old' (旧笔)

    Returns
    -------
    list[Pen]
    """
    if fractals is None:
        fractals = find_fractals(df_included)
    if len(fractals) < 2:
        return []

    fractals = _filter_same_type_fractals(fractals)

    # 构造笔: 相邻异性质分型, 满足成笔条件
    pens: list[Pen] = []
    i = 0

    while i < len(fractals):
        curr = fractals[i]
        # 向后找第一个异性质分型
        j = i + 1
        while j < len(fractals):
            nxt = fractals[j]
            if curr.ftype == nxt.ftype:
                j += 1
                continue

            # 检查不共用K线 (处理后index差>=2)
            if nxt.index - curr.index < 2:
                j += 1
                continue

            # 检查独立K线条件
            if mode == "old":
                # 旧笔: 处理后至少1根独立K线 → index差 >= 3
                if nxt.index - curr.index < 3:
                    j += 1
                    continue
            else:
                # 新笔: 原始K线中至少3根
                orig_start_curr = int(df_included.iloc[curr.index]["_orig_start"])
                orig_end_curr = int(df_included.iloc[curr.index]["_orig_end"])
                orig_start_nxt = int(df_included.iloc[nxt.index]["_orig_start"])
                orig_end_nxt = int(df_included.iloc[nxt.index]["_orig_end"])

                # 不含两端K线之间的原始K线数
                between = orig_start_nxt - orig_end_curr - 1
                # 分型中间K线的原始范围
                # 新笔要求: 顶分型最高K线与底分型最低K线之间(不含), 至少3根原始K线
                if between < 3:
                    j += 1
                    continue

            # 空间约束: 顶>底
            if curr.ftype == "top":
                top, bottom = curr, nxt
            else:
                top, bottom = nxt, curr
            if top.value <= bottom.value:
                j += 1
                continue

            # 成笔
            orig_s = int(df_included.iloc[curr.index]["_orig_start"])
            orig_e = int(df_included.iloc[nxt.index]["_orig_end"])
            if curr.ftype == "bottom":
                direction = 1  # 向上笔
                pens.append(Pen(
                    start_idx=curr.index, end_idx=nxt.index,
                    direction=direction,
                    start_value=curr.value, end_value=nxt.value,
                    start_frac=curr, end_frac=nxt,
                    orig_start=orig_s, orig_end=orig_e
                ))
            else:
                direction = -1  # 向下笔
                pens.append(Pen(
                    start_idx=curr.index, end_idx=nxt.index,
                    direction=direction,
                    start_value=curr.value, end_value=nxt.value,
                    start_frac=curr, end_frac=nxt,
                    orig_start=orig_s, orig_end=orig_e
                ))
            i = j
            break
        else:
            # 未找到配对
            break

    return pens


# ═══════════════════════════════════════════════════════════════════════
# 4. 线段划分
# ═══════════════════════════════════════════════════════════════════════

def _pen_to_element(pen: Pen) -> tuple[float, float]:
    """将笔转为特征序列元素 (high, low)。"""
    if pen.direction == 1:
        return (pen.end_value, pen.start_value)
    else:
        return (pen.start_value, pen.end_value)


def _elements_overlap(h1: float, l1: float, h2: float, l2: float) -> bool:
    """判断两个区间是否有重叠。"""
    return not (l1 > h2 or l2 > h1)


def _feature_sequence_fractal_check(seq: list[tuple[float, float]]) -> Optional[int]:
    """
    检查特征序列最后三个元素是否形成分型。

    Returns
    -------
    1 = 顶分型, -1 = 底分型, None = 无分型
    """
    if len(seq) < 3:
        return None
    a, b, c = seq[-3], seq[-2], seq[-1]
    # 顶分型: 中间最高
    if b[0] > a[0] and b[0] > c[0] and b[1] > a[1] and b[1] > c[1]:
        return 1
    # 底分型: 中间最低
    if b[1] < a[1] and b[1] < c[1] and b[0] < a[0] and b[0] < c[0]:
        return -1
    return None


def _merge_feature_inclusion(seq: list[tuple[float, float]],
                             direction: int) -> list[tuple[float, float]]:
    """
    特征序列包含处理。

    Parameters
    ----------
    seq : 特征序列 [(high, low), ...]
    direction : 1=向上线段, -1=向下线段

    Returns
    -------
    合并后的特征序列
    """
    if len(seq) <= 1:
        return list(seq)
    result = [seq[0]]
    for i in range(1, len(seq)):
        prev = result[-1]
        curr = seq[i]
        h_prev, l_prev = prev
        h_curr, l_curr = curr

        if _is_inclusive(h_prev, l_prev, h_curr, l_curr):
            if direction == 1:  # 向上线段: 取高
                merged = (max(h_prev, h_curr), max(l_prev, l_curr))
            else:  # 向下线段: 取低
                merged = (min(h_prev, h_curr), min(l_prev, l_curr))
            result[-1] = merged
        else:
            result.append(curr)
    return result


def build_segments(pens: list[Pen],
                   df_included: pd.DataFrame) -> list[Segment]:
    """
    从笔序列划分线段。

    基于缠论第67、71、78课的线段划分标准:
    - 特征序列提取与包含处理
    - 第一种情况: 无缺口 → 特征序列分型即确认
    - 第二种情况: 有缺口 → 需第二特征序列出现分型确认
    - 至少3笔重叠构成线段

    Parameters
    ----------
    pens : 笔列表
    df_included : 包含处理后的K线 (用于获取价格)

    Returns
    -------
    list[Segment]
    """
    if len(pens) < 3:
        return []

    segments: list[Segment] = []
    n = len(pens)

    seg_start = 0  # 当前线段起始笔序号

    i = 3  # 从第4笔开始检查(前3笔至少构成候选)
    while i <= n:
        # 当前线段方向 = 第一笔的方向
        seg_dir = pens[seg_start].direction

        # 提取特征序列 (与线段方向相反的笔)
        feature_seq: list[tuple[float, float]] = []
        for k in range(seg_start, i):
            if pens[k].direction != seg_dir:
                feature_seq.append(_pen_to_element(pens[k]))

        if len(feature_seq) < 3:
            i += 1
            continue

        # 包含处理
        std_seq = _merge_feature_inclusion(feature_seq, seg_dir)

        # 检查特征序列分型
        fractal_type = _feature_sequence_fractal_check(std_seq)

        if fractal_type is not None:
            # 检查第一种/第二种情况
            if len(std_seq) >= 3:
                has_gap = not _elements_overlap(
                    std_seq[-3][0], std_seq[-3][1],
                    std_seq[-2][0], std_seq[-2][1]
                )
            else:
                has_gap = False

            if not has_gap:
                # 第一种情况: 无缺口 → 直接确认线段破坏
                # 线段终点 = 特征序列分型对应位置
                seg_end = i - 2  # 倒数第二笔 (分型中间笔)

                # 计算线段的高低
                seg_high = max(
                    p.end_value if p.direction == 1 else p.start_value
                    for p in pens[seg_start:seg_end + 1]
                )
                seg_low = min(
                    p.start_value if p.direction == 1 else p.end_value
                    for p in pens[seg_start:seg_end + 1]
                )

                segments.append(Segment(
                    start_idx=seg_start, end_idx=seg_end,
                    direction=seg_dir, high=seg_high, low=seg_low
                ))
                seg_start = seg_end + 1
                i = seg_start + 3
                continue
            else:
                # 第二种情况: 有缺口 → 需额外确认
                # 简化处理: 有缺口的分型也确认 (严格版需考察第二特征序列)
                # 此处采用"特征序列出现分型即确认"的实用策略
                seg_end = i - 2

                seg_high = max(
                    p.end_value if p.direction == 1 else p.start_value
                    for p in pens[seg_start:seg_end + 1]
                )
                seg_low = min(
                    p.start_value if p.direction == 1 else p.end_value
                    for p in pens[seg_start:seg_end + 1]
                )

                segments.append(Segment(
                    start_idx=seg_start, end_idx=seg_end,
                    direction=seg_dir, high=seg_high, low=seg_low
                ))
                seg_start = seg_end + 1
                i = seg_start + 3
                continue

        i += 1

    # 处理剩余的笔 (未完成线段)
    if seg_start < n:
        remaining_dir = pens[seg_start].direction
        seg_high = max(
            p.end_value if p.direction == 1 else p.start_value
            for p in pens[seg_start:]
        )
        seg_low = min(
            p.start_value if p.direction == 1 else p.end_value
            for p in pens[seg_start:]
        )
        segments.append(Segment(
            start_idx=seg_start, end_idx=n - 1,
            direction=remaining_dir, high=seg_high, low=seg_low
        ))

    return segments


# ═══════════════════════════════════════════════════════════════════════
# 5. 中枢识别
# ═══════════════════════════════════════════════════════════════════════

def find_pivots(segments: list[Segment]) -> list[Pivot]:
    """
    从线段序列中识别中枢。

    中枢定义: 至少三个连续线段的重叠区间。
    - ZG = min(前三段高点)
    - ZD = max(前三段低点)
    - 后续线段若与中枢区间有重叠 → 中枢延伸

    Parameters
    ----------
    segments : 线段列表

    Returns
    -------
    list[Pivot]
    """
    if len(segments) < 3:
        return []

    pivots: list[Pivot] = []
    i = 0

    while i <= len(segments) - 3:
        s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]

        # 三段重叠: 取前三段
        high_min = min(s1.high, s2.high, s3.high)
        low_max = max(s1.low, s2.low, s3.low)

        if high_min > low_max:
            # 有效中枢
            zg = high_min
            zd = low_max
            gg = max(s1.high, s2.high, s3.high)
            dd = min(s1.low, s2.low, s3.low)
            seg_count = 3
            end_seg = i + 2

            # 检查延伸
            j = i + 3
            while j < len(segments):
                seg = segments[j]
                if seg.high > zd and seg.low < zg:
                    # 延伸
                    seg_count += 1
                    gg = max(gg, seg.high)
                    dd = min(dd, seg.low)
                    end_seg = j
                    j += 1
                else:
                    break

            pivots.append(Pivot(
                start_seg_idx=i, end_seg_idx=end_seg,
                ZG=zg, ZD=zd, GG=gg, DD=dd,
                seg_count=seg_count
            ))
            i = end_seg + 1
        else:
            i += 1

    return pivots


# ═══════════════════════════════════════════════════════════════════════
# 6. MACD 计算
# ═══════════════════════════════════════════════════════════════════════

def _calc_ema(series: np.ndarray, period: int) -> np.ndarray:
    """计算 EMA。"""
    alpha = 2.0 / (period + 1)
    result = np.empty_like(series)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = alpha * series[i] + (1 - alpha) * result[i - 1]
    return result


def calc_macd(close: np.ndarray,
              fast: int = 12, slow: int = 26, signal: int = 9
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    计算标准 MACD。

    Returns
    -------
    (DIF, DEA, histogram)  histogram = 2 * (DIF - DEA)
    """
    ema_fast = _calc_ema(close, fast)
    ema_slow = _calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = _calc_ema(dif, signal)
    hist = 2.0 * (dif - dea)
    return dif, dea, hist


def _macd_area(hist: np.ndarray, start: int, end: int,
               direction: int) -> float:
    """
    计算指定区间MACD柱子面积。

    direction=1: 累加正值(红柱)
    direction=-1: 累加负值的绝对值(绿柱)
    """
    area = 0.0
    for i in range(start, end + 1):
        if i < 0 or i >= len(hist):
            continue
        v = hist[i]
        if direction == 1 and v > 0:
            area += v
        elif direction == -1 and v < 0:
            area += abs(v)
    return area


# ═══════════════════════════════════════════════════════════════════════
# 7. 背驰检测
# ═══════════════════════════════════════════════════════════════════════

def detect_divergence(pivots: list[Pivot],
                      df: pd.DataFrame,
                      segments: list[Segment],
                      pens: list[Pen]) -> list[DivergenceInfo]:
    """
    检测趋势背驰。

    基于第24、25、27课:
    - 至少两个同方向中枢构成趋势
    - A段 = 进入最后中枢前的走势段
    - C段 = 离开最后中枢的走势段
    - C段MACD面积 < A段MACD面积 → 背驰
    - 价格创新高/低但指标未同步 → 确认

    Parameters
    ----------
    pivots : 中枢列表
    df : 原始DataFrame
    segments : 线段列表
    pens : 笔列表 (用于精确映射线段到原始行号)

    Returns
    -------
    list[DivergenceInfo]
    """
    results: list[DivergenceInfo] = []

    if len(pivots) < 2:
        return results

    close = df["close"].values.astype(float)
    _, _, hist = calc_macd(close)

    # 逐对相邻中枢检查
    for pi in range(1, len(pivots)):
        p_prev = pivots[pi - 1]
        p_curr = pivots[pi]

        # 判断趋势方向
        if p_curr.ZG > p_prev.ZG:
            trend_dir = 1  # 上涨趋势
        elif p_curr.ZD < p_prev.ZD:
            trend_dir = -1  # 下跌趋势
        else:
            continue  # 盘整, 跳过

        # A段: p_prev 中枢到 p_curr 中枢之间的走势
        a_start_seg = p_prev.end_seg_idx
        a_end_seg = p_curr.start_seg_idx - 1

        # C段: p_curr 中枢之后的走势
        c_start_seg = p_curr.end_seg_idx + 1
        c_end_seg = min(c_start_seg + (a_end_seg - a_start_seg) + 1,
                        len(segments) - 1)

        if c_start_seg >= len(segments):
            continue

        # 映射到原始行号 (使用笔的orig_start/orig_end精确定位)
        def _get_orig_range(seg_idx: int) -> tuple[int, int]:
            """获取线段对应的原始DataFrame行号范围"""
            if seg_idx < 0 or seg_idx >= len(segments):
                return 0, len(df) - 1
            s = segments[seg_idx]
            # 找到属于该线段的所有笔
            pens_in_seg = [p for p in pens
                           if s.start_idx <= pens.index(p) <= s.end_idx]
            if not pens_in_seg:
                return 0, len(df) - 1
            return pens_in_seg[0].orig_start, pens_in_seg[-1].orig_end

        def _seg_to_row(seg_idx: int) -> int:
            _, orig_end = _get_orig_range(seg_idx)
            return min(orig_end, len(df) - 1)

        a_row_start = _seg_to_row(a_start_seg)
        a_row_end = _seg_to_row(a_end_seg)
        c_row_start = _seg_to_row(c_start_seg)
        c_row_end = _seg_to_row(c_end_seg)

        # 价格创新极值检查
        if trend_dir == 1:
            price_a_end = close[min(a_row_end, len(close) - 1)]
            price_c_end = close[min(c_row_end, len(close) - 1)]
            if price_c_end <= price_a_end:
                continue  # 未创新高, 非标准背驰
        else:
            price_a_end = close[min(a_row_end, len(close) - 1)]
            price_c_end = close[min(c_row_end, len(close) - 1)]
            if price_c_end >= price_a_end:
                continue  # 未创新低

        # MACD面积比较
        area_a = _macd_area(hist, a_row_start, a_row_end, trend_dir)
        area_c = _macd_area(hist, c_row_start, c_row_end, trend_dir)

        if area_a <= 0:
            continue

        ratio = area_c / area_a

        if ratio < 1.0:
            # 背驰!
            if ratio < 0.5:
                strength = "STRONG"
            elif ratio < 0.75:
                strength = "NORMAL"
            else:
                strength = "WEAK"

            # direction: 1=顶背驰(涨势衰竭), -1=底背驰(跌势衰竭)
            div_dir = -trend_dir

            results.append(DivergenceInfo(
                pivot_idx=pi,
                direction=div_dir,
                area_a=area_a,
                area_c=area_c,
                ratio=round(ratio, 4),
                strength=strength,
                price_a_end=round(float(price_a_end), 4),
                price_c_end=round(float(price_c_end), 4)
            ))

    return results


# ═══════════════════════════════════════════════════════════════════════
# 8. 买卖点标注
# ═══════════════════════════════════════════════════════════════════════

def find_buy_sell_points(
    pivots: list[Pivot],
    divergence: list[DivergenceInfo],
    df: pd.DataFrame,
    segments: list[Segment],
    pens: list[Pen]
) -> list[BuySellPoint]:
    """
    标注三类买卖点。

    第一类买卖点: 趋势背驰转折点
    第二类买卖点: 第一类买卖点后的次级别回调低点/高点
    第三类买卖点: 次级别离开中枢后回抽不破ZG/ZD

    Parameters
    ----------
    pivots : 中枢列表
    divergence : 背驰信息列表
    df : 原始DataFrame
    segments : 线段列表
    pens : 笔列表

    Returns
    -------
    list[BuySellPoint]
    """
    results: list[BuySellPoint] = []
    n = len(df)

    def _seg_orig_row(seg_idx: int) -> int:
        """用笔的orig_end精确映射线段到原始DataFrame行号"""
        if seg_idx < 0 or seg_idx >= len(segments):
            return n - 1
        s = segments[seg_idx]
        pens_in_seg = [p for p in pens
                       if s.start_idx <= pens.index(p) <= s.end_idx]
        if not pens_in_seg:
            return n - 1
        return min(pens_in_seg[-1].orig_end, n - 1)

    # ── 第一类买卖点 (基于背驰) ──
    for div in divergence:
        if div.direction == 1:
            # 底背驰 → 第一类买点
            # 定位: C段末尾 (价格最低处附近)
            p = pivots[div.pivot_idx]
            # 在中枢结束后的线段范围中找最低价
            search_start = _seg_orig_row(p.end_seg_idx)
            search_end = min(search_start + max(20, len(df) // 10), n - 1)
            lows = df["low"].values[search_start:search_end + 1]
            if len(lows) == 0:
                continue
            min_idx = search_start + int(np.argmin(lows))

            results.append(BuySellPoint(
                point_type=1, side="buy",
                price=round(float(df.iloc[min_idx]["low"]), 4),
                idx=int(df.index[min_idx]) if min_idx < len(df) else 0,
                confidence=_div_confidence(div.ratio),
                pivot_ref=div.pivot_idx
            ))

        elif div.direction == -1:
            # 顶背驰 → 第一类卖点
            p = pivots[div.pivot_idx]
            search_start = _seg_orig_row(p.end_seg_idx)
            search_end = min(search_start + max(20, len(df) // 10), n - 1)
            highs = df["high"].values[search_start:search_end + 1]
            if len(highs) == 0:
                continue
            max_idx = search_start + int(np.argmax(highs))

            results.append(BuySellPoint(
                point_type=1, side="sell",
                price=round(float(df.iloc[max_idx]["high"]), 4),
                idx=int(df.index[max_idx]) if max_idx < len(df) else 0,
                confidence=_div_confidence(div.ratio),
                pivot_ref=div.pivot_idx
            ))

    # ── 第三类买卖点 (基于中枢破坏) ──
    for pi, p in enumerate(pivots):
        # 在中枢之后寻找离开+回抽
        # 简化: 检查中枢后是否有线段向上离开且回抽不破ZG
        after_seg_start = p.end_seg_idx + 1
        if after_seg_start >= len(segments):
            continue

        for si in range(after_seg_start, len(segments)):
            seg = segments[si]

            # 第三类买点: 向上线段离开中枢后, 后续向下线段低点 >= ZG
            if seg.direction == 1 and seg.low > p.ZD:
                # 检查下一个线段(回抽)
                if si + 1 < len(segments):
                    pullback = segments[si + 1]
                    if pullback.direction == -1 and pullback.low >= p.ZG:
                        row_idx = _seg_orig_row(si + 1)
                        if row_idx < n:
                            results.append(BuySellPoint(
                                point_type=3, side="buy",
                                price=round(
                                    float(df.iloc[row_idx]["low"]), 4),
                                idx=int(df.index[row_idx]),
                                confidence=0.85,
                                pivot_ref=pi
                            ))
                        break  # 一个中枢最多产生一个第三类买点

            # 第三类卖点: 向下线段离开中枢后, 后续向上线段高点 <= ZD
            if seg.direction == -1 and seg.high < p.ZG:
                if si + 1 < len(segments):
                    pullback = segments[si + 1]
                    if pullback.direction == 1 and pullback.high <= p.ZD:
                        row_idx = _seg_orig_row(si + 1)
                        if row_idx < n:
                            results.append(BuySellPoint(
                                point_type=3, side="sell",
                                price=round(
                                    float(df.iloc[row_idx]["high"]), 4),
                                idx=int(df.index[row_idx]),
                                confidence=0.85,
                                pivot_ref=pi
                            ))
                        break

    # ── 第二类买卖点 (基于第一类买卖点) ──
    type1_buys = [r for r in results if r.point_type == 1 and r.side == "buy"]
    for b1 in type1_buys:
        # Buy1 后找第一段次级别向上 + 向下回调
        b1_idx = b1.idx
        # 在原始DataFrame中, 向后搜索回调低点
        search_end = min(b1_idx + max(30, len(df) // 8), n - 1)
        if b1_idx + 2 >= search_end:
            continue

        # 找第一波反弹高点
        window = df.iloc[b1_idx + 1:search_end + 1]
        if len(window) < 2:
            continue
        high_idx_rel = int(window["high"].values.argmax())
        high_price = float(window["high"].values[high_idx_rel])
        high_row = b1_idx + 1 + high_idx_rel

        # 在高点之后找回调低点
        if high_row + 1 < n:
            end_search = min(high_row + max(20, len(df) // 10), n - 1)
            pullback_window = df.iloc[high_row + 1:end_search + 1]
            if len(pullback_window) > 0:
                low_idx_rel = int(pullback_window["low"].values.argmin())
                low_price = float(pullback_window["low"].values[low_idx_rel])
                low_row = high_row + 1 + low_idx_rel

                # 验证: 回调低点 > Buy1 价格 (不破前低)
                if low_price > b1.price:
                    results.append(BuySellPoint(
                        point_type=2, side="buy",
                        price=round(low_price, 4),
                        idx=int(df.index[low_row]),
                        confidence=0.75,
                        pivot_ref=b1.pivot_ref
                    ))

    # 第二类卖点 (镜像)
    type1_sells = [r for r in results
                   if r.point_type == 1 and r.side == "sell"]
    for s1 in type1_sells:
        s1_idx = s1.idx
        search_end = min(s1_idx + max(30, len(df) // 8), n - 1)
        if s1_idx + 2 >= search_end:
            continue

        window = df.iloc[s1_idx + 1:search_end + 1]
        if len(window) < 2:
            continue
        low_idx_rel = int(window["low"].values.argmin())
        low_price = float(window["low"].values[low_idx_rel])
        low_row = s1_idx + 1 + low_idx_rel

        if low_row + 1 < n:
            end_search = min(low_row + max(20, len(df) // 10), n - 1)
            pullback_window = df.iloc[low_row + 1:end_search + 1]
            if len(pullback_window) > 0:
                high_idx_rel = int(
                    pullback_window["high"].values.argmax())
                high_price = float(
                    pullback_window["high"].values[high_idx_rel])
                high_row = low_row + 1 + high_idx_rel

                if high_price < s1.price:
                    results.append(BuySellPoint(
                        point_type=2, side="sell",
                        price=round(high_price, 4),
                        idx=int(df.index[high_row]),
                        confidence=0.75,
                        pivot_ref=s1.pivot_ref
                    ))

    # 按位置排序
    results.sort(key=lambda x: x.idx)
    return results


def _seg_to_row_approx(seg_idx: int, segments: list[Segment],
                       n_rows: int) -> int:
    """将线段序号近似映射到 DataFrame 行号。"""
    if not segments:
        return n_rows - 1
    seg = segments[min(seg_idx, len(segments) - 1)]
    # 用笔的index范围近似
    pen_range = seg.end_idx - seg.start_idx + 1
    total_pen_range = segments[-1].end_idx - segments[0].start_idx + 1
    if total_pen_range <= 0:
        return n_rows - 1
    ratio = pen_range / total_pen_range
    return min(int(ratio * n_rows), n_rows - 1)


def _div_confidence(ratio: float) -> float:
    """根据MACD面积比率计算置信度。"""
    if ratio < 0.3:
        return 0.95
    elif ratio < 0.5:
        return 0.90
    elif ratio < 0.7:
        return 0.80
    elif ratio < 0.9:
        return 0.70
    else:
        return 0.60


# ═══════════════════════════════════════════════════════════════════════
# 分析主流水线
# ═══════════════════════════════════════════════════════════════════════

def analyze(df: pd.DataFrame, pen_mode: str = "new") -> dict:
    """
    执行完整的缠论分析流水线。

    Parameters
    ----------
    df : DataFrame
        columns: date, open, high, low, close, volume
    pen_mode : str
        'new' (新笔, 默认) | 'old' (旧笔)

    Returns
    -------
    dict
        包含所有分析结果的结构化字典:
        - summary: 各步骤计数
        - fractals: 分型列表
        - pens: 笔列表
        - segments: 线段列表
        - pivots: 中枢列表
        - divergence: 背驰信息
        - buy_sell_points: 买卖点
        - compute_status: 流水线状态 + 数据质量
    """
    # ── Initialize compute_status tracking ──
    pipeline_warnings: list[str] = []
    klines_count = len(df)

    if klines_count < 30:
        pipeline_warnings.append("insufficient_klines")
    elif klines_count < 100:
        pipeline_warnings.append("limited_klines")

    # Step 1: 包含处理
    df_inc = process_inclusion(df)
    if klines_count > 0 and (klines_count - len(df_inc)) / klines_count > 0.5:
        pipeline_warnings.append("high_inclusion_ratio")

    # Step 2: 分型识别
    fractals = find_fractals(df_inc)
    if len(fractals) < 3:
        pipeline_warnings.append("too_few_fractals")

    # Step 3: 笔的划分
    pens = build_pens(df_inc, fractals, mode=pen_mode)
    if len(pens) < 3:
        pipeline_warnings.append("too_few_pens")

    # Step 4: 线段划分
    segments = build_segments(pens, df_inc)

    # Step 5: 中枢识别
    pivots = find_pivots(segments)
    if len(pivots) == 0 and len(pens) >= 3:
        pipeline_warnings.append("no_pivots_found")

    # Step 6: 背驰检测
    divergence = detect_divergence(pivots, df, segments, pens)

    # Step 7: 买卖点标注
    buy_sell = find_buy_sell_points(pivots, divergence, df, segments, pens)

    # Engine always treats the last segment as potentially unconfirmed
    # (known simplification — see compute/SKILL.md)
    if segments:
        pipeline_warnings.append("last_segment_unconfirmed")

    # Determine data quality
    sufficient = klines_count >= 30 and "too_few_pens" not in pipeline_warnings

    compute_status = {
        "pipeline_version": "2.0",
        "inclusion_done": True,
        "fractals_done": True,
        "strokes_done": True,
        "segments_done": True,
        "centers_done": True,
        "divergence_done": True,
        "buy_sell_points_done": True,
        "warnings": pipeline_warnings,
        "data_quality": {
            "klines_count": klines_count,
            "after_inclusion_count": len(df_inc),
            "missing_sessions": 0,
            "sufficient": sufficient,
        },
    }

    # RUO-384: pen_to_segment_ratio in data_quality
    compute_status["data_quality"]["pen_to_segment_ratio"] = (
        round(len(pens) / len(segments), 1) if segments else None
    )

    # RUO-384: current_state in compute_status
    if pivots:
        latest_pv = pivots[-1]
        current_price = float(df["close"].iloc[-1])
        if current_price > latest_pv.ZG:
            _pos = "above_ZG"
        elif current_price < latest_pv.ZD:
            _pos = "below_ZD"
        else:
            _pos = "inside_center"
        compute_status["current_state"] = {
            "price": round(current_price, 2),
            "position_vs_pivot": _pos,
            "nearest_ZG": round(float(latest_pv.ZG), 2),
            "nearest_ZD": round(float(latest_pv.ZD), 2),
            "last_segment_direction": (
                segments[-1].direction if segments else None
            ),
        }
    else:
        compute_status["current_state"] = None

    return {
        "summary": {
            "total_klines": len(df),
            "after_inclusion": len(df_inc),
            "merged_count": len(df) - len(df_inc),
            "fractal_count": len(fractals),
            "pen_count": len(pens),
            "segment_count": len(segments),
            "pivot_count": len(pivots),
            "divergence_count": len(divergence),
            "buy_sell_point_count": len(buy_sell),
        },
        "fractals": [
            {
                "index": int(f.index),
                "type": f.ftype,
                "value": round(float(f.value), 4),
                "high": round(float(f.high), 4),
                "low": round(float(f.low), 4),
            }
            for f in fractals
        ],
        "pens": [
            {
                "start_idx": int(p.start_idx),
                "end_idx": int(p.end_idx),
                "direction": "up" if p.direction == 1 else "down",
                "start_value": round(float(p.start_value), 4),
                "end_value": round(float(p.end_value), 4),
            }
            for p in pens
        ],
        "segments": [
            {
                "start_idx": int(s.start_idx),
                "end_idx": int(s.end_idx),
                "direction": "up" if s.direction == 1 else "down",
                "high": round(float(s.high), 4),
                "low": round(float(s.low), 4),
            }
            for s in segments
        ],
        "pivots": [
            {
                "start_seg": int(pv.start_seg_idx),
                "end_seg": int(pv.end_seg_idx),
                "ZG": round(float(pv.ZG), 4),
                "ZD": round(float(pv.ZD), 4),
                "GG": round(float(pv.GG), 4),
                "DD": round(float(pv.DD), 4),
                "seg_count": int(pv.seg_count),
            }
            for pv in pivots
        ],
        "divergence": [
            {
                "pivot_idx": int(d.pivot_idx),
                "direction": "top_divergence" if d.direction == -1
                             else "bottom_divergence",
                "area_a": round(float(d.area_a), 6),
                "area_c": round(float(d.area_c), 6),
                "ratio": d.ratio,
                "strength": d.strength,
            }
            for d in divergence
        ],
        "buy_sell_points": [
            {
                "type": int(bp.point_type),
                "side": bp.side,
                "price": bp.price,
                "idx": int(bp.idx),
                "confidence": round(float(bp.confidence), 2),
                "pivot_ref": int(bp.pivot_ref),
            }
            for bp in buy_sell
        ],
        "compute_status": compute_status,
    }


# ═══════════════════════════════════════════════════════════════════════
# Convenience: analyze_symbol
# ═══════════════════════════════════════════════════════════════════════

def analyze_symbol(symbol: str, period: str = "1y", interval: str = "1d",
                    pen_mode: str = "new") -> dict:
    """
    一键拉取 yfinance 数据并执行缠论分析。

    Parameters
    ----------
    symbol : 股票代码 (e.g. 'NVDA', 'AAPL')
    period : yfinance period ('1y', '6mo', '2y', etc.)
    interval : yfinance interval ('1d', '1wk', '60m', etc.)
    pen_mode : 'new' (default) | 'old'

    Returns
    -------
    dict : same as analyze() output
    """
    import yfinance as yf
    raw = yf.download(symbol, period=period, interval=interval, progress=False)
    # yfinance >= 0.28 may return MultiIndex columns
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    data = raw[["Open", "High", "Low", "Close", "Volume"]].reset_index()
    data.columns = ["date", "open", "high", "low", "close", "volume"]
    return analyze(data, pen_mode=pen_mode)


# ═══════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════

def _load_csv(path: str) -> pd.DataFrame:
    """
    从CSV文件加载K线数据。

    支持 columns: date, open, high, low, close, volume
    (大小写不敏感, 支持常见变体)
    """
    df = pd.read_csv(path)

    # 标准化列名
    col_map = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("date", "datetime", "time", "timestamp"):
            col_map[col] = "date"
        elif cl == "open":
            col_map[col] = "open"
        elif cl == "high":
            col_map[col] = "high"
        elif cl == "low":
            col_map[col] = "low"
        elif cl in ("close", "adj close", "adj_close", "close/last"):
            col_map[col] = "close"
        elif cl in ("volume", "vol"):
            col_map[col] = "volume"
    df = df.rename(columns=col_map)

    required = ["date", "open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "volume" not in df.columns:
        df["volume"] = 0

    # 确保数值类型
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.reset_index(drop=True)
    return df


def _generate_sample_data() -> pd.DataFrame:
    """生成模拟K线数据用于测试。"""
    np.random.seed(42)
    n = 200
    dates = pd.bdate_range("2025-01-01", periods=n)

    # 模拟价格走势: 带趋势的随机游走
    returns = np.random.randn(n) * 0.02 + 0.0005
    close = 100.0 * np.cumprod(1 + returns)

    high = close * (1 + np.abs(np.random.randn(n)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n)) * 0.01)
    open_price = close * (1 + np.random.randn(n) * 0.005)
    volume = (np.random.rand(n) * 1e6 + 1e5).astype(int)

    df = pd.DataFrame({
        "date": dates,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })

    # 确保 high >= max(open,close), low <= min(open,close)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


def main():
    """
    命令行入口。

    用法:
      # 分析CSV文件
      python chanlun_engine.py --csv data.csv

      # 使用内置样例数据
      python chanlun_engine.py --sample

      # 仅输出摘要
      python chanlun_engine.py --sample --summary-only

      # 指定旧笔模式
      python chanlun_engine.py --sample --pen-mode old

      # 输出到文件
      python chanlun_engine.py --sample --output result.json
    """
    parser = argparse.ArgumentParser(
        description="缠论核心计算引擎 - Chanlun Technical Analysis Engine"
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="CSV文件路径 (columns: date, open, high, low, close, volume)"
    )
    parser.add_argument(
        "--sample", action="store_true",
        help="使用内置样例数据运行"
    )
    parser.add_argument(
        "--pen-mode", type=str, choices=["new", "old"], default="new",
        help="笔的判定模式: new (新笔, 默认) 或 old (旧笔)"
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="仅输出摘要信息"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="输出JSON文件路径 (默认stdout)"
    )

    args = parser.parse_args()

    if args.csv:
        if not os.path.exists(args.csv):
            print(f"Error: File not found: {args.csv}", file=sys.stderr)
            sys.exit(1)
        df = _load_csv(args.csv)
        print(f"Loaded {len(df)} klines from {args.csv}", file=sys.stderr)
    elif args.sample:
        df = _generate_sample_data()
        print(f"Generated {len(df)} sample klines", file=sys.stderr)
    else:
        parser.print_help()
        sys.exit(1)

    # 执行分析
    result = analyze(df, pen_mode=args.pen_mode)

    # 输出
    if args.summary_only:
        output = {"summary": result["summary"]}
    else:
        output = result

    json_str = json.dumps(output, indent=2, ensure_ascii=False, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json_str)

    # 打印摘要
    s = result["summary"]
    print("\n── 缠论分析摘要 ──", file=sys.stderr)
    print(f"  原始K线: {s['total_klines']}", file=sys.stderr)
    print(f"  合并后:  {s['after_inclusion']} "
          f"(合并 {s['merged_count']} 根)", file=sys.stderr)
    print(f"  分型:    {s['fractal_count']} "
          f"(顶{sum(1 for f in result['fractals'] if f['type']=='top')} "
          f"底{sum(1 for f in result['fractals'] if f['type']=='bottom')})",
          file=sys.stderr)
    print(f"  笔:      {s['pen_count']}", file=sys.stderr)
    print(f"  线段:    {s['segment_count']}", file=sys.stderr)
    print(f"  中枢:    {s['pivot_count']}", file=sys.stderr)
    print(f"  背驰:    {s['divergence_count']}", file=sys.stderr)
    print(f"  买卖点:  {s['buy_sell_point_count']}", file=sys.stderr)

    if result["pivots"]:
        print("\n  中枢详情:", file=sys.stderr)
        for i, pv in enumerate(result["pivots"]):
            print(f"    [{i}] ZG={pv['ZG']} ZD={pv['ZD']} "
                  f"({pv['seg_count']}段)", file=sys.stderr)

    if result["buy_sell_points"]:
        print("\n  买卖点:", file=sys.stderr)
        for bp in result["buy_sell_points"]:
            side_str = "买入" if bp["side"] == "buy" else "卖出"
            print(f"    {side_str}{bp['type']} @ {bp['price']} "
                  f"(置信度 {bp['confidence']})", file=sys.stderr)


if __name__ == "__main__":
    main()
