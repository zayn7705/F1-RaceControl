from __future__ import annotations

import time
from typing import Any, Dict, Optional, Sequence

from .engine import RaceStateEngine
from .run_telemetry import RunTelemetry
from .state import RaceState


class InstrumentedRaceStateEngine:
    """
    Wrapper around RaceStateEngine that records wall-clock timings into RunTelemetry.

    This keeps instrumentation out of the core deterministic engine.
    """

    def __init__(self, engine: RaceStateEngine, telemetry: RunTelemetry) -> None:
        self._engine = engine
        self.telemetry = telemetry

    # ---- passthrough surface ---------------------------------------

    @property
    def events(self) -> Sequence[Dict[str, Any]]:
        return self._engine.events

    def reset(self) -> None:
        return self._engine.reset()

    def get_state(self) -> RaceState:
        return self._engine.get_state()

    # ---- instrumented methods --------------------------------------

    def apply_next_event(self) -> Optional[RaceState]:
        t0 = time.monotonic()
        st: Optional[RaceState] = None
        try:
            st = self._engine.apply_next_event()
        except BaseException as e:  # noqa: BLE001
            self.telemetry.record_exception(e)
            raise
        if st is not None:
            self.telemetry.record_apply_next_event(time.monotonic() - t0)
        return st

    def jump_to_event(self, target_index: int) -> RaceState:
        t0 = time.monotonic()
        try:
            return self._engine.jump_to_event(target_index)
        except BaseException as e:  # noqa: BLE001
            self.telemetry.record_exception(e)
            raise
        finally:
            self.telemetry.record_seek(time.monotonic() - t0)

    def jump_to_time(self, target_time_s: float) -> RaceState:
        t0 = time.monotonic()
        try:
            return self._engine.jump_to_time(target_time_s)
        except BaseException as e:  # noqa: BLE001
            self.telemetry.record_exception(e)
            raise
        finally:
            self.telemetry.record_seek(time.monotonic() - t0)

    def rewind(self, delta_s: float) -> RaceState:
        t0 = time.monotonic()
        try:
            return self._engine.rewind(delta_s)
        except BaseException as e:  # noqa: BLE001
            self.telemetry.record_exception(e)
            raise
        finally:
            self.telemetry.record_seek(time.monotonic() - t0)

    def fast_forward(self, delta_s: float) -> RaceState:
        t0 = time.monotonic()
        try:
            return self._engine.fast_forward(delta_s)
        except BaseException as e:  # noqa: BLE001
            self.telemetry.record_exception(e)
            raise
        finally:
            self.telemetry.record_seek(time.monotonic() - t0)

