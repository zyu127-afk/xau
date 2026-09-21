from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import sqrt
import time
from typing import Optional


@dataclass(frozen=True, slots=True)
class AlignmentEstimate:
    a: float
    b: float
    offset: float
    correlation: float
    samples: int
    rmse: float
    max_abs_residual: float
    age_seconds: float


class PriceAlignmentEngine:
    """Rolling least-squares mapping: MT5 ~= a * GC + b, with quality/freshness metrics."""

    def __init__(self, window: int = 300, min_samples: int = 30) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self.samples: deque[tuple[float, float]] = deque(maxlen=window)
        self.min_samples = max(2, min_samples)
        self.last_update_monotonic = 0.0
        self.instrument = ""

    def reset(self, instrument: str | None = None) -> None:
        self.samples.clear()
        self.last_update_monotonic = 0.0
        if instrument is not None:
            self.instrument = instrument

    def set_instrument(self, instrument: str) -> bool:
        instrument = str(instrument or "")
        if instrument and self.instrument and instrument != self.instrument:
            self.reset(instrument)
            return True
        if instrument and not self.instrument:
            self.instrument = instrument
        return False

    def add(self, gc_price: float, mt5_price: float) -> None:
        x = float(gc_price); y = float(mt5_price)
        if not (x > 0 and y > 0):
            return
        # Once warmed up, reject extreme isolated mapping outliers. A real contract change is handled by set_instrument/reset.
        current = self.estimate()
        if current is not None:
            residual = abs(y - (current.a * x + current.b))
            dynamic_limit = max(5.0, current.rmse * 6.0)
            if residual > dynamic_limit:
                return
        self.samples.append((x, y))
        self.last_update_monotonic = time.monotonic()

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
        residuals = [y - (a * x + b) for x, y in self.samples]
        rmse = sqrt(sum(r * r for r in residuals) / n)
        max_abs = max(abs(r) for r in residuals)
        age = float("inf") if self.last_update_monotonic <= 0 else max(0.0, time.monotonic() - self.last_update_monotonic)
        return AlignmentEstimate(a=a, b=b, offset=my - mx, correlation=corr, samples=n,
                                 rmse=rmse, max_abs_residual=max_abs, age_seconds=age)

    def quality_ok(self, min_correlation: float = 0.80, max_residual: float = 2.50,
                   stale_seconds: float = 5.0) -> bool:
        e = self.estimate()
        return bool(e is not None and abs(e.correlation) >= min_correlation and e.rmse <= max_residual and e.age_seconds <= stale_seconds)

    def quality_reason(self, min_correlation: float = 0.80, max_residual: float = 2.50,
                       stale_seconds: float = 5.0) -> str:
        e = self.estimate()
        if e is None:
            return "WARMING_UP"
        if abs(e.correlation) < min_correlation:
            return "LOW_CORRELATION"
        if e.rmse > max_residual:
            return "HIGH_RESIDUAL"
        if e.age_seconds > stale_seconds:
            return "STALE"
        return "HEALTHY"

    def map_gc_to_mt5(self, gc_price: float) -> Optional[float]:
        estimate = self.estimate()
        if estimate is None:
            return None
        return estimate.a * float(gc_price) + estimate.b
