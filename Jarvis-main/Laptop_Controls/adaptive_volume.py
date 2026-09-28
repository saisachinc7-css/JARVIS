"""
Adaptive Volume Control for Friday (JARVIS Voice Assistant)
===========================================================

Dynamically adjusts Windows system volume so Friday's voice replies are always
clearly audible, without permanently affecting the user's existing audio.

Uses pycaw (Python Core Audio Windows) for precise, low-latency volume control.

CASES:
  A) Media playing → duck system vol to 15%, speak at 35%, restore
  B) Explicit call  → ensure vol ≥ 30%, speak at 30%, restore

SAFETY:
  - Original volume is always cached before any change
  - Restored via try/finally, atexit, and signal handlers
  - Thread-safe with reentrance guard against flickering

OPTIONAL:
  - Smooth fade transitions
  - All thresholds configurable via volume_config
  - Full logging
"""

import threading
import time
import logging
import atexit
from typing import Optional

# ============================================================================
# LOGGING
# ============================================================================

logger = logging.getLogger("AdaptiveVolume")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(name)s] %(levelname)s: %(message)s"
    ))
    logger.addHandler(_handler)


# ============================================================================
# CONFIG (defaults – overridden by volume_config if present)
# ============================================================================

_config = {
    # Case A: media is playing
    "media_duck_volume": 30,        # system vol while Friday speaks (%)
    "media_friday_volume": 40,      # Friday reply volume (%)

    # Case B: explicit call
    "explicit_friday_volume": 35,   # Friday reply volume (%)
    "explicit_min_system_volume": 30,  # raise system vol to this if below

    # Fade settings
    "fade_enabled": True,
    "fade_steps": 10,               # number of intermediate steps
    "fade_duration_ms": 300,        # total fade time in ms

    # Audio detection threshold (pycaw peak meter, 0.0–1.0)
    "media_playing_threshold": 0.01,

    # Audio ducking (per-app)
    "ducking_enabled": False,       # DISABLED: too risky if restore fails
    "ducking_level": 0.50,
    "ducking_fade_ms": 150,
    "ducking_fade_steps": 5,
    "ducking_target_processes": [],
    "ducking_exclude_processes": [],

    # Night mode (lower volumes between these hours)
    "night_mode_enabled": True,
    "night_start_hour": 22,         # 10 PM
    "night_end_hour": 7,            # 7 AM
    "night_volume_multiplier": 0.6, # multiply all target volumes by this
}


def _load_config():
    """Attempt to load user overrides from volume_config.py"""
    try:
        from Laptop_Controls.volume_config import VOLUME_CONFIG
        _config.update(VOLUME_CONFIG)
        logger.info("Loaded user volume config overrides")
    except ImportError:
        pass  # Use defaults
    except Exception as e:
        logger.warning(f"Error loading volume config: {e}")


_load_config()


# ============================================================================
# WINDOWS AUDIO INTERFACE (pycaw)
# ============================================================================

