"""
Volume Configuration for Friday's Adaptive Volume Control
==========================================================

Edit these values to customize volume behavior.
All volume values are percentages (0–100).

This file is imported by adaptive_volume.py at startup.
"""

VOLUME_CONFIG = {
    # -- CASE A: Media is playing (YouTube, Music, Movies, etc.) --
    # System volume is ducked to this while Friday speaks
    "media_duck_volume": 30,
    # Friday's effective reply volume target
    "media_friday_volume": 40,

    # -- CASE B: Explicit "Friday" call (no media / any situation) --
    # Friday's reply volume target
    "explicit_friday_volume": 35,
    # If system volume is below this, temporarily raise it
    "explicit_min_system_volume": 30,

    # ── Fade / Transition Settings ──
    # Smooth fade between volume levels (True/False)
    "fade_enabled": True,
    # Number of intermediate volume steps during a fade
    "fade_steps": 10,
    # Total fade duration in milliseconds
    "fade_duration_ms": 300,

    # ── Media Detection ──
    # Peak audio level threshold to consider "media is playing" (0.0–1.0)
    # Lower = more sensitive, Higher = less sensitive
    "media_playing_threshold": 0.01,

    # ── Night Mode ──
    # Reduce all target volumes during night hours
    "night_mode_enabled": True,
    # Night window start (24h format)
    "night_start_hour": 22,
    # Night window end (24h format)
    "night_end_hour": 7,
    # Multiply all target volumes by this during night hours
    "night_volume_multiplier": 0.6,

    # -- Audio Ducking (Per-App Volume Control) --
    # When wake word is detected, duck OTHER apps (Spotify, Chrome, etc.)
    # while JARVIS's own audio stays at full volume
    # DISABLED by default: if JARVIS crashes, apps stay ducked permanently
    "ducking_enabled": False,
    # Duck other apps to this fraction of their current volume (0.0-1.0)
    # 0.50 = reduce to 50% of their volume (safer than 15%)
    "ducking_level": 0.50,
    # How fast to duck (ms). Lower = faster reaction on wake word
    "ducking_fade_ms": 150,
    # Fade steps for ducking transitions
    "ducking_fade_steps": 5,
    # Processes to always duck (even if not producing audio)
    # Empty list = duck all non-Python processes
    "ducking_target_processes": [],
    # Processes to NEVER duck (besides Python itself)
    "ducking_exclude_processes": [],
}
