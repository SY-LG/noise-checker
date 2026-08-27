"""Noise detection and state management."""

import threading
from collections.abc import Callable
from datetime import datetime


class NoiseDetector:
    """Tracks decibel levels over time and triggers alarms on persistent noise."""

    def __init__(
        self,
        decibel_threshold: float = 40.0,
        noise_rate_threshold: float = 0.05,
        noise_duration_threshold: float = 5.0,
        reset_timeout: float = 30.0,
        on_alarm_callback: Callable[[], None] | None = None,
    ) -> None:
        self.decibel_threshold = decibel_threshold
        self.noise_rate_threshold = noise_rate_threshold
        self.noise_duration_threshold = noise_duration_threshold
        self.reset_timeout = reset_timeout
        self.on_alarm_callback = on_alarm_callback

        self.is_checking: bool = False
        self.total_frames: int = 0
        self.noise_frames: int = 0
        self.current_rate: float = 0.0
        self.reset_countdown: float = 0.0
        self.elapsed_seconds: float = 0.0

        self._check_begin_time: datetime | None = None
        self._check_latest_time: datetime | None = None

    def process_sample(self, timestamp: datetime, decibel: float) -> tuple[float, float, float]:
        """
        Updates detector state with latest decibel sample.
        `timestamp` comes from the data source so all downstream code shares a
        single clock. Returns (current_rate, elapsed_seconds, reset_countdown).
        """
        now = timestamp

        if self.is_checking:
            self.total_frames += 1
            if decibel > self.decibel_threshold:
                self.noise_frames += 1
                self._check_latest_time = now

            self.current_rate = (
                self.noise_frames / self.total_frames if self.total_frames > 0 else 0.0
            )

            if self._check_latest_time:
                silent_elapsed = (now - self._check_latest_time).total_seconds()
                self.reset_countdown = max(0.0, self.reset_timeout - silent_elapsed)
                if self.reset_countdown <= 0.0:
                    self._reset()

            if self._check_begin_time:
                self.elapsed_seconds = (now - self._check_begin_time).total_seconds()
                if (
                    self.elapsed_seconds > self.noise_duration_threshold
                    and self.current_rate > self.noise_rate_threshold
                ):
                    self._trigger_alarm()
                    self._reset()

        elif decibel > self.decibel_threshold:
            self.is_checking = True
            self._check_begin_time = now
            self._check_latest_time = now
            self.total_frames = 1
            self.noise_frames = 1
            self.current_rate = 1.0
            self.reset_countdown = self.reset_timeout
            self.elapsed_seconds = 0.0

        return self.current_rate, self.elapsed_seconds, self.reset_countdown

    def _reset(self) -> None:
        self.is_checking = False
        self.total_frames = 0
        self.noise_frames = 0
        self.current_rate = 0.0
        self.reset_countdown = 0.0
        self.elapsed_seconds = 0.0
        self._check_begin_time = None
        self._check_latest_time = None

    def _trigger_alarm(self) -> None:
        if self.on_alarm_callback:
            threading.Thread(target=self.on_alarm_callback, daemon=True).start()