class _WindowsAudio:
    """
    Low-level Windows audio interface using pycaw.
    Provides get/set system volume and media-playing detection.
    Compatible with pycaw >= 2025 (new API: speakers.EndpointVolume).
    """

    def __init__(self):
        self._volume_interface = None
        self._meter_interface = None
        self._initialized = False
        self._init_lock = threading.Lock()

    def _ensure_init(self):
        """Lazy-init COM interfaces (must be called from same thread or with care)."""
        if self._initialized:
            return True

        with self._init_lock:
            if self._initialized:
                return True
            try:
                import comtypes
                comtypes.CoInitialize()

                from pycaw.pycaw import AudioUtilities

                speakers = AudioUtilities.GetSpeakers()

                # New pycaw API: EndpointVolume property
                self._volume_interface = speakers.EndpointVolume

                # Audio meter for detecting media playback via raw IMMDevice
                try:
                    from pycaw.pycaw import IAudioMeterInformation
                    from comtypes import CLSCTX_ALL
                    raw_device = speakers._dev
                    meter = raw_device.Activate(
                        IAudioMeterInformation._iid_, CLSCTX_ALL, None
                    )
                    self._meter_interface = meter.QueryInterface(IAudioMeterInformation)
                except Exception as e:
                    logger.warning(f"Audio meter unavailable (media detection limited): {e}")
                    self._meter_interface = None

                self._initialized = True
                logger.info("Windows audio interface initialized")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize Windows audio: {e}")
                return False

    def get_volume(self) -> int:
        """Get current system master volume as 0–100 integer."""
        if not self._ensure_init():
            return 50  # safe fallback
        try:
            scalar = self._volume_interface.GetMasterVolumeLevelScalar()
            return round(scalar * 100)
        except Exception as e:
            logger.error(f"Get volume failed: {e}")
            return 50

    def set_volume(self, level: int):
        """Set system master volume (0–100)."""
        if not self._ensure_init():
            return
        level = max(0, min(100, level))
        try:
            self._volume_interface.SetMasterVolumeLevelScalar(level / 100.0, None)
        except Exception as e:
            logger.error(f"Set volume failed: {e}")

    def is_media_playing(self) -> bool:
        """Detect if any audio is currently playing on the system."""
        if not self._ensure_init():
            return False

        # Method 1: Audio meter peak level
        if self._meter_interface:
            try:
                peak = self._meter_interface.GetPeakValue()
                return peak > _config["media_playing_threshold"]
            except Exception:
                pass

        # Method 2: Check active audio sessions
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name():
                    proc_name = session.Process.name().lower()
                    # Skip our own process
                    if "python" in proc_name:
                        continue
                    # Check if session is active (has audio)
                    try:
                        meter = session._ctl.QueryInterface(
                            self._get_session_meter_iid()
                        )
                        if meter.GetPeakValue() > _config["media_playing_threshold"]:
                            return True
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"Session enumeration failed: {e}")

        return False

    def _get_session_meter_iid(self):
        """Get IAudioMeterInformation IID for session-level metering."""
        from pycaw.pycaw import IAudioMeterInformation
        return IAudioMeterInformation._iid_

    def is_muted(self) -> bool:
        """Check if system volume is muted."""
        if not self._ensure_init():
            return False
        try:
            return bool(self._volume_interface.GetMute())
        except Exception:
            return False

    def get_app_sessions(self):
        """
        Get all active audio sessions with per-app volume control.
        Returns list of (process_name, ISimpleAudioVolume) tuples.
        Excludes our own Python process.
        """
        if not self._ensure_init():
            return []

        sessions_out = []
        try:
            from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

            sessions = AudioUtilities.GetAllSessions()
            exclude = {"python.exe", "pythonw.exe"}
            extra_exclude = set(
                p.lower() for p in _config.get("ducking_exclude_processes", [])
            )
            exclude |= extra_exclude

            for session in sessions:
                if not session.Process:
                    continue
                proc_name = session.Process.name().lower()
                if proc_name in exclude:
                    continue
                try:
                    vol_ctl = session._ctl.QueryInterface(ISimpleAudioVolume)
                    sessions_out.append((proc_name, vol_ctl))
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"get_app_sessions error: {e}")

        return sessions_out

    def duck_apps(self, level: float = None) -> dict:
        """
        Duck (lower) volume of ALL other apps to given fraction.
        JARVIS's own Python process is excluded so TTS stays loud.

        Args:
            level: 0.0–1.0 fraction to set other apps to (default from config)

        Returns:
            dict mapping process_name -> original_volume (for restoring later)
        """
        if level is None:
            level = _config.get("ducking_level", 0.15)

        originals = {}
        sessions = self.get_app_sessions()

        for proc_name, vol_ctl in sessions:
            try:
                orig = vol_ctl.GetMasterVolume()
                originals[proc_name] = orig
                target = orig * level
                vol_ctl.SetMasterVolume(max(0.0, min(1.0, target)), None)
            except Exception as e:
                logger.debug(f"Duck {proc_name} failed: {e}")

        if originals:
            logger.info(
                f"Ducked {len(originals)} app(s) to {level:.0%}: "
                f"{', '.join(originals.keys())}"
            )
        return originals

    def unduck_apps(self, originals: dict):
        """
        Restore app volumes from a previous duck_apps() call.

        Args:
            originals: dict from duck_apps() mapping proc_name -> original_volume
        """
        if not originals:
            return

        sessions = self.get_app_sessions()
        proc_map = {name: ctl for name, ctl in sessions}

        restored = 0
        for proc_name, orig_vol in originals.items():
            vol_ctl = proc_map.get(proc_name)
            if vol_ctl:
                try:
                    vol_ctl.SetMasterVolume(max(0.0, min(1.0, orig_vol)), None)
                    restored += 1
                except Exception as e:
                    logger.debug(f"Unduck {proc_name} failed: {e}")

        if restored:
            logger.info(f"Restored volume for {restored}/{len(originals)} app(s)")

    def _reset_all_app_volumes(self):
        """
        Emergency blanket reset: set ALL app session volumes to 100%.
        Used as a last resort when the originals dict may be lost/corrupted.
        """
        sessions = self.get_app_sessions()
        for name, vol_ctl in sessions:
            try:
                vol_ctl.SetMasterVolume(1.0, None)
            except Exception:
                pass


