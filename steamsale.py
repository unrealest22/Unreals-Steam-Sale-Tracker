import sys
import json
import os
import time
import threading
import urllib.request
import urllib.parse
import wave
import struct
import math
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QSystemTrayIcon, QMenu, QAction, QMessageBox, QFrame,
    QScrollArea, QGraphicsDropShadowEffect, QStackedWidget,
    QSizePolicy, QGridLayout, QFileDialog, QSpacerItem, QFormLayout
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, QRect, pyqtSignal, QObject, QPoint
)
from PyQt5.QtGui import QIcon, QColor, QFont, QPixmap, QPalette, QCursor, QPainter

APP_DIR = os.path.join(os.path.expanduser("~"), ".steam_sale_tracker")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
SOUNDS_DIR = os.path.join(APP_DIR, "sounds")
os.makedirs(APP_DIR, exist_ok=True)
os.makedirs(SOUNDS_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "cc": "US",
    "run_in_background": True,
    "run_on_startup": False,
    "tracked_games": [],
    "check_interval": 300,
    "last_prices": {},
    "notification_sound": "builtin:coin"
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(json.load(f))
            return cfg
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

BUILTIN_SOUNDS = {
    "none": "None (Silent)",
    "coin": "Coin",
    "alert": "Alert",
    "chime": "Chime",
    "powerup": "Power Up"
}

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

def play_notification_sound(config):
    sound = config.get("notification_sound", "builtin:coin")
    if sound == "none" or not sound:
        return
    if sound.startswith("builtin:"):
        name = sound[8:]
        path = os.path.join(SOUNDS_DIR, f"{name}.wav")
    else:
        path = sound
    if not os.path.exists(path):
        return
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            os.system(f"afplay '{path}' &")
        else:
            os.system(f"aplay '{path}' &")
    except Exception:
        pass

generate_builtin_sounds()

STEAM_STORE_API = "https://store.steampowered.com/api/appdetails"
STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch"
STEAM_FEATURED_API = "https://store.steampowered.com/api/featuredcategories"
STEAM_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"

CC_MAP = {
    "US": ("USD", "$"), "PH": ("PHP", "₱"), "GB": ("GBP", "£"),
    "EU": ("EUR", "€"), "JP": ("JPY", "¥"), "AU": ("AUD", "A$"),
    "CA": ("CAD", "C$"), "IN": ("INR", "₹"), "BR": ("BRL", "R$"),
    "SG": ("SGD", "S$"), "MY": ("MYR", "RM"), "ID": ("IDR", "Rp"),
    "TH": ("THB", "฿"), "VN": ("VND", "₫"), "KR": ("KRW", "₩"),
    "RU": ("RUB", "₽"), "TR": ("TRY", "₺"), "ZA": ("ZAR", "R"),
    "MX": ("MXN", "Mex$"), "NZ": ("NZD", "NZ$"), "CH": ("CHF", "CHf"),
    "HK": ("HKD", "HK$"),
}

DLC_TYPES = {"dlc", "music", "demo", "tool", "mod", "video", "series", "episode"}

def get_currency_info(cc):
    return CC_MAP.get(cc, ("USD", "$"))

def format_price(price, symbol):
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0
    if price == 0:
        return f"{symbol}0.00"
    return f"{symbol}{price:,.2f}"

def fetch_json(url, retries=4, delay=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[ERROR] fetch attempt {i+1}/{retries} for {url}: {e}")
            if i < retries - 1:
                time.sleep(delay)
    return None

def search_game_by_name(name, cc="US"):
    params = urllib.parse.urlencode({"term": name, "l": "english", "cc": cc})
    url = f"{STEAM_SEARCH_API}?{params}"
    data = fetch_json(url)
    if not data or "items" not in data:
        return []
    return [{"appid": str(item["id"]), "name": item["name"]} for item in data["items"]]

def get_game_details(appid, cc="US"):
    params = urllib.parse.urlencode({"appids": appid, "cc": cc, "l": "english"})
    url = f"{STEAM_STORE_API}?{params}"
    data = fetch_json(url)
    if not data or appid not in data:
        return None
    app_data = data[appid]
    if not app_data.get("success"):
        return None
    return app_data["data"]

def fetch_featured_games(cc="US"):
    url = f"{STEAM_FEATURED_API}?cc={cc}&l=english"
    data = fetch_json(url)
    if not data:
        return []
    specials = data.get("specials", {})
    items = specials.get("items", []) if isinstance(specials, dict) else specials if isinstance(specials, list) else []
    results = []
    for item in items[:8]:
        appid = str(item.get("id", ""))
        if not appid:
            continue
        name = item.get("name", "Unknown")
        discount = item.get("discount", 0)
        if isinstance(discount, str):
            try: discount = int(discount)
            except: discount = 0
        final_price = item.get("final_price", 0)
        if isinstance(final_price, str):
            try: final_price = int(final_price)
            except: final_price = 0
        final_price = final_price / 100
        original_price = item.get("original_price", final_price * 100)
        if isinstance(original_price, str):
            try: original_price = int(original_price)
            except: original_price = int(final_price * 100)
        original_price = original_price / 100
        header_image = item.get("header_image", f"{STEAM_CDN}/{appid}/header.jpg")
        results.append({
            "appid": appid, "name": name, "discount": discount,
            "final_price": final_price, "original_price": original_price,
            "header_image": header_image
        })
    return results

def get_editions(appid, cc="US"):
    details = get_game_details(appid, cc)
    if not details:
        return [], None, None
    game_name = details.get("name", "Unknown")
    app_type = details.get("type", "game")
    editions = []
    if details.get("is_free"):
        editions.append({"name": "Free to Play", "packageid": None, "price_final": 0, "price_original": 0, "discount_pct": 0, "is_free": True})
        return editions, game_name, app_type

    price_overview = details.get("price_overview", {})
    reliable_discount = 0
    if price_overview:
        reliable_discount = price_overview.get("discount_percent", 0)
        if isinstance(reliable_discount, str):
            try: reliable_discount = int(reliable_discount)
            except: reliable_discount = 0

    package_groups = details.get("package_groups", [])
    if not package_groups:
        if price_overview:
            editions.append({
                "name": "Standard Edition", "packageid": None,
                "price_final": price_overview.get("final", 0) / 100,
                "price_original": price_overview.get("initial", 0) / 100,
                "discount_pct": reliable_discount, "is_free": False
            })
        else:
            editions.append({"name": "Standard Edition", "packageid": None, "price_final": 0, "price_original": 0, "discount_pct": 0, "is_free": False})
        return editions, game_name, app_type

    for group in package_groups:
        for sub in group.get("subs", []):
            edition_name = sub.get("option_text", sub.get("name", "Standard Edition"))
            if " - " in edition_name:
                edition_name = edition_name.rsplit(" - ", 1)[0]
            if edition_name.lower().startswith("buy "):
                edition_name = edition_name[4:].strip()
            if edition_name.strip().lower() == game_name.strip().lower():
                edition_name = "Standard Edition"

            price_final = sub.get("price_in_cents_with_discount", 0)
            if isinstance(price_final, str):
                try: price_final = int(price_final)
                except: price_final = 0
            price_final = price_final / 100

            discount_pct = reliable_discount
            if discount_pct == 0:
                discount_pct = sub.get("percent_savings", 0)
                if isinstance(discount_pct, str):
                    try: discount_pct = int(discount_pct)
                    except: discount_pct = 0

            if discount_pct > 0 and price_final > 0:
                price_original = round(price_final / (1 - discount_pct / 100), 2)
            else:
                price_original = price_final

            editions.append({
                "name": edition_name, "packageid": str(sub.get("packageid", "")),
                "price_final": price_final, "price_original": price_original,
                "discount_pct": discount_pct, "is_free": False
            })

    seen = set()
    unique_editions = []
    for ed in editions:
        if ed["name"] not in seen:
            seen.add(ed["name"])
            unique_editions.append(ed)
    return unique_editions, game_name, app_type

def fetch_price_for_game(appid, edition_name, cc):
    details = get_game_details(appid, cc)
    if not details:
        return None

    game_name = details.get("name", "Unknown")
    currency, symbol = get_currency_info(cc)

    if details.get("is_free"):
        return {"is_free": True, "on_sale": False, "discount_pct": 0,
                "price_final": 0, "price_original": 0,
                "symbol": symbol, "currency": currency, "game_name": game_name}

    price_overview = details.get("price_overview")
    if price_overview:
        discount = price_overview.get("discount_percent", 0)
        if isinstance(discount, str):
            try: discount = int(discount)
            except: discount = 0
        final = price_overview.get("final", 0)
        if isinstance(final, str):
            try: final = int(final)
            except: final = 0
        initial = price_overview.get("initial", 0)
        if isinstance(initial, str):
            try: initial = int(initial)
            except: initial = 0

        if edition_name.lower() == "standard edition":
            return {"is_free": False, "on_sale": discount > 0,
                    "discount_pct": discount,
                    "price_final": final / 100,
                    "price_original": initial / 100,
                    "symbol": symbol, "currency": currency,
                    "game_name": game_name}

        package_groups = details.get("package_groups", [])
        for group in package_groups:
            for sub in group.get("subs", []):
                ed_name = sub.get("option_text", sub.get("name", "Standard Edition"))
                if " - " in ed_name:
                    ed_name = ed_name.rsplit(" - ", 1)[0]
                if ed_name.lower().startswith("buy "):
                    ed_name = ed_name[4:].strip()
                if ed_name.strip().lower() == game_name.strip().lower():
                    ed_name = "Standard Edition"

                if ed_name.lower() == edition_name.lower():
                    sub_price = sub.get("price_in_cents_with_discount", 0)
                    if isinstance(sub_price, str):
                        try: sub_price = int(sub_price)
                        except: sub_price = 0
                    sub_price = sub_price / 100

                    if discount > 0 and sub_price > 0:
                        sub_original = round(sub_price / (1 - discount / 100), 2)
                    else:
                        sub_original = sub_price

                    return {"is_free": False, "on_sale": discount > 0,
                            "discount_pct": discount,
                            "price_final": sub_price,
                            "price_original": sub_original,
                            "symbol": symbol, "currency": currency,
                            "game_name": game_name}

        return {"is_free": False, "on_sale": discount > 0,
                "discount_pct": discount,
                "price_final": final / 100,
                "price_original": initial / 100,
                "symbol": symbol, "currency": currency,
                "game_name": game_name}

    package_groups = details.get("package_groups", [])
    for group in package_groups:
        for sub in group.get("subs", []):
            ed_name = sub.get("option_text", sub.get("name", "Standard Edition"))
            if " - " in ed_name:
                ed_name = ed_name.rsplit(" - ", 1)[0]
            if ed_name.lower().startswith("buy "):
                ed_name = ed_name[4:].strip()
            if ed_name.strip().lower() == game_name.strip().lower():
                ed_name = "Standard Edition"

            if ed_name.lower() == edition_name.lower() or edition_name.lower() == "standard edition":
                discount = sub.get("percent_savings", 0)
                if isinstance(discount, str):
                    try: discount = int(discount)
                    except: discount = 0
                price_final = sub.get("price_in_cents_with_discount", 0)
                if isinstance(price_final, str):
                    try: price_final = int(price_final)
                    except: price_final = 0
                price_final = price_final / 100
                if discount > 0 and price_final > 0:
                    price_original = round(price_final / (1 - discount / 100), 2)
                else:
                    price_original = price_final
                return {"is_free": False, "on_sale": discount > 0,
                        "discount_pct": discount,
                        "price_final": price_final,
                        "price_original": price_original,
                        "symbol": symbol, "currency": currency,
                        "game_name": game_name}

    return None

STEAM_STYLESHEET = """
QWidget { background-color: #1b2838; color: #c7d5e0; font-family: "Segoe UI", "Arial", sans-serif; font-size: 14px; }
QMainWindow, QWidget#mainWidget { background-color: #1b2838; }
QLabel { color: #c7d5e0; }
QLabel#titleLabel { color: #ffffff; font-size: 22px; font-weight: bold; }
QLabel#sectionLabel { color: #66c0f4; font-size: 13px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
QLabel#gameNameLabel { color: #ffffff; font-size: 16px; font-weight: bold; }
QLabel#editionNameLabel { color: #c7d5e0; font-size: 13px; font-style: italic; }
QLabel#priceLabel { color: #beee11; font-size: 18px; font-weight: bold; }
QLabel#discountLabel { color: #4c6b22; background-color: #beee11; font-size: 16px; font-weight: bold; padding: 4px 10px; border-radius: 3px; }
QLabel#discountLabelSmall { color: #4c6b22; background-color: #beee11; font-size: 13px; font-weight: bold; padding: 3px 8px; border-radius: 3px; }
QLabel#noDiscountLabel { color: #8f98a0; font-size: 14px; }
QLabel#statusLabel { color: #8f98a0; font-size: 12px; }
QLabel#loadingLabel { color: #66c0f4; font-size: 14px; font-weight: bold; }
QLabel#errorLabel { color: #ff6b6b; font-size: 14px; font-weight: bold; }
QLabel#popularNameLabel { color: #ffffff; font-size: 14px; font-weight: bold; }
QLabel#popularOrigLabel { color: #8f98a0; font-size: 12px; }
QLabel#typeBadgeLabel { color: #66c0f4; background-color: #2a475e; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 2px; }
QLabel#origPriceStrikethrough { color: #8f98a0; font-size: 14px; text-decoration: line-through; }
QLabel#finalPriceGreen { color: #beee11; font-size: 16px; font-weight: bold; }
QLabel#priceNormal { color: #c7d5e0; font-size: 16px; font-weight: bold; }
QLabel#settingLabel { color: #c7d5e0; font-size: 14px; }
QLineEdit { background-color: #316282; color: #ffffff; border: 1px solid #2a475e; border-radius: 3px; padding: 10px 14px; font-size: 14px; selection-background-color: #66c0f4; }
QLineEdit:focus { border: 1px solid #66c0f4; background-color: #3d6f8f; }
QLineEdit::placeholder { color: #8fa7b8; }
QPushButton { background-color: #2a475e; color: #66c0f4; border: 1px solid #2a475e; border-radius: 3px; padding: 10px 24px; font-size: 14px; font-weight: bold; }
QPushButton:hover { background-color: #316282; color: #ffffff; }
QPushButton:pressed { background-color: #1b2838; color: #66c0f4; }
QPushButton#primaryBtn { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #75b022, stop:1 #588a1b); color: #ffffff; border: 1px solid #75b022; border-radius: 3px; padding: 10px 28px; font-size: 14px; font-weight: bold; }
QPushButton#primaryBtn:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8bc62f, stop:1 #6ba320); }
QPushButton#primaryBtn:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6ba320, stop:1 #4e7a17); }
QPushButton#trackBtn { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #75b022, stop:1 #588a1b); color: #ffffff; border: 1px solid #75b022; border-radius: 3px; padding: 6px 16px; font-size: 13px; font-weight: bold; min-width: 70px; }
QPushButton#trackBtn:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8bc62f, stop:1 #6ba320); }
QPushButton#trackBtn:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6ba320, stop:1 #4e7a17); }
QPushButton#navBtn { background-color: transparent; color: #8fa7b8; border: none; border-radius: 0px; padding: 14px 24px; font-size: 13px; font-weight: bold; text-align: left; }
QPushButton#navBtn:hover { color: #ffffff; background-color: #223445; }
QPushButton#navBtn:checked { color: #66c0f4; background-color: #1b2838; border-left: 3px solid #66c0f4; }
QComboBox { background-color: #316282; color: #ffffff; border: 1px solid #2a475e; border-radius: 3px; padding: 8px 12px; min-width: 180px; }
QComboBox:hover { border: 1px solid #66c0f4; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #66c0f4; margin-right: 8px; }
QComboBox QAbstractItemView { background-color: #2a475e; color: #c7d5e0; border: 1px solid #1b2838; selection-background-color: #316282; selection-color: #ffffff; outline: none; padding: 4px; }
QCheckBox { color: #c7d5e0; font-size: 14px; spacing: 10px; padding: 6px 0; }
QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #2a475e; border-radius: 3px; background-color: #1b2838; }
QCheckBox::indicator:hover { border: 2px solid #66c0f4; }
QCheckBox::indicator:checked { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #75b022, stop:1 #588a1b); border: 2px solid #75b022; }
QScrollArea { background-color: #1b2838; border: none; }
QScrollArea > QWidget > QWidget { background-color: #1b2838; }
QScrollBar:vertical { background-color: #1b2838; width: 10px; border: none; margin: 0; }
QScrollBar::handle:vertical { background-color: #2a475e; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background-color: #316282; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
QScrollBar:horizontal { height: 0px; background: none; border: none; }
QFrame#gameCard { background-color: #16202d; border: 1px solid #2a475e; border-radius: 6px; }
QFrame#gameCard:hover { border: 1px solid #66c0f4; }
QFrame#editionCard { background-color: #1b2838; border: 1px solid #2a475e; border-radius: 4px; }
QFrame#editionCard:hover { border: 1px solid #66c0f4; }
QFrame#popularCard { background-color: #16202d; border: 1px solid #2a475e; border-radius: 6px; }
QFrame#popularCard:hover { border: 1px solid #66c0f4; }
QFrame#separator { background-color: #2a475e; max-height: 1px; min-height: 1px; }
QFrame#navBar { background-color: #171a21; border-right: 1px solid #000000; }
QMenu { background-color: #2a475e; border: 1px solid #1b2838; color: #c7d5e0; padding: 6px; }
QMenu::item { padding: 8px 30px 8px 20px; border-radius: 3px; }
QMenu::item:selected { background-color: #316282; color: #ffffff; }
QMenu::separator { height: 1px; background-color: #1b2838; margin: 4px 8px; }
"""

def slide_in_from_right(widget, duration=250):
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    target_pos = widget.pos()
    anim.setStartValue(target_pos + QPoint(30, 0))
    anim.setEndValue(target_pos)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim

class ImageLoader(QObject):
    image_loaded = pyqtSignal(str, QPixmap)
    def load(self, url, appid):
        def _fetch():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                self.image_loaded.emit(appid, pixmap)
            except: pass
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

class PriceChecker(QObject):
    sale_detected = pyqtSignal(str, str, str, int, float, str)
    check_done = pyqtSignal()
    status_update = pyqtSignal(str)
    price_fetched = pyqtSignal(str, str, dict)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                self._check_all()
            except Exception as e:
                print(f"[ERROR] checker loop: {e}")
            time.sleep(self.config.get("check_interval", 300))

    def _check_all(self):
        games = self.config.get("tracked_games", [])
        if not games:
            return
        self.status_update.emit(f"Checking {len(games)} tracked game(s)...")
        cc = self.config.get("cc", "US")
        last_prices = self.config.get("last_prices", {})
        for game in games:
            appid = game["appid"]
            edition_name = game.get("edition", "Standard Edition")
            price_info = fetch_price_for_game(appid, edition_name, cc)
            if not price_info:
                self.price_fetched.emit(appid, edition_name, {"error": True})
                continue
            game_name = price_info.get("game_name", game.get("name", "Unknown"))
            key = f"{appid}_{edition_name}_{cc}"
            was_on_sale = last_prices.get(key, {}).get("on_sale", False)
            prev_discount = last_prices.get(key, {}).get("discount_pct", 0)
            symbol = price_info["symbol"]
            is_newly_tracked = key not in last_prices
            if price_info["on_sale"] and (is_newly_tracked or not was_on_sale or prev_discount != price_info["discount_pct"]):
                self.sale_detected.emit(appid, game_name, edition_name, price_info["discount_pct"], price_info["price_final"], symbol)
            last_prices[key] = {
                "on_sale": price_info["on_sale"],
                "discount_pct": price_info["discount_pct"],
                "price_final": price_info["price_final"],
                "price_original": price_info["price_original"],
                "is_free": price_info.get("is_free", False),
                "symbol": symbol
            }
            self.price_fetched.emit(appid, edition_name, last_prices[key])
        self.config["last_prices"] = last_prices
        save_config(self.config)
        self.check_done.emit()
        self.status_update.emit(f"Last checked: {datetime.now().strftime('%H:%M:%S')}")

    def check_single(self, appid, edition_name, game_name=""):
        def _check():
            time.sleep(2)
            cc = self.config.get("cc", "US")
            price_info = fetch_price_for_game(appid, edition_name, cc)
            if not price_info:
                self.price_fetched.emit(appid, edition_name, {"error": True})
                self.status_update.emit(f"Could not fetch price for {game_name or appid}")
                return
            actual_name = price_info.get("game_name", game_name)
            symbol = price_info["symbol"]
            key = f"{appid}_{edition_name}_{cc}"
            last_prices = self.config.get("last_prices", {})
            last_prices[key] = {
                "on_sale": price_info["on_sale"],
                "discount_pct": price_info["discount_pct"],
                "price_final": price_info["price_final"],
                "price_original": price_info["price_original"],
                "is_free": price_info.get("is_free", False),
                "symbol": symbol
            }
            self.config["last_prices"] = last_prices
            save_config(self.config)
            self.price_fetched.emit(appid, edition_name, last_prices[key])
            if price_info["on_sale"]:
                self.sale_detected.emit(appid, actual_name, edition_name, price_info["discount_pct"], price_info["price_final"], symbol)
            elif price_info.get("is_free"):
                self.status_update.emit(f"{actual_name} is Free to Play")
            else:
                self.status_update.emit(f"Now tracking: {actual_name} — {format_price(price_info['price_final'], symbol)}")
        t = threading.Thread(target=_check, daemon=True)
        t.start()

class GameCard(QFrame):
    remove_clicked = pyqtSignal(str, str)

    def __init__(self, appid, name, edition, price_info=None):
        super().__init__()
        self.appid = appid
        self.edition = edition
        self.setObjectName("gameCard")
        self.setFixedHeight(100)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(3)
        self.name_label = QLabel(name)
        self.name_label.setObjectName("gameNameLabel")
        left.addWidget(self.name_label)
        self.edition_label = QLabel(edition)
        self.edition_label.setObjectName("editionNameLabel")
        left.addWidget(self.edition_label)
        self.status_label = QLabel(f"App ID: {appid} • Fetching price...")
        self.status_label.setObjectName("statusLabel")
        left.addWidget(self.status_label)
        left.addStretch()
        layout.addLayout(left)
        self.right_layout = QHBoxLayout()
        self.right_layout.setSpacing(12)
        self.price_widget = None
        self._update_price_display(price_info)
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(32, 32)
        remove_btn.setStyleSheet("QPushButton { background-color: transparent; color: #8f98a0; border: none; font-size: 16px; font-weight: bold; } QPushButton:hover { color: #ff4444; }")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.appid, self.edition))
        self.right_layout.addWidget(remove_btn)
        layout.addLayout(self.right_layout)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def update_price(self, price_info):
        self._update_price_display(price_info)
        status_text = f"App ID: {self.appid}"
        if price_info and not price_info.get("error"):
            if price_info.get("is_free"):
                status_text += " • Free to Play"
            elif price_info.get("on_sale"):
                status_text += " • On Sale"
            else:
                status_text += f" • {format_price(price_info.get('price_final', 0), price_info.get('symbol', '$'))}"
        elif price_info and price_info.get("error"):
            status_text += " • Price Unavailable"
        self.status_label.setText(status_text)

    def _update_price_display(self, price_info):
        if self.price_widget:
            self.price_widget.deleteLater()
            self.price_widget = None
        if not price_info:
            loading = QLabel("Loading...")
            loading.setObjectName("loadingLabel")
            self.price_widget = loading
            self.right_layout.insertWidget(0, loading)
            return
        if price_info.get("error"):
            err = QLabel("Unavailable")
            err.setObjectName("errorLabel")
            self.price_widget = err
            self.right_layout.insertWidget(0, err)
            return
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)
        symbol = price_info.get("symbol", "$")
        price_final = price_info.get("price_final", 0)
        price_original = price_info.get("price_original", 0)
        discount_pct = price_info.get("discount_pct", 0)
        if price_info.get("is_free"):
            free = QLabel("FREE")
            free.setObjectName("discountLabel")
            free.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(free)
        elif price_info.get("on_sale"):
            disc = QLabel(f"-{discount_pct}%")
            disc.setObjectName("discountLabel")
            disc.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(disc)
            orig = QLabel(format_price(price_original, symbol))
            orig.setObjectName("origPriceStrikethrough")
            container_layout.addWidget(orig)
            final = QLabel(format_price(price_final, symbol))
            final.setObjectName("finalPriceGreen")
            container_layout.addWidget(final)
        else:
            price = QLabel(format_price(price_final, symbol))
            price.setObjectName("priceNormal")
            container_layout.addWidget(price)
        self.price_widget = container
        self.right_layout.insertWidget(0, container)

