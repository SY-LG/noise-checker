"""Real-time decibel plotter and desktop status overlay."""

import collections
from collections.abc import Callable
from datetime import datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation


class DecibelVisualizer:
    """Handles real-time dual-subplot visualization with rolling buffer queues."""

    # Animation update interval in ms. Must match FuncAnimation's interval below.
    _SAMPLE_INTERVAL_MS = 50
    # Capacity for the "Recent Minute" subplot at _SAMPLE_INTERVAL_MS.
    _MINUTE_POINTS = 60 * 1000 // _SAMPLE_INTERVAL_MS
    # Capacity for the "Recent Hour" subplot at _SAMPLE_INTERVAL_MS.
    _HOUR_POINTS = 60 * 60 * 1000 // _SAMPLE_INTERVAL_MS

    def __init__(
        self,
        window_title: str,
        decibel_threshold: float,
        data_source: Callable[[], tuple[datetime, float]],
        status_source: Callable[[datetime, float], tuple[float, float, float]],
        quit_check: Callable[[], bool],
    ) -> None:
        self.window_title = window_title
        self.decibel_threshold = decibel_threshold
        self.data_source = data_source
        self.status_source = status_source
        self.quit_check = quit_check

        self.times_minute: collections.deque[datetime] = collections.deque(
            maxlen=self._MINUTE_POINTS
        )
        self.decibels_minute: collections.deque[float] = collections.deque(
            maxlen=self._MINUTE_POINTS
        )
        self.times_hour: collections.deque[datetime] = collections.deque(
            maxlen=self._HOUR_POINTS
        )
        self.decibels_hour: collections.deque[float] = collections.deque(
            maxlen=self._HOUR_POINTS
        )

        self.fig, self.axs = plt.subplots(2, 1, figsize=(8, 6))
        self.lines = [ax.plot([], [])[0] for ax in self.axs]
        self._status_text = self.fig.text(0.5, 0.5, "", ha="center", va="center")
        self._ani: FuncAnimation | None = None

        self._setup_layout()

    def _setup_layout(self) -> None:
        self.fig.canvas.manager.set_window_title(self.window_title)
        plt.subplots_adjust(hspace=0.5)

        for ax in self.axs:
            ax.set_xlabel("Time")
            ax.set_ylabel("Decibel (dB)")
            ax.axhline(y=self.decibel_threshold, color="red", linestyle="--", alpha=0.7)

        self.axs[0].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        self.axs[0].set_title("Recent Hour")

        self.axs[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.axs[1].set_title("Recent Minute")

    def _update_frame(self, _frame: int):
        if self.quit_check():
            self._ani.event_source.stop()
            plt.close(self.fig)
            return self.lines

        timestamp, decibel = self.data_source()
        rate, elapsed, reset = self.status_source(timestamp, decibel)

        self.times_minute.append(timestamp)
        self.decibels_minute.append(decibel)
        self.times_hour.append(timestamp)
        self.decibels_hour.append(decibel)

        # Update text readout
        self._status_text.set_text(
            f"Noise Rate: {rate:.2f} | Active: {int(elapsed)}s | Reset in: {int(reset)}s"
        )

        # self.lines[0] is the "Recent Hour" axes (axs[0]); self.lines[1] is "Recent Minute".
        self.lines[0].set_data(list(self.times_hour), list(self.decibels_hour))
        self.lines[1].set_data(list(self.times_minute), list(self.decibels_minute))

        # Update limits for hour view
        self.axs[0].set_xlim(
            timestamp - timedelta(minutes=59), timestamp + timedelta(minutes=1)
        )
        self.axs[0].relim()
        self.axs[0].autoscale(axis="y")

        # Update limits for minute view
        self.axs[1].set_xlim(
            timestamp - timedelta(seconds=59), timestamp + timedelta(seconds=1)
        )
        self.axs[1].relim()
        self.axs[1].autoscale(axis="y")

        return self.lines

    def start(self) -> None:
        """Starts the animation loop."""
        self._ani = FuncAnimation(
            self.fig,
            self._update_frame,
            interval=50,
            blit=False,
            cache_frame_data=False,
        )
        plt.show()
