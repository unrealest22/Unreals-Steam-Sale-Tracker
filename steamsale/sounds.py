import os
import sys
import math
import wave
import struct
import ctypes

from .config import SOUNDS_DIR

## ─── Get base path (handles both source and frozen exe) ──
if getattr(sys, 'frozen', False):
    # PyInstaller extracts to _MEIPASS. We look in the 'steamsale' subfolder.
    BASE_PATH = os.path.join(sys._MEIPASS, "steamsale")
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# ─── Built-in Sounds Config ──
BUILTIN_SOUNDS = {
    "none": "None (Silent)",
    "coin": "Coin",
    "alert": "Alert",
    "chime": "Chime",
    "powerup": "Power Up",
    # Custom Built-In sounds, the unreal special:
    "fartsound": "Fart",
    "ButterflyDing": "Ding",
    "barkfart": "Bark & Fart"
}

# ─── Generate the default WAV files on first run ──
def generate_builtin_sounds():
    sounds = {
        "coin": [(988, 80), (1319, 200)],
        "alert": [(784, 100), (523, 100), (392, 250)],
        "chime": [(1319, 150), (988, 150), (659, 350)],
        "powerup": [(523, 80), (659, 80), (784, 80), (1047, 250)]
    }
    sample_rate = 44100
    for name, freq_data in sounds.items():
        path = os.path.join(SOUNDS_DIR, f"{name}.wav")
        if os.path.exists(path):
            continue
        try:
            with wave.open(path, 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                for freq, dur_ms in freq_data:
                    num_samples = int(sample_rate * dur_ms / 1000)
                    fade_samples = min(int(sample_rate * 0.01), num_samples // 2)
                    for i in range(num_samples):
                        env = 1.0
                        if i < fade_samples:
                            env = i / fade_samples
                        elif i > num_samples - fade_samples:
                            env = (num_samples - i) / fade_samples
                        env = max(0.0, min(1.0, env))
                        sample = int(32767 * 0.3 * env * math.sin(2 * math.pi * freq * i / sample_rate))
                        wav.writeframes(struct.pack('<h', sample))
        except Exception:
            pass

# ─── Audio Player ──
def play_notification_sound(config):
    sound = config.get("notification_sound", "builtin:coin")
    if sound == "none" or not sound:
        return

    path = None
    if sound.startswith("builtin:"):
        name = sound[8:]
        # Check if it's a generated WAV first
        wav_path = os.path.join(SOUNDS_DIR, f"{name}.wav")
        if os.path.exists(wav_path):
            path = wav_path
        else:
            # Otherwise, look for the bundled MP3
            path = os.path.join(BASE_PATH, f"{name}.mp3")
    else:
        # Custom user file
        path = sound

    if not path or not os.path.exists(path):
        print(f"[WARN] sound file not found: {path}")
        return

    try:
        if sys.platform == "win32":
            if path.lower().endswith('.mp3'):
                # Use Windows MCI to play MP3 without opening any windows
                winmm = ctypes.windll.winmm
                winmm.mciSendStringW(u"close all", None, 0, None)
                winmm.mciSendStringW(f'open "{path}" type mpegvideo alias mp3', None, 0, None)
                winmm.mciSendStringW(u"play mp3", None, 0, None)
            else:
                # It's a WAV, use winsound directly
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            os.system(f"afplay '{path}' &")
        else:
            os.system(f"aplay '{path}' &")
    except Exception as e:
        print(f"[ERROR] sound playback: {e}")

# Generate sounds on import
generate_builtin_sounds()