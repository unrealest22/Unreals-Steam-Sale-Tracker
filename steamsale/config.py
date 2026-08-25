import os
import json

APP_DIR = os.path.join(os.path.expanduser("~"), ".steam_sale_tracker")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
SOUNDS_DIR = os.path.join(APP_DIR, "sounds")
os.makedirs(APP_DIR, exist_ok=True)
os.makedirs(SOUNDS_DIR, exist_ok=True)

# bump this when config format changes so old configs get overwritten instead of crashing
DEFAULT_CONFIG = {
    "cc": "US",
    "run_in_background": True,
    "run_on_startup": False,
    "tracked_games": [],
    "check_interval": 300,
    "last_prices": {},
    "notification_sound": "builtin:coin"
}

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