class SearchResultCard(QFrame):
    track_clicked = pyqtSignal(str, str, str)
    editions_loaded = pyqtSignal(list, str, str)
    editions_failed = pyqtSignal(str)
    type_determined = pyqtSignal(str, str)

    def __init__(self, appid, name, cc, delay=0):
        super().__init__()
        self.appid = appid
        self.game_name = name
        self.cc = cc
        self.editions = []
        self.app_type = "game"
        self.setObjectName("gameCard")
        self.editions_loaded.connect(self._on_editions_loaded)
        self.editions_failed.connect(self._on_editions_failed)
        self._build_ui()
        self._load_editions(delay)

    def _build_ui(self):
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(16, 14, 16, 14)
        self.layout_main.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.name_label = QLabel(self.game_name)
        self.name_label.setObjectName("gameNameLabel")
        top.addWidget(self.name_label)
        self.type_badge = QLabel()
        self.type_badge.setObjectName("typeBadgeLabel")
        self.type_badge.setVisible(False)
        top.addWidget(self.type_badge)
        top.addStretch()
        self.id_label = QLabel(f"App ID: {self.appid}")
        self.id_label.setObjectName("statusLabel")
        top.addWidget(self.id_label)
        self.loading_label = QLabel("Loading editions...")
        self.loading_label.setObjectName("loadingLabel")
        top.addWidget(self.loading_label)
        self._dot_count = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_loading_text)
        self._spinner_timer.start(500)
        self.layout_main.addLayout(top)
        self.editions_container = QVBoxLayout()
        self.editions_container.setSpacing(8)
        self.layout_main.addLayout(self.editions_container)

    def _update_loading_text(self):
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self.loading_label.setText(f"Loading editions{dots}")

    def _load_editions(self, delay=0):
        def _fetch():
            if delay > 0:
                time.sleep(delay)
            try:
                editions, game_name, app_type = get_editions(self.appid, self.cc)
                if editions:
                    self.editions_loaded.emit(editions, game_name or self.game_name, app_type or "game")
                else:
                    self.editions_failed.emit("No editions found")
            except Exception as e:
                self.editions_failed.emit(str(e))
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

    def _on_editions_loaded(self, editions, game_name, app_type):
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.editions = editions
        self.app_type = app_type
        if game_name and game_name != self.game_name:
            self.game_name = game_name
            self.name_label.setText(game_name)
        if app_type in DLC_TYPES:
            self.type_badge.setText(app_type.upper())
            self.type_badge.setVisible(True)
        self.type_determined.emit(self.appid, app_type)
        if not editions:
            no_ed = QLabel("No purchase options available for this game.")
            no_ed.setObjectName("statusLabel")
            self.editions_container.addWidget(no_ed)
        else:
            for ed in editions:
                self._add_edition_row(ed)
        self.adjustSize()
        self.updateGeometry()
        if self.parent():
            self.parent().updateGeometry()

    def _on_editions_failed(self, error_msg):
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.type_determined.emit(self.appid, "game")
        error_frame = QFrame()
        error_frame.setObjectName("editionCard")
        error_frame.setFixedHeight(52)
        err_layout = QHBoxLayout(error_frame)
        err_layout.setContentsMargins(12, 8, 12, 8)
        err_label = QLabel(f"Failed to load: {error_msg}")
        err_label.setStyleSheet("color: #ff6b6b; font-size: 13px;")
        err_layout.addWidget(err_label)
        err_layout.addStretch()
        retry_btn = QPushButton("Retry")
        retry_btn.setObjectName("trackBtn")
        retry_btn.setCursor(QCursor(Qt.PointingHandCursor))
        retry_btn.setFixedWidth(90)
        retry_btn.clicked.connect(self._retry)
        err_layout.addWidget(retry_btn)
        self.editions_container.addWidget(error_frame)
        self.adjustSize()
        self.updateGeometry()
        if self.parent():
            self.parent().updateGeometry()

    def _retry(self):
        while self.editions_container.count():
            item = self.editions_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.loading_label.setVisible(True)
        self.loading_label.setText("Loading editions...")
        self._spinner_timer.start(500)
        def _delayed_retry():
            time.sleep(1)
            self._load_editions()
        t = threading.Thread(target=_delayed_retry, daemon=True)
        t.start()

    def _add_edition_row(self, edition):
        row = QFrame()
        row.setObjectName("editionCard")
        row.setFixedHeight(52)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(12)
        ed_name = QLabel(edition["name"])
        ed_name.setStyleSheet("color: #c7d5e0; font-size: 13px; font-weight: bold;")
        ed_name.setMinimumWidth(200)
        ed_name.setToolTip(edition["name"])
        row_layout.addWidget(ed_name)
        row_layout.addStretch()
        currency, symbol = get_currency_info(self.cc)
        if edition.get("is_free"):
            price_label = QLabel("FREE")
            price_label.setObjectName("discountLabelSmall")
            price_label.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(price_label)
        elif edition["discount_pct"] > 0:
            disc = QLabel(f"-{edition['discount_pct']}%")
            disc.setObjectName("discountLabelSmall")
            disc.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(disc)
            orig = QLabel(format_price(edition["price_original"], symbol))
            orig.setStyleSheet("color: #8f98a0; font-size: 13px; text-decoration: line-through;")
            row_layout.addWidget(orig)
            final = QLabel(format_price(edition["price_final"], symbol))
            final.setStyleSheet("color: #beee11; font-size: 15px; font-weight: bold;")
            row_layout.addWidget(final)
        else:
            price = QLabel(format_price(edition["price_final"], symbol))
            price.setStyleSheet("color: #8f98a0; font-size: 14px;")
            row_layout.addWidget(price)
        track_btn = QPushButton("Track")
        track_btn.setObjectName("trackBtn")
        track_btn.setCursor(QCursor(Qt.PointingHandCursor))
        track_btn.setFixedWidth(90)
        track_btn.clicked.connect(
            lambda checked, a=self.appid, n=self.game_name, ed=edition["name"]:
                self.track_clicked.emit(a, n, ed)
        )
        row_layout.addWidget(track_btn)
        self.editions_container.addWidget(row)

