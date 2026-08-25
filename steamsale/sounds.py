import os
import sys
import math
import wave
import struct
import ctypes

from .config import SOUNDS_DIR

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.join(sys._MEIPASS, "steamsale")
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

BUILTIN_SOUNDS = {
    # Put ur funny note here
    "none": "None (Silent)",
    "coin": "Coin",
    "alert": "Alert",
    "chime": "Chime",
    "powerup": "Power Up",
    "fartsound": "Fart",
    "ButterflyDing": "Ding",
    "barkfart": "Bark & Fart"
}
     # I found out you can generate sounds with like frequencies n shit, so sick
def generate_builtin_sounds():
    # these are just sine waves, nothing fancy. they sound okay i guess
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

def play_notification_sound(config):
    sound = config.get("notification_sound", "builtin:coin")
    if sound == "none" or not sound:
        return

    path = None
    if sound.startswith("builtin:"):
        name = sound[8:]
        wav_path = os.path.join(SOUNDS_DIR, f"{name}.wav")
        if os.path.exists(wav_path):
            path = wav_path
        else:
            path = os.path.join(BASE_PATH, f"{name}.mp3")
    else:
        path = sound

    if not path or not os.path.exists(path):
        print(f"[WARN] sound file not found: {path}")
        return

    try:
        if sys.platform == "win32":
            if path.lower().endswith('.mp3'):
                winmm = ctypes.windll.winmm
                winmm.mciSendStringW(u"close all", None, 0, None)
                winmm.mciSendStringW(f'open "{path}" type mpegvideo alias mp3', None, 0, None)
                winmm.mciSendStringW(u"play mp3", None, 0, None)
            else:
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            os.system(f"afplay '{path}' &")
        else:
            os.system(f"aplay '{path}' &")
    except Exception as e:
        print(f"[ERROR] sound playback: {e}")

generate_builtin_sounds()