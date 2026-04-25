from __future__ import annotations

import json
import platform
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _now_monotonic() -> float:
    return time.monotonic()


def _safe_quantile(sorted_vals: Sequence[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    # Linear interpolation between closest ranks (works well enough for reporting)
    idx = (len(sorted_vals) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


@dataclass(frozen=True)
class LatencySummary:
    count: int
    min_s: Optional[float]
    mean_s: Optional[float]
    max_s: Optional[float]
    p50_s: Optional[float]
    p90_s: Optional[float]
    p95_s: Optional[float]
    p99_s: Optional[float]


def summarize_latencies(samples_s: Sequence[float]) -> LatencySummary:
    empty = LatencySummary(
        count=0, min_s=None, mean_s=None, max_s=None, p50_s=None, p90_s=None, p95_s=None, p99_s=None
    )
    if not samples_s:
        return empty
    vals = list(float(x) for x in samples_s if x is not None)
    if not vals:
        return empty
    vals.sort()
    return LatencySummary(
        count=len(vals),
        min_s=float(vals[0]),
        mean_s=float(statistics.fmean(vals)),
        max_s=float(vals[-1]),
        p50_s=_safe_quantile(vals, 0.50),
        p90_s=_safe_quantile(vals, 0.90),
        p95_s=_safe_quantile(vals, 0.95),
        p99_s=_safe_quantile(vals, 0.99),
    )


class RingBuffer:
    """
    Fixed-size buffer for telemetry samples.

    When full, overwrites oldest samples. Exposes contents in FIFO order.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._cap = int(capacity)
        self._buf: List[Optional[float]] = [None] * self._cap
        self._size = 0
        self._head = 0

    def append(self, v: float) -> None:
        self._buf[self._head] = float(v)
        self._head = (self._head + 1) % self._cap
        self._size = min(self._size + 1, self._cap)

    def __len__(self) -> int:
        return self._size

    def values(self) -> List[float]:
        if self._size == 0:
            return []
        start = (self._head - self._size) % self._cap
        out: List[float] = []
        for i in range(self._size):
            v = self._buf[(start + i) % self._cap]
            if v is not None:
                out.append(float(v))
        return out


@dataclass
class SimulationRunReport:
    schema_version: int
    run_id: str
    race_id: Optional[str]

    total_events: int
    events_applied: int
    completed: bool

    wall_time_s: float
    events_per_s: Optional[float]

    apply_next_event_latency: LatencySummary
    callback_latency: LatencySummary
    seek_latency: LatencySummary

    stream_issue_count: int = 0
    stream_issue_samples: List[str] = field(default_factory=list)
    state_issue_count: int = 0
    state_issue_samples: List[str] = field(default_factory=list)

    exception_count: int = 0
    exception_samples: List[str] = field(default_factory=list)

    replay_drift_mean_s: Optional[float] = None
    replay_drift_max_s: Optional[float] = None

    platform_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Flatten nested dataclasses (LatencySummary) into dicts for JSON stability
        d["apply_next_event_latency"] = asdict(self.apply_next_event_latency)
        d["callback_latency"] = asdict(self.callback_latency)
        d["seek_latency"] = asdict(self.seek_latency)
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SimulationRunReport":
        def _ls(key: str) -> LatencySummary:
            x = d[key]
            return LatencySummary(
                count=int(x["count"]),
                min_s=(float(x["min_s"]) if x.get("min_s") is not None else None),
                mean_s=(float(x["mean_s"]) if x.get("mean_s") is not None else None),
                max_s=(float(x["max_s"]) if x.get("max_s") is not None else None),
                p50_s=(float(x["p50_s"]) if x.get("p50_s") is not None else None),
                p90_s=(float(x["p90_s"]) if x.get("p90_s") is not None else None),
                p95_s=(float(x["p95_s"]) if x.get("p95_s") is not None else None),
                p99_s=(float(x["p99_s"]) if x.get("p99_s") is not None else None),
            )

        return SimulationRunReport(
            schema_version=int(d["schema_version"]),
            run_id=str(d["run_id"]),
            race_id=d.get("race_id"),
            total_events=int(d["total_events"]),
            events_applied=int(d["events_applied"]),
            completed=bool(d["completed"]),
            wall_time_s=float(d["wall_time_s"]),
            events_per_s=(float(d["events_per_s"]) if d.get("events_per_s") is not None else None),
            apply_next_event_latency=_ls("apply_next_event_latency"),
            callback_latency=_ls("callback_latency"),
            seek_latency=_ls("seek_latency"),
            stream_issue_count=int(d.get("stream_issue_count", 0)),
            stream_issue_samples=list(d.get("stream_issue_samples", [])),
            state_issue_count=int(d.get("state_issue_count", 0)),
            state_issue_samples=list(d.get("state_issue_samples", [])),
            exception_count=int(d.get("exception_count", 0)),
            exception_samples=list(d.get("exception_samples", [])),
            replay_drift_mean_s=(float(d["replay_drift_mean_s"]) if d.get("replay_drift_mean_s") is not None else None),
            replay_drift_max_s=(float(d["replay_drift_max_s"]) if d.get("replay_drift_max_s") is not None else None),
            platform_info=dict(d.get("platform_info", {})),
        )


class RunTelemetry:
    """
    Collects run performance + reliability telemetry and produces a SimulationRunReport.

    This is intentionally lightweight and in-process (no external dependencies).
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        race_id: Optional[str] = None,
        sample_capacity: int = 50_000,
        issue_sample_cap: int = 50,
        exception_sample_cap: int = 20,
    ) -> None:
        self.run_id = str(uuid.uuid4())
        self.race_id = race_id
        self.sample_capacity = int(sample_capacity)
        self.issue_sample_cap = int(issue_sample_cap)
        self.exception_sample_cap = int(exception_sample_cap)

        self._t0 = _now_monotonic()
        self._t1: Optional[float] = None

        self.total_events: int = 0
        self.events_applied: int = 0
        self.completed: bool = False

        self.apply_next_event_samples = RingBuffer(self.sample_capacity)
        self.callback_samples = RingBuffer(self.sample_capacity)
        self.seek_samples = RingBuffer(max(1, min(10_000, self.sample_capacity)))

        self.stream_issue_count: int = 0
        self.stream_issues: List[str] = []
        self.state_issue_count: int = 0
        self.state_issues: List[str] = []
        self.exception_count: int = 0
        self.exceptions: List[str] = []

        self._drift_samples = RingBuffer(max(1, min(10_000, self.sample_capacity)))

    # ---- lifecycle -------------------------------------------------

    def elapsed_wall_s(self) -> float:
        """Wall seconds since start() (or since construction before start)."""
        return max(0.0, float(_now_monotonic() - self._t0))

    def apply_latency_live(self) -> LatencySummary:
        """Current apply_next_event latency quantiles without finishing the run."""
        return summarize_latencies(self.apply_next_event_samples.values())

    def start(self, *, total_events: int) -> None:
        self.total_events = int(total_events)
        self._t0 = _now_monotonic()
        self._t1 = None
        self.events_applied = 0
        self.completed = False
        self.stream_issue_count = 0
        self.stream_issues = []
        self.state_issue_count = 0
        self.state_issues = []
        self.exception_count = 0
        self.exceptions = []

    def finish(self, *, completed: bool) -> None:
        self._t1 = _now_monotonic()
        self.completed = bool(completed)

    @property
    def finished(self) -> bool:
        return self._t1 is not None

    # ---- recorders -------------------------------------------------

    def record_apply_next_event(self, duration_s: float) -> None:
        self.apply_next_event_samples.append(duration_s)
        self.events_applied += 1

    def record_callback(self, duration_s: float) -> None:
        self.callback_samples.append(duration_s)

    def record_seek(self, duration_s: float) -> None:
        self.seek_samples.append(duration_s)

    def record_stream_issues(self, issues: Iterable[str]) -> None:
        for msg in issues:
            self.stream_issue_count += 1
            if len(self.stream_issues) < self.issue_sample_cap:
                self.stream_issues.append(str(msg))

    def record_state_issues(self, issues: Iterable[str]) -> None:
        for msg in issues:
            self.state_issue_count += 1
            if len(self.state_issues) < self.issue_sample_cap:
                self.state_issues.append(str(msg))

    def record_exception(self, exc: BaseException) -> None:
        self.exception_count += 1
        if len(self.exceptions) < self.exception_sample_cap:
            self.exceptions.append(repr(exc))

    def record_replay_drift(self, drift_s: float) -> None:
        self._drift_samples.append(drift_s)

    # ---- reporting -------------------------------------------------

    def report(self) -> SimulationRunReport:
        t1 = self._t1 if self._t1 is not None else _now_monotonic()
        wall = max(0.0, float(t1 - self._t0))
        eps = (float(self.events_applied) / wall) if wall > 0 else None

        drift_vals = self._drift_samples.values()
        drift_mean = float(statistics.fmean(drift_vals)) if drift_vals else None
        drift_max = float(max(drift_vals)) if drift_vals else None

        platform_info = {
            "python": platform.python_version(),
            "platform": platform.platform(),
        }

        return SimulationRunReport(
            schema_version=self.SCHEMA_VERSION,
            run_id=self.run_id,
            race_id=self.race_id,
            total_events=int(self.total_events),
            events_applied=int(self.events_applied),
            completed=bool(self.completed),
            wall_time_s=wall,
            events_per_s=eps,
            apply_next_event_latency=summarize_latencies(self.apply_next_event_samples.values()),
            callback_latency=summarize_latencies(self.callback_samples.values()),
            seek_latency=summarize_latencies(self.seek_samples.values()),
            stream_issue_count=int(self.stream_issue_count),
            stream_issue_samples=list(self.stream_issues),
            state_issue_count=int(self.state_issue_count),
            state_issue_samples=list(self.state_issues),
            exception_count=int(self.exception_count),
            exception_samples=list(self.exceptions),
            replay_drift_mean_s=drift_mean,
            replay_drift_max_s=drift_max,
            platform_info=platform_info,
        )