class PopularSearchCard(QFrame):
    track_clicked = pyqtSignal(str, str, str)

    def __init__(self, appid, name, discount, final_price, original_price, image_url, cc):
        super().__init__()
        self.appid = appid
        self.game_name = name
        self.cc = cc
        self.setObjectName("popularCard")
        self.setFixedHeight(120)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        self.image_label = QLabel()
        self.image_label.setFixedSize(184, 69)
        self.image_label.setStyleSheet("background-color: #000000; border-radius: 3px;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("...")
        layout.addWidget(self.image_label)
        self.image_loader = ImageLoader()
        self.image_loader.image_loaded.connect(self._on_image_loaded)
        self.image_loader.load(image_url, appid)
        info = QVBoxLayout()
        info.setSpacing(4)
        name_label = QLabel(name)
        name_label.setObjectName("popularNameLabel")
        name_label.setWordWrap(True)
        info.addWidget(name_label)
        currency, symbol = get_currency_info(cc)
        price_row = QHBoxLayout()
        price_row.setSpacing(8)
        if discount > 0:
            disc_label = QLabel(f"-{discount}%")
            disc_label.setObjectName("discountLabelSmall")
            disc_label.setAlignment(Qt.AlignCenter)
            price_row.addWidget(disc_label)
            orig_label = QLabel(format_price(original_price, symbol))
            orig_label.setObjectName("popularOrigLabel")
            orig_label.setStyleSheet("text-decoration: line-through;")
            price_row.addWidget(orig_label)
            final_label = QLabel(format_price(final_price, symbol))
            final_label.setObjectName("finalPriceGreen")
            price_row.addWidget(final_label)
        elif final_price == 0:
            free_label = QLabel("FREE")
            free_label.setObjectName("discountLabelSmall")
            free_label.setAlignment(Qt.AlignCenter)
            price_row.addWidget(free_label)
        else:
            final_label = QLabel(format_price(final_price, symbol))
            final_label.setObjectName("priceNormal")
            price_row.addWidget(final_label)
        price_row.addStretch()
        info.addLayout(price_row)
        info.addStretch()
        layout.addLayout(info, 1)
        track_btn = QPushButton("Track")
        track_btn.setObjectName("trackBtn")
        track_btn.setCursor(QCursor(Qt.PointingHandCursor))
        track_btn.setFixedWidth(90)
        track_btn.clicked.connect(
            lambda checked, a=self.appid, n=self.game_name:
                self.track_clicked.emit(a, n, "Standard Edition")
        )
        layout.addWidget(track_btn, 0, Qt.AlignVCenter)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def _on_image_loaded(self, appid, pixmap):
        if appid == self.appid and not pixmap.isNull():
            scaled = pixmap.scaled(184, 69, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

class SearchPage(QWidget):
    game_added = pyqtSignal(dict)
    popular_loaded = pyqtSignal(list)
    popular_failed = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.popular_games = []
        self.has_searched = False
        self.popular_loaded.connect(self._on_popular_loaded)
        self.popular_failed.connect(self._on_popular_failed)
        self._build_ui()
        self._load_popular()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        title = QLabel("Track a Game")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        subtitle = QLabel("Enter a Steam App ID or game name — editions load automatically per game")
        subtitle.setObjectName("statusLabel")
        layout.addWidget(subtitle)
        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("[GAME ID] or Name of the Game")
        self.search_input.returnPressed.connect(self._do_search)
        self.search_input.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self.search_input)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("primaryBtn")
        search_btn.setCursor(QCursor(Qt.PointingHandCursor))
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setSpacing(16)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.search_section_widget = QWidget()
        self.search_section_layout = QVBoxLayout(self.search_section_widget)
        self.search_section_layout.setSpacing(12)
        self.search_section_layout.setContentsMargins(0, 0, 0, 0)
        self.games_label = QLabel("Games")
        self.games_label.setObjectName("sectionLabel")
        self.search_section_layout.addWidget(self.games_label)
        self.games_container = QVBoxLayout()
        self.games_container.setSpacing(10)
        self.search_section_layout.addLayout(self.games_container)
        self.dlc_section_widget = QWidget()
        self.dlc_section_layout = QVBoxLayout(self.dlc_section_widget)
        self.dlc_section_layout.setSpacing(10)
        self.dlc_section_layout.setContentsMargins(0, 0, 0, 0)
        self.dlc_separator = QFrame()
        self.dlc_separator.setObjectName("separator")
        self.dlc_section_layout.addWidget(self.dlc_separator)
        self.dlc_label = QLabel("Downloadable Content")
        self.dlc_label.setObjectName("sectionLabel")
        self.dlc_section_layout.addWidget(self.dlc_label)
        self.dlc_container = QVBoxLayout()
        self.dlc_container.setSpacing(10)
        self.dlc_section_layout.addLayout(self.dlc_container)
        self.dlc_section_widget.setVisible(False)
        self.search_section_layout.addWidget(self.dlc_section_widget)
        self.search_section_widget.setVisible(False)
        self.results_layout.addWidget(self.search_section_widget)
        self.popular_section_widget = QWidget()
        self.popular_section_layout = QVBoxLayout(self.popular_section_widget)
        self.popular_section_layout.setSpacing(10)
        self.popular_section_layout.setContentsMargins(0, 0, 0, 0)
        popular_header = QHBoxLayout()
        popular_header.setSpacing(12)
        self.popular_label = QLabel("Popular Searches")
        self.popular_label.setObjectName("sectionLabel")
        popular_header.addWidget(self.popular_label)
        popular_header.addStretch()
        self.refresh_popular_btn = QPushButton("Refresh")
        self.refresh_popular_btn.setObjectName("trackBtn")
        self.refresh_popular_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.refresh_popular_btn.setFixedWidth(90)
        self.refresh_popular_btn.clicked.connect(self._load_popular)
        popular_header.addWidget(self.refresh_popular_btn)
        self.popular_section_layout.addLayout(popular_header)
        self.popular_loading_label = QLabel("Loading popular games...")
        self.popular_loading_label.setObjectName("loadingLabel")
        self.popular_section_layout.addWidget(self.popular_loading_label)
        self._popular_dot_count = 0
        self._popular_spinner = QTimer(self)
        self._popular_spinner.timeout.connect(self._update_popular_loading)
        self._popular_spinner.start(500)
        self.popular_container = QVBoxLayout()
        self.popular_container.setSpacing(10)
        self.popular_section_layout.addLayout(self.popular_container)
        self.popular_section_widget.setVisible(True)
        self.results_layout.addWidget(self.popular_section_widget)
        self.results_layout.addStretch()
        self.scroll.setWidget(self.results_widget)
        layout.addWidget(self.scroll)

    def _on_text_changed(self, text):
        if not text.strip() and self.has_searched:
            self.has_searched = False
            self.search_section_widget.setVisible(False)
            self.popular_section_widget.setVisible(True)

    def _update_popular_loading(self):
        self._popular_dot_count = (self._popular_dot_count + 1) % 4
        dots = "." * self._popular_dot_count
        self.popular_loading_label.setText(f"Loading popular games{dots}")

    def _load_popular(self):
        while self.popular_container.count():
            item = self.popular_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.popular_loading_label.setVisible(True)
        self.popular_loading_label.setText("Loading popular games...")
        self._popular_spinner.start(500)
        def _fetch():
            cc = self.config.get("cc", "US")
            games = fetch_featured_games(cc)
            if games:
                self.popular_loaded.emit(games)
            else:
                self.popular_failed.emit()
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

    def _on_popular_loaded(self, games):
        self._popular_spinner.stop()
        self.popular_loading_label.setVisible(False)
        self.popular_games = games
        cc = self.config.get("cc", "US")
        for game in games:
            card = PopularSearchCard(
                game["appid"], game["name"], game["discount"],
                game["final_price"], game["original_price"],
                game["header_image"], cc
            )
            card.track_clicked.connect(self._on_track_clicked)
            self.popular_container.addWidget(card)
        if not games:
            no_pop = QLabel("No popular games available right now.")
            no_pop.setObjectName("statusLabel")
            no_pop.setAlignment(Qt.AlignCenter)
            self.popular_container.addWidget(no_pop)

    def _on_popular_failed(self):
        self._popular_spinner.stop()
        self.popular_loading_label.setVisible(False)
        err = QLabel("Failed to load popular games. Click Refresh to try again.")
        err.setObjectName("statusLabel")
        err.setAlignment(Qt.AlignCenter)
        self.popular_container.addWidget(err)

    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        while self.games_container.count():
            item = self.games_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self.dlc_container.count():
            item = self.dlc_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.dlc_section_widget.setVisible(False)
        self.has_searched = True
        self.search_section_widget.setVisible(True)
        self.popular_section_widget.setVisible(False)
        cc = self.config.get("cc", "US")
        if query.isdigit():
            self._add_search_result_card(query, f"App ID: {query}", 0)
        else:
            results = search_game_by_name(query, cc)
            if not results:
                no_results = QLabel("No games found. Try a different name or App ID.")
                no_results.setObjectName("statusLabel")
                no_results.setAlignment(Qt.AlignCenter)
                self.games_container.addWidget(no_results)
                return
            for i, result in enumerate(results[:10]):
                self._add_search_result_card(result["appid"], result["name"], i * 0.5)

    def _add_search_result_card(self, appid, name, delay=0):
        cc = self.config.get("cc", "US")
        card = SearchResultCard(appid, name, cc, delay=delay)
        card.track_clicked.connect(self._on_track_clicked)
        card.type_determined.connect(self._on_card_type_determined)
        self.games_container.addWidget(card)

    def _on_card_type_determined(self, appid, app_type):
        if app_type not in DLC_TYPES:
            return
        for i in range(self.games_container.count()):
            item = self.games_container.itemAt(i)
            if item.widget() and isinstance(item.widget(), SearchResultCard) and item.widget().appid == appid:
                card = item.widget()
                self.games_container.removeWidget(card)
                self.dlc_container.addWidget(card)
                self.dlc_section_widget.setVisible(True)
                break

    def _on_track_clicked(self, appid, name, edition):
        for g in self.config["tracked_games"]:
            if g["appid"] == appid and g.get("edition", "") == edition:
                return
        game_entry = {"appid": appid, "name": name, "edition": edition}
        self.config["tracked_games"].append(game_entry)
        save_config(self.config)
        self.game_added.emit(game_entry)

    def reload_popular(self):
        self._load_popular()

class TrackedPage(QWidget):
    refresh_requested = pyqtSignal()
    game_removed = pyqtSignal(str, str)
    price_updated = pyqtSignal(str, str, dict)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._card_map = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        header = QHBoxLayout()
        title = QLabel("Tracked Games")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QPushButton("Refresh Prices")
        refresh_btn.setObjectName("primaryBtn")
        refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(refresh_btn)
        layout.addLayout(header)
        self.count_label = QLabel("0 games tracked")
        self.count_label.setObjectName("statusLabel")
        layout.addWidget(self.count_label)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)

    def refresh_cards(self):
        self._card_map.clear()
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        games = self.config.get("tracked_games", [])
        self.count_label.setText(f"{len(games)} game(s) tracked")
        cc = self.config.get("cc", "US")
        last_prices = self.config.get("last_prices", {})
        for game in games:
            appid = game["appid"]
            name = game["name"]
            edition = game.get("edition", "Standard Edition")
            key = f"{appid}_{edition}_{cc}"
            price_info = last_prices.get(key)
            card = GameCard(appid, name, edition, price_info)
            card.remove_clicked.connect(self._remove_game)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            self._card_map[(appid, edition)] = card
        if not games:
            empty = QLabel("No games tracked yet.\nGo to the Search tab to add games.")
            empty.setObjectName("statusLabel")
            empty.setAlignment(Qt.AlignCenter)
            self.cards_layout.insertWidget(0, empty)

    def update_card_price(self, appid, edition, price_info):
        key = (appid, edition)
        if key in self._card_map:
            self._card_map[key].update_price(price_info)

    def _remove_game(self, appid, edition):
        self.config["tracked_games"] = [
            g for g in self.config["tracked_games"]
            if not (g["appid"] == appid and g.get("edition", "") == edition)
        ]
        cc = self.config.get("cc", "US")
        key = f"{appid}_{edition}_{cc}"
        self.config["last_prices"].pop(key, None)
        save_config(self.config)
        self._card_map.pop((appid, edition), None)
        self.game_removed.emit(appid, edition)
        self.refresh_cards()

