"""Windows audio endpoint and session volume management via Core Audio APIs."""

from ctypes import POINTER, cast

import comtypes
import numpy as np
import pygame
import pythoncom
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.pycaw import (
    AudioUtilities,
    EDataFlow,
    IAudioEndpointVolume,
    IMMDeviceEnumerator,
    ISimpleAudioVolume,
)


class SpeakerVolumeController:
    """Controls the master endpoint volume and mute state."""

    def __init__(self, target_device_id: str = "") -> None:
        self.device_id = target_device_id
        self._volume: POINTER(IAudioEndpointVolume) | None = None
        self._vol_range: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._last_level: float = 0.0
        self._last_mute: int = 0
        self._init_device()

    def _init_device(self) -> None:
        device_enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator,
            IMMDeviceEnumerator,
            comtypes.CLSCTX_INPROC_SERVER,
        )
        flow = EDataFlow.eRender.value

        target_device = None
        if self.device_id:
            devices = device_enumerator.EnumAudioEndpoints(flow, 1)
            for device in devices:
                if device.GetId() == self.device_id:
                    target_device = device
                    break
        else:
            target_device = AudioUtilities.GetSpeakers()

        if target_device is None:
            raise RuntimeError("Audio output device not found.")

        endpoint = target_device.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        self._volume = cast(endpoint, POINTER(IAudioEndpointVolume))
        self._vol_range = self._volume.GetVolumeRange()

    def maximize(self) -> None:
        """Saves current state, unmutes, and sets master volume to max."""
        if not self._volume:
            return
        self._last_level = self._volume.GetMasterVolumeLevel()
        self._last_mute = self._volume.GetMute()
        self._volume.SetMasterVolumeLevel(self._vol_range[1], None)
        self._volume.SetMute(0, None)

    def restore(self) -> None:
        """Restores master volume and mute state to previous levels."""
        if not self._volume:
            return
        self._volume.SetMasterVolumeLevel(self._last_level, None)
        self._volume.SetMute(self._last_mute, None)


class SessionVolumeController:
    """Controls application/system session volume."""

    def __init__(self) -> None:
        pythoncom.CoInitialize()
        self._volume: ISimpleAudioVolume | None = None
        self._last_volume: float = 1.0
        self._init_session()

    def _init_session(self) -> None:
        for session in AudioUtilities.GetAllSessions():
            if session.DisplayName and "AudioSrv.Dll" in session.DisplayName:
                self._volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                break

    def maximize(self) -> None:
        """Saves current volume and sets to 100%."""
        if not self._volume:
            return
        self._last_volume = self._volume.GetMasterVolume()
        self._volume.SetMasterVolume(1.0, None)

    def restore(self) -> None:
        """Restores session volume to previous level."""
        if not self._volume:
            return
        self._volume.SetMasterVolume(self._last_volume, None)


class AlarmPlayer:
    """Generates and plays alarm beeps using Pygame."""

    def __init__(
        self,
        frequency: int = 1000,
        duration_ms: int = 1000,
        volume: float = 0.5,
        repeat_count: int = 10,
        speaker_device_id: str = "",
    ) -> None:
        self.frequency = frequency
        self.duration_ms = duration_ms
        self.volume = volume
        self.repeat_count = repeat_count
        self.speaker_device_id = speaker_device_id

        self._speaker_ctrl = SpeakerVolumeController(speaker_device_id)
        self._sound = self._build_sound()

    def _build_sound(self) -> pygame.mixer.Sound:
        sample_rate = 44100
        num_samples = int(self.duration_ms * sample_rate / 1000)
        time_steps = np.arange(num_samples)
        sine_wave = np.sin(2 * np.pi * self.frequency * time_steps / sample_rate)
        audio_data = (32767 * self.volume * sine_wave).astype(np.int16)
        # Convert mono array to stereo buffer for Pygame mixer compatibility
        stereo_data = np.ascontiguousarray(np.column_stack((audio_data, audio_data)))
        return pygame.sndarray.make_sound(stereo_data)

    def trigger(self) -> None:
        """Overrides volumes, sounds the alarm, and restores volume states."""
        session_ctrl = SessionVolumeController()
        try:
            session_ctrl.maximize()
            self._speaker_ctrl.maximize()
            for _ in range(self.repeat_count):
                self._sound.play()
                pygame.time.wait(self.duration_ms)
        finally:
            try:
                session_ctrl.restore()
            finally:
                self._speaker_ctrl.restore()