# ============================================================================
# ADAPTIVE VOLUME CONTROLLER
# ============================================================================

class AdaptiveVolumeController:
    """
    Thread-safe adaptive volume controller for Friday's speech.

    NEW: Per-app audio ducking for wake word detection.
    When the user says "Friday", OTHER apps (Spotify, Chrome, etc.) are
    instantly ducked to ~15% of their volume. JARVIS's own TTS stays at
    full volume since it runs in the Python process (which is excluded).
    After JARVIS finishes speaking, all apps are restored.

    Usage:
        avc = get_adaptive_volume()

        # On wake word detection (instant):
        avc.on_wake_word()

        # Before Friday speaks (also ensures min system vol):
        avc.prepare_for_speech()

        # ... play TTS audio ...

        # After Friday finishes (restores everything):
        avc.restore_after_speech()
    """

    def __init__(self):
        self._audio = _WindowsAudio()
        self._lock = threading.Lock()

        # System volume state
        self._original_volume: Optional[int] = None
        self._is_adjusted = False
        self._adjustment_count = 0  # reentrance guard

        # Per-app ducking state
        self._ducked_originals: dict = {}  # proc_name -> original_volume
        self._is_ducked = False

        # Register emergency restore
        atexit.register(self._emergency_restore)

        # Safety: reset any stuck ducked apps from a previous crashed session
        self._startup_safety_check()

    # ── Public API ──────────────────────────────────────────────────────
    def on_wake_word(self):
        """
        Called INSTANTLY when the wake word is detected.
        Ducks all other app volumes so background audio is quiet while
        JARVIS listens and responds. JARVIS's own audio (Python process)
        is NOT ducked, so TTS will be loud and clear.

        Safe to call multiple times — only ducks once per cycle.
        """
        if not _config.get("ducking_enabled", True):
            return

        with self._lock:
            if self._is_ducked:
                logger.debug("Already ducked, skipping")
                return

            try:
                ducking_level = _config.get("ducking_level", 0.15)
                self._ducked_originals = self._audio.duck_apps(ducking_level)
                self._is_ducked = bool(self._ducked_originals)
                if self._is_ducked:
                    logger.info("Wake word -> apps ducked")
                    # Update shared state
                    try:
                        from shared_state import set_wake_ducking
                        set_wake_ducking(True)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Wake word ducking failed: {e}")
    def prepare_for_speech(self) -> dict:
        """
        Adjust system volume before Friday speaks.
        Detects active media and applies the appropriate case.

        Returns:
            dict with keys: case, original_volume, target_volume, media_playing
        """
        with self._lock:
            self._adjustment_count += 1

            # Already adjusted (re-entrant call) – skip
            if self._is_adjusted:
                logger.debug("Already adjusted, skipping (reentrant)")
                return {
                    "case": "reentrant",
                    "original_volume": self._original_volume,
                    "target_volume": self._audio.get_volume(),
                    "media_playing": False,
                }

            current_vol = self._audio.get_volume()
            self._original_volume = current_vol
            media_playing = self._audio.is_media_playing()

            night_mult = self._get_night_multiplier()

            if media_playing:
                # CASE A: Media is playing
                target = int(_config["media_duck_volume"] * night_mult)
                friday_vol = int(_config["media_friday_volume"] * night_mult)
                case = "A_media"
                logger.info(
                    f"CASE A: Media playing | vol {current_vol}% -> {target}% | "
                    f"Friday vol target: {friday_vol}%"
                )
            else:
                # CASE B: Explicit call
                friday_vol = int(_config["explicit_friday_volume"] * night_mult)
                min_sys = int(_config["explicit_min_system_volume"] * night_mult)

                if current_vol < min_sys:
                    target = min_sys
                    case = "B_raise"
                    logger.info(
                        f"CASE B: Vol too low ({current_vol}%) -> raising to {target}%"
                    )
                else:
                    target = current_vol  # don't change
                    case = "B_keep"
                    logger.info(
                        f"CASE B: Vol adequate ({current_vol}%), keeping"
                    )

            # Apply volume change
            if target != current_vol:
                self._fade_volume(current_vol, target)
            
            self._is_adjusted = True

            return {
                "case": case,
                "original_volume": self._original_volume,
                "target_volume": target,
                "friday_volume": friday_vol,
                "media_playing": media_playing,
            }

    def restore_after_speech(self):
        """
        Restore system volume AND unduck all apps after Friday finishes speaking.
        Safe to call multiple times – only restores once per prepare cycle.
        """
        with self._lock:
            # ── Restore per-app ducking first ──
            if self._is_ducked:
                try:
                    self._audio.unduck_apps(self._ducked_originals)
                    logger.info("Apps un-ducked")
                except Exception as e:
                    logger.error(f"Unduck failed: {e}")
                finally:
                    self._ducked_originals = {}
                    self._is_ducked = False
                    try:
                        from shared_state import set_wake_ducking
                        set_wake_ducking(False)
                    except Exception:
                        pass

            # ── Restore system volume ──
            if not self._is_adjusted:
                logger.debug("Not adjusted, nothing to restore")
                return

            self._adjustment_count -= 1
            if self._adjustment_count > 0:
                logger.debug(f"Nested call, {self._adjustment_count} remaining")
                return

            if self._original_volume is not None:
                current = self._audio.get_volume()
                target = self._original_volume

                # SAFETY: If the user MANUALLY raised volume while we were
                # speaking (e.g. they set it to 80% but we stored 26% as
                # "original"), we must NOT slam it back down. Only restore
                # if current is still close to what WE set it to.
                if current > target:
                    # User raised it — respect their choice, don't lower
                    logger.info(
                        f"Volume is now {current}% (was {target}%) — "
                        f"user raised it, keeping their setting"
                    )
                elif current != target:
                    logger.info(
                        f"Restoring volume: {current}% -> {target}%"
                    )
                    self._fade_volume(current, target)
                else:
                    logger.debug("Volume unchanged, no restore needed")

            self._is_adjusted = False
            self._original_volume = None
            self._adjustment_count = 0

    def get_system_volume(self) -> int:
        """Get current system volume (0–100)."""
        return self._audio.get_volume()

    def set_system_volume(self, level: int):
        """Directly set system volume (0–100). Use with care."""
        self._audio.set_volume(level)

    def is_media_playing(self) -> bool:
        """Check if media audio is currently playing."""
        return self._audio.is_media_playing()

    def is_night_time(self) -> bool:
        """Check if current time is within night hours."""
        if not _config["night_mode_enabled"]:
            return False
        from datetime import datetime
        hour = datetime.now().hour
        start = _config["night_start_hour"]
        end = _config["night_end_hour"]
        if start > end:
            return hour >= start or hour < end
        return start <= hour < end

    def get_volume_status(self) -> dict:
        """Get current volume system status for debugging."""
        return {
            "current_volume": self._audio.get_volume(),
            "is_adjusted": self._is_adjusted,
            "original_volume": self._original_volume,
            "media_playing": self._audio.is_media_playing(),
            "is_muted": self._audio.is_muted(),
            "night_mode": self.is_night_time(),
            "config": dict(_config),
        }

    # ── Private helpers ─────────────────────────────────────────────────

    def _fade_volume(self, from_vol: int, to_vol: int):
        """
        Smoothly transition volume from from_vol to to_vol.
        Falls back to instant set if fade is disabled or fails.
        """
        if not _config["fade_enabled"] or from_vol == to_vol:
            self._audio.set_volume(to_vol)
            return

        steps = _config["fade_steps"]
        duration = _config["fade_duration_ms"] / 1000.0
        step_delay = duration / steps

        try:
            for i in range(1, steps + 1):
                progress = i / steps
                intermediate = round(from_vol + (to_vol - from_vol) * progress)
                self._audio.set_volume(intermediate)
                if i < steps:
                    time.sleep(step_delay)
        except Exception as e:
            logger.error(f"Fade failed, setting directly: {e}")
            self._audio.set_volume(to_vol)

    def _get_night_multiplier(self) -> float:
        """Return volume multiplier based on time of day."""
        if self.is_night_time():
            mult = _config["night_volume_multiplier"]
            logger.debug(f"Night mode active, multiplier: {mult}")
            return mult
        return 1.0

    def _emergency_restore(self):
        """Last-resort volume restore on process exit."""
        # Restore per-app ducking
        if self._is_ducked and self._ducked_originals:
            try:
                logger.warning("Emergency unduck")
                self._audio.unduck_apps(self._ducked_originals)
            except Exception:
                pass
            finally:
                self._ducked_originals = {}
                self._is_ducked = False

        # Also do a blanket reset of all app volumes to 100%
        # in case the originals dict was lost/corrupted
        try:
            self._audio._reset_all_app_volumes()
        except Exception:
            pass

        # Restore system volume
        if self._original_volume is not None and self._is_adjusted:
            try:
                logger.warning(
                    f"Emergency restore: vol -> {self._original_volume}%"
                )
                self._audio.set_volume(self._original_volume)
            except Exception as e:
                logger.error(f"Emergency restore failed: {e}")
            finally:
                self._is_adjusted = False
                self._original_volume = None

    def _startup_safety_check(self):
        """
        Detect and fix app volumes that were left ducked from a previous
        JARVIS session that crashed before restore_after_speech() ran.
        
        Heuristic: if multiple apps are at suspiciously low volumes
        (below 30%), reset them all to 100%.
        """
        try:
            sessions = self._audio.get_app_sessions()
            if not sessions:
                return

            low_apps = []
            for name, vol_ctl in sessions:
                try:
                    vol = vol_ctl.GetMasterVolume()
                    if vol < 0.30:
                        low_apps.append((name, vol, vol_ctl))
                except Exception:
                    continue

            # If 2+ apps are suspiciously low, this is likely a stuck duck
            if len(low_apps) >= 2:
                logger.warning(
                    f"Startup safety: {len(low_apps)} apps at low volume "
                    f"(likely stuck from previous crash). Resetting all to 100%."
                )
                for name, old_vol, vol_ctl in low_apps:
                    try:
                        vol_ctl.SetMasterVolume(1.0, None)
                        logger.info(f"  Reset {name}: {old_vol:.0%} -> 100%")
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Startup safety check failed (non-fatal): {e}")