class SettingsPage(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._build_ui()

    def _build_ui(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(40)

        title = QLabel("Settings")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        region_section = QLabel("REGION")
        region_section.setObjectName("sectionLabel")
        layout.addWidget(region_section)

        region_row = QHBoxLayout()
        region_row.setSpacing(20)
        region_label = QLabel("Your Country / Region:")
        region_label.setObjectName("settingLabel")
        region_label.setMinimumWidth(200)
        region_row.addWidget(region_label)

        self.country_combo = QComboBox()
        self.country_combo.setMinimumHeight(36)
        for cc in sorted(CC_MAP.keys()):
            currency, symbol = CC_MAP[cc]
            self.country_combo.addItem(f"{cc} — {currency} ({symbol})", cc)
        idx = self.country_combo.findData(self.config.get("cc", "US"))
        if idx >= 0:
            self.country_combo.setCurrentIndex(idx)
        self.country_combo.currentIndexChanged.connect(self._save_region)
        region_row.addWidget(self.country_combo, 1)
        layout.addLayout(region_row)

        sep1 = QFrame()
        sep1.setObjectName("separator")
        layout.addWidget(sep1)

        bg_section = QLabel("APPLICATION")
        bg_section.setObjectName("sectionLabel")
        layout.addWidget(bg_section)

        self.bg_checkbox = QCheckBox("Run in Background (minimize to system tray)")
        self.bg_checkbox.setChecked(self.config.get("run_in_background", True))
        self.bg_checkbox.setMinimumHeight(30)
        self.bg_checkbox.stateChanged.connect(self._save_background)
        layout.addWidget(self.bg_checkbox)

        self.startup_checkbox = QCheckBox("Run on Startup (system tray only)")
        self.startup_checkbox.setChecked(self.config.get("run_on_startup", False))
        self.startup_checkbox.setMinimumHeight(30)
        self.startup_checkbox.stateChanged.connect(self._save_startup)
        layout.addWidget(self.startup_checkbox)

        sep2 = QFrame()
        sep2.setObjectName("separator")
        layout.addWidget(sep2)

        interval_section = QLabel("CHECK INTERVAL")
        interval_section.setObjectName("sectionLabel")
        layout.addWidget(interval_section)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(20)
        interval_label = QLabel("Check for sales every:")
        interval_label.setObjectName("settingLabel")
        interval_label.setMinimumWidth(200)
        interval_row.addWidget(interval_label)

        self.interval_combo = QComboBox()
        self.interval_combo.setMinimumHeight(36)
        intervals = [("1 minute", 60), ("5 minutes", 300), ("15 minutes", 900), ("30 minutes", 1800), ("1 hour", 3600)]
        for label, val in intervals:
            self.interval_combo.addItem(label, val)
        idx = self.interval_combo.findData(self.config.get("check_interval", 300))
        if idx >= 0:
            self.interval_combo.setCurrentIndex(idx)
        self.interval_combo.currentIndexChanged.connect(self._save_interval)
        interval_row.addWidget(self.interval_combo, 1)
        layout.addLayout(interval_row)

        sep3 = QFrame()
        sep3.setObjectName("separator")
        layout.addWidget(sep3)

        sound_section = QLabel("NOTIFICATION SOUND")
        sound_section.setObjectName("sectionLabel")
        layout.addWidget(sound_section)

        sound_row = QHBoxLayout()
        sound_row.setSpacing(20)
        sound_label = QLabel("Alert Sound:")
        sound_label.setObjectName("settingLabel")
        sound_label.setMinimumWidth(200)
        sound_row.addWidget(sound_label)

        self.sound_combo = QComboBox()
        self.sound_combo.setMinimumHeight(36)
        self._populate_sound_combo()
        sound_row.addWidget(self.sound_combo, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("trackBtn")
        browse_btn.setCursor(QCursor(Qt.PointingHandCursor))
        browse_btn.clicked.connect(self._browse_sound)
        sound_row.addWidget(browse_btn)

        test_btn = QPushButton("Test")
        test_btn.setObjectName("trackBtn")
        test_btn.setCursor(QCursor(Qt.PointingHandCursor))
        test_btn.clicked.connect(self._test_sound)
        sound_row.addWidget(test_btn)
        layout.addLayout(sound_row)

        self.custom_sound_label = QLabel("")
        self.custom_sound_label.setObjectName("statusLabel")
        self.custom_sound_label.setContentsMargins(220, 10, 0, 0)
        current_sound = self.config.get("notification_sound", "builtin:coin")
        if current_sound.startswith("builtin:"):
            name = current_sound[8:]
            self.custom_sound_label.setText(f"Current: {BUILTIN_SOUNDS.get(name, name)}")
        elif current_sound == "none":
            self.custom_sound_label.setText("Current: None (Silent)")
        else:
            self.custom_sound_label.setText(f"Current: {os.path.basename(current_sound)}")
        layout.addWidget(self.custom_sound_label)

        layout.addStretch()

        info = QLabel(
            "Settings are saved automatically.\n"
            "Background mode keeps the app running in the system tray when closed.\n"
            "Startup launches the app silently in the tray on system boot.\n"
            "Region determines the currency shown for all game prices.\n"
            "Notification sound plays when a tracked game goes on sale."
        )
        info.setObjectName("statusLabel")
        layout.addWidget(info)

        self.scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll)

    def _populate_sound_combo(self):
        self.sound_combo.blockSignals(True)
        self.sound_combo.clear()
        for key, label in BUILTIN_SOUNDS.items():
            self.sound_combo.addItem(label, f"builtin:{key}" if key != "none" else "none")
        current = self.config.get("notification_sound", "builtin:coin")
        if not current.startswith("builtin:") and current != "none" and os.path.exists(current):
            self.sound_combo.addItem(f"Custom: {os.path.basename(current)}", current)
        idx = self.sound_combo.findData(current)
        if idx >= 0:
            self.sound_combo.setCurrentIndex(idx)
        self.sound_combo.blockSignals(False)
        self.sound_combo.currentIndexChanged.connect(self._save_sound)

    def _browse_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Notification Sound", "", "Audio Files (*.wav *.mp3);;All Files (*.*)"
        )
        if path:
            self.config["notification_sound"] = path
            save_config(self.config)
            self._populate_sound_combo()
            self.custom_sound_label.setText(f"Current: {os.path.basename(path)}")
            self.settings_changed.emit()
            play_notification_sound(self.config)

    def _test_sound(self):
        current = self.sound_combo.currentData()
        temp_config = {"notification_sound": current}
        play_notification_sound(temp_config)

    def _save_sound(self):
        sound = self.sound_combo.currentData()
        self.config["notification_sound"] = sound
        save_config(self.config)
        if sound.startswith("builtin:"):
            name = sound[8:]
            self.custom_sound_label.setText(f"Current: {BUILTIN_SOUNDS.get(name, name)}")
        elif sound == "none":
            self.custom_sound_label.setText("Current: None (Silent)")
        else:
            self.custom_sound_label.setText(f"Current: {os.path.basename(sound)}")
        self.settings_changed.emit()

    def _save_region(self):
        self.config["cc"] = self.country_combo.currentData()
        save_config(self.config)
        self.settings_changed.emit()

    def _save_background(self, state):
        self.config["run_in_background"] = bool(state)
        save_config(self.config)
        self.settings_changed.emit()

    def _save_startup(self, state):
        self.config["run_on_startup"] = bool(state)
        save_config(self.config)
        self._toggle_startup(bool(state))
        self.settings_changed.emit()

    def _save_interval(self):
        self.config["check_interval"] = self.interval_combo.currentData()
        save_config(self.config)
        self.settings_changed.emit()

    def _toggle_startup(self, enable):
        if sys.platform == "win32":
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "SteamSaleTracker"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                if enable:
                    exe_path = sys.executable
                    if exe_path.endswith("python.exe"):
                        script = os.path.abspath(__file__)
                        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}" "{script}" --tray')
                    else:
                        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}" --tray')
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)
            except Exception as e:
                print(f"[ERROR] startup reg: {e}")
        elif sys.platform == "darwin":
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.steamtracker.plist")
            if enable:
                plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.steamtracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{os.path.abspath(__file__)}</string>
        <string>--tray</string>
    </array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>"""
                os.makedirs(os.path.dirname(plist_path), exist_ok=True)
                with open(plist_path, "w") as f:
                    f.write(plist_content)
            else:
                if os.path.exists(plist_path):
                    os.remove(plist_path)
        elif sys.platform.startswith("linux"):
            autostart_dir = os.path.expanduser("~/.config/autostart")
            desktop_path = os.path.join(autostart_dir, "steam-tracker.desktop")
            if enable:
                os.makedirs(autostart_dir, exist_ok=True)
                content = f"""[Desktop Entry]
