# Noise Checker

An automated, real-time decibel monitoring and alert system designed for Windows. It tracks ambient audio levels, provides a live visual dashboard, filters transient sound spikes via a state machine, and triggers a system-overriding alarm when continuous noise thresholds are breached.

## Features

- **Real-Time Visualization**: Dual-scale Matplotlib dashboard showing rolling decibel trends across the past hour and past minute.
- **State-Driven Detection**: Differentiates isolated bumps from sustained disturbances using rate-based duration windows.
- **Volume Override Alarm**: Temporarily un-mutes and maximizes Windows endpoint/session volumes during an alert, restoring original states afterward.
- **Bounded Memory Profile**: Employs rolling double-ended queues to ensure leak-free background execution.
- **Configurable Settings**: Centralized YAML configuration for thresholds, audio devices, and schedules.

## Configuration

Modify `config/config.yaml` to adjust thresholds and audio properties.

## Automation

You can schedule Noise Checker to launch automatically at night using **Windows Task Scheduler** (`taskschd.msc`):

1. Create a basic task with a daily schedule trigger.
2. Set the action to **Start a program**:
* **Program/script**: `path\to\your\venv\Scripts\pythonw.exe` (or `python.exe`)
* **Arguments**: `main.py`
* **Start in**: `path\to\noise-checker\` *(Required so relative paths and configs resolve correctly)*.
