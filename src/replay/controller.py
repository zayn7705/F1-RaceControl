from __future__ import annotations

import os
import threading
import time
from typing import Callable, Dict, List, Optional, Sequence

from .engine import RaceStateEngine
from .formatting import format_full_state


class ReplayController:
    """
    Orchestrates interactive replay of a RaceStateEngine.

    It maintains play/pause state, playback speed, and exposes helpers
    for pause, rewind, fast-forward, and printing status.
    """

    def __init__(
        self,
        events: Sequence[Dict],
        snapshot_interval_events: int = 50,
        initial_speed: float = 1.0,
        status_printer: Optional[Callable[[str], None]] = None,
        prints_per_lap: int = 3,
    ) -> None:
        self.engine = RaceStateEngine(events, snapshot_interval_events=snapshot_interval_events)
        self.playback_speed = max(0.1, initial_speed)

        self._playing = False
        self._lock = threading.Lock()
        self._play_thread: Optional[threading.Thread] = None
        self._stop_requested = False

        # Allow injection for tests; default to print
        self._status_printer = status_printer or print

        # Limit how often we print during continuous play: up to
        # `prints_per_lap` times per race lap.
        self.prints_per_lap = max(1, prints_per_lap)
        self._lap_print_counts: Dict[int, int] = {}

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self) -> None:
        """Start or resume playback."""
        with self._lock:
            if self._playing:
                return
            self._playing = True
            self._stop_requested = False
            if self._play_thread is None or not self._play_thread.is_alive():
                self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
                self._play_thread.start()

    def pause(self) -> None:
        """Pause playback."""
        with self._lock:
            self._playing = False

    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier."""
        if speed <= 0:
            raise ValueError("speed must be positive")
        with self._lock:
            self.playback_speed = speed

    def stop(self) -> None:
        """Stop playback thread and reset playing flag."""
        with self._lock:
            self._stop_requested = True
            self._playing = False
        if self._play_thread is not None:
            self._play_thread.join(timeout=1.0)

    # ------------------------------------------------------------------
    # Single-step and seeking helpers
    # ------------------------------------------------------------------

    def step(self, n: int = 1) -> None:
        """Apply n events and print resulting status."""
        if n <= 0:
            return
        for _ in range(n):
            state = self.engine.apply_next_event()
            if state is None:
                break
        self.print_status()

    def rewind(self, seconds: float) -> None:
        state = self.engine.rewind(seconds)
        self._status_printer(format_full_state(state))

    def fast_forward(self, seconds: float) -> None:
        state = self.engine.fast_forward(seconds)
        self._status_printer(format_full_state(state))

    def jump_time(self, time_s: float) -> None:
        state = self.engine.jump_to_time(time_s)
        self._status_printer(format_full_state(state))

    def print_status(self, limit: int | None = None) -> None:
        state = self.engine.get_state()
        self._status_printer(format_full_state(state, limit=limit))

    # ------------------------------------------------------------------
    # Playback loop
    # ------------------------------------------------------------------

    def _play_loop(self) -> None:
        """
        Run in a background thread, applying events according to simulated
        event_time differences scaled by playback_speed.
        """
        events = self.engine.events
        while True:
            with self._lock:
                if self._stop_requested:
                    return
                playing = self._playing
                speed = self.playback_speed

            if not playing:
                time.sleep(0.05)
                continue

            idx = self.engine.get_state().current_event_index
            next_index = idx + 1
            if next_index >= len(events):
                # End of stream
                with self._lock:
                    self._playing = False
                return

            current_time = events[idx]["event_time"] if idx >= 0 else events[0]["event_time"]
            next_time = events[next_index]["event_time"]
            delta = max(0.0, float(next_time) - float(current_time))

            # Scale by playback speed; protect against extremely small sleeps
            sleep_duration = delta / speed if speed > 0 else 0.0
            if sleep_duration > 0.0:
                time.sleep(min(sleep_duration, 1.0))

            state = self.engine.apply_next_event()
            if state is None:
                # No more events to apply (safety net)
                with self._lock:
                    self._playing = False
                self._status_printer("Race complete. Exiting.")
                os._exit(0)

            # Always print final state and exit when we reach the last event,
            # regardless of per-lap print throttling.
            if state.current_event_index == len(events) - 1:
                self._status_printer(format_full_state(state))
                with self._lock:
                    self._playing = False
                self._status_printer("Race complete. Exiting.")
                os._exit(0)

            # Determine current race lap as the max lap among drivers
            if state.drivers:
                current_lap = max(d.lap for d in state.drivers.values())
            else:
                current_lap = 0

            count = self._lap_print_counts.get(current_lap, 0)
            if count < self.prints_per_lap:
                self._status_printer(format_full_state(state))
                self._lap_print_counts[current_lap] = count + 1