Type=Application
Name=Steam Sale Tracker
Exec={sys.executable} {os.path.abspath(__file__)} --tray
Terminal=false
Hidden=false
"""
                with open(desktop_path, "w") as f:
                    f.write(content)
            else:
                if os.path.exists(desktop_path):
                    os.remove(desktop_path)

class MainWindow(QMainWindow):
    def __init__(self, config, start_in_tray=False):
        super().__init__()
        self.config = config
        self.start_in_tray = start_in_tray
        self.setWindowTitle("Steam Sale Tracker")
        self.setMinimumSize(900, 600)
        self.resize(960, 640)
        central = QWidget()
        central.setObjectName("mainWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        nav_bar = QFrame()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        logo_label = QLabel("  STEAM")
        logo_label.setStyleSheet("color: #66c0f4; font-size: 24px; font-weight: bold; padding: 24px 16px 8px 16px; letter-spacing: 2px;")
        nav_layout.addWidget(logo_label)
        subtitle = QLabel("  Sale Tracker")
        subtitle.setStyleSheet("color: #8f98a0; font-size: 12px; padding: 0px 16px 24px 16px;")
        nav_layout.addWidget(subtitle)
        self.nav_buttons = []
        for label, idx in [("Search", 0), ("Tracked Games", 1), ("Settings", 2)]:
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        nav_layout.addStretch()
        self.status_label = QLabel("  Ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("padding: 12px 16px;")
        nav_layout.addWidget(self.status_label)
        main_layout.addWidget(nav_bar)
        self.stack = QStackedWidget()
        self.search_page = SearchPage(config)
        self.tracked_page = TrackedPage(config)
        self.settings_page = SettingsPage(config)
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.tracked_page)
        self.stack.addWidget(self.settings_page)
        main_layout.addWidget(self.stack)
        self.stack.currentChanged.connect(self._on_page_changed)
        self.search_page.game_added.connect(self._on_game_added)
        self.tracked_page.refresh_requested.connect(self._refresh_prices)
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._create_tray_icon())
        self.tray_icon.setToolTip("Steam Sale Tracker")
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)
        check_action = QAction("Check Now", self)
        check_action.triggered.connect(self._refresh_prices)
        tray_menu.addAction(check_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()
        self.checker = PriceChecker(config)
        self.checker.sale_detected.connect(self._on_sale_detected)
        self.checker.check_done.connect(self._on_check_done)
        self.checker.status_update.connect(self._update_status)
        self.checker.price_fetched.connect(self._on_price_fetched)
        self.checker.start()
        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)
        if start_in_tray:
            self.hide()
        else:
            self.show()

    def _create_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#66c0f4"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QColor("#1b2838"))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "S")
        painter.end()
        return QIcon(pixmap)

    def _switch_page(self, index):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)

    def _on_page_changed(self, index):
        widget = self.stack.widget(index)
        if widget:
            slide_in_from_right(widget, 200)
        if index == 1:
            self.tracked_page.refresh_cards()

    def _on_game_added(self, game):
        self.tracked_page.refresh_cards()
        self._update_status(f"Now tracking: {game['name']} ({game.get('edition', 'N/A')})")
        self.checker.check_single(game["appid"], game.get("edition", "Standard Edition"), game["name"])

    def _on_price_fetched(self, appid, edition, price_info):
        self.tracked_page.update_card_price(appid, edition, price_info)

    def _refresh_prices(self):
        self._update_status("Checking prices...")
        def _check():
            self.checker._check_all()
        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _on_check_done(self):
        self.tracked_page.refresh_cards()

    def _on_sale_detected(self, appid, name, edition, discount, final_price, symbol):
        title = "Steam Sale Alert!"
        body = f'The game "{name}" ({edition}) is on sale at {discount}%!\nNow: {format_price(final_price, symbol)}'
        self.tray_icon.showMessage(title, body, QSystemTrayIcon.Information, 10000)
        play_notification_sound(self.config)
        self._update_status(f"SALE: {name} ({edition}) -{discount}%")

    def _update_status(self, text):
        self.status_label.setText(f"  {text}")

    def _on_settings_changed(self):
        self.checker.stop()
        self.checker = PriceChecker(self.config)
        self.checker.sale_detected.connect(self._on_sale_detected)
        self.checker.check_done.connect(self._on_check_done)
        self.checker.status_update.connect(self._update_status)
        self.checker.price_fetched.connect(self._on_price_fetched)
        self.checker.start()
        self._update_status("Settings saved")
        self.tracked_page.refresh_cards()
        self.search_page.reload_popular()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.config.get("run_in_background", True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Steam Sale Tracker", "Running in background. Click the tray icon to reopen.", QSystemTrayIcon.Information, 3000)
        else:
            self._quit_app()

    def _quit_app(self):
        self.checker.stop()
        self.tray_icon.hide()
        QApplication.quit()

def main():
    start_in_tray = "--tray" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("Steam Sale Tracker")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STEAM_STYLESHEET)
    config = load_config()
    window = MainWindow(config, start_in_tray=start_in_tray)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()