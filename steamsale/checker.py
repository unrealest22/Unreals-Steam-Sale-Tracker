import time
import threading
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal

from .config import save_config, format_price
from .api import fetch_price_for_game

class PriceChecker(QObject):
    # angry robot stalks your wishlist until something goes on sale, then screams about it
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
            # TODO: maybe add jitter so we don't hammer steam at exact intervals
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