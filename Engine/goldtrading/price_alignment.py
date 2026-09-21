from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import sqrt
from typing import Optional


@dataclass(frozen=True, slots=True)
class AlignmentEstimate:
    a: float
    b: float
    offset: float
    correlation: float
    samples: int


class PriceAlignmentEngine:
    """Rolling least-squares mapping: MT5 ~= a * GC + b."""

    def __init__(self, window: int = 300, min_samples: int = 30) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self.samples: deque[tuple[float, float]] = deque(maxlen=window)
        self.min_samples = max(2, min_samples)

    def reset(self) -> None:
        self.samples.clear()

    def add(self, gc_price: float, mt5_price: float) -> None:
        self.samples.append((float(gc_price), float(mt5_price)))

    def estimate(self) -> Optional[AlignmentEstimate]:
        n = len(self.samples)
        if n < self.min_samples:
            return None
        xs = [x for x, _ in self.samples]
        ys = [y for _, y in self.samples]
        mx = sum(xs) / n
        my = sum(ys) / n
        xx = sum((x - mx) ** 2 for x in xs)
        yy = sum((y - my) ** 2 for y in ys)
        if xx == 0 or yy == 0:
            return None
        xy = sum((x - mx) * (y - my) for x, y in self.samples)
        a = xy / xx
        b = my - a * mx
        corr = xy / sqrt(xx * yy)
        return AlignmentEstimate(a=a, b=b, offset=my - mx, correlation=corr, samples=n)

    def map_gc_to_mt5(self, gc_price: float) -> Optional[float]:
        estimate = self.estimate()
        if estimate is None:
            return None
        return estimate.a * float(gc_price) + estimate.b