# ============================================================================
# SINGLETON
# ============================================================================

_instance: Optional[AdaptiveVolumeController] = None
_instance_lock = threading.Lock()


def get_adaptive_volume() -> AdaptiveVolumeController:
    """Get singleton AdaptiveVolumeController instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AdaptiveVolumeController()
    return _instance


# ============================================================================
# CONVENIENCE WRAPPERS (for use in TTS and other modules)
# ============================================================================

def prepare_for_speech() -> dict:
    """Convenience: adjust volume before Friday speaks."""
    return get_adaptive_volume().prepare_for_speech()


def restore_after_speech():
    """Convenience: restore volume after Friday finishes."""
    get_adaptive_volume().restore_after_speech()


def on_wake_word():
    """Convenience: duck other apps instantly when wake word is detected."""
    get_adaptive_volume().on_wake_word()


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    av = get_adaptive_volume()
    status = av.get_volume_status()
    print("=== Adaptive Volume Status ===")
    for k, v in status.items():
        if k != "config":
            print(f"  {k}: {v}")
    print(f"\nCurrent volume: {av.get_system_volume()}%")
    print(f"Media playing: {av.is_media_playing()}")
    print(f"Night time: {av.is_night_time()}")

    print("\n--- Testing prepare/restore cycle ---")
    info = av.prepare_for_speech()
    print(f"Prepared: {info}")
    time.sleep(2)
    av.restore_after_speech()
    print(f"Restored -> {av.get_system_volume()}%")
