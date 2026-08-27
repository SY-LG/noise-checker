"""Entry point for the Noise Checker application."""

import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyaudio
import pygetwindow as gw
import pymsgbox
import yaml

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "True"
import pygame

from src.audio_controller import AlarmPlayer
from src.monitor import NoiseDetector
from src.visualizer import DecibelVisualizer

APP_NAME = "noise checker"


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_input_device_index(
    audio: pyaudio.PyAudio, keyword: str | None
) -> int | None:
    if not keyword:
        return None
    for idx in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(idx)
        if keyword.lower() in info.get("name", "").lower():
            return idx
    return None


def minimize_window(title: str) -> None:
    """Silently minimizes the application window after a brief delay."""
    time.sleep(0.8)
    windows = gw.getWindowsWithTitle(title)
    if windows:
        windows[0].minimize()
    pymsgbox.alert("Noise Checker is active.", "Monitoring Started")


def main() -> None:
    config = load_config()

    # Initialize Pygame Mixer
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.init()

    # Setup PyAudio Stream
    audio = pyaudio.PyAudio()
    audio_cfg = config["audio"]
    sample_rate = audio_cfg.get("sample_rate", 48000)
    chunk_size = audio_cfg.get("chunk_size", 1024)
    channels = audio_cfg.get("channels", 1)
    input_idx = get_input_device_index(audio, audio_cfg.get("input_device_keyword"))

    stream = audio.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_size,
        input_device_index=input_idx,
    )

    # Initialize Alarm Player & Noise Detector
    alarm_cfg = config["alarm"]
    alarm_player = AlarmPlayer(
        frequency=alarm_cfg.get("frequency", 1000),
        duration_ms=alarm_cfg.get("duration_ms", 1000),
        volume=alarm_cfg.get("volume", 0.5),
        repeat_count=alarm_cfg.get("repeat_count", 10),
        speaker_device_id=alarm_cfg.get("speaker_device_id", ""),
    )

    detect_cfg = config["detection"]
    detector = NoiseDetector(
        decibel_threshold=detect_cfg.get("decibel_threshold", 40.0),
        noise_rate_threshold=detect_cfg.get("noise_rate_threshold", 0.05),
        noise_duration_threshold=detect_cfg.get("noise_duration_threshold", 5.0),
        reset_timeout=detect_cfg.get("reset_timeout", 30.0),
        on_alarm_callback=alarm_player.trigger,
    )

    def read_audio_data() -> tuple[datetime, float]:
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(tz=beijing_tz)
        raw_data = stream.read(chunk_size, exception_on_overflow=False)
        samples = np.frombuffer(raw_data, dtype=np.int16)
        mean_square = np.mean(samples.astype(np.float64) ** 2)
        decibel = 20.0 * np.log10(np.sqrt(mean_square)) if mean_square > 0 else 0.0
        return now, max(0.0, decibel)

    def check_auto_quit() -> bool:
        beijing_tz = timezone(timedelta(hours=8))
        schedule_cfg = config.get("schedule", {})
        if schedule_cfg.get("auto_quit", False):
            return datetime.now(tz=beijing_tz).hour == schedule_cfg.get("quit_hour", 4)
        return False

    visualizer = DecibelVisualizer(
        window_title=APP_NAME,
        decibel_threshold=detect_cfg.get("decibel_threshold", 40.0),
        data_source=read_audio_data,
        status_source=detector.process_sample,
        quit_check=check_auto_quit,
    )

    # Launch background task to minimize window
    threading.Thread(target=minimize_window, args=(APP_NAME,), daemon=True).start()

    try:
        visualizer.start()
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
