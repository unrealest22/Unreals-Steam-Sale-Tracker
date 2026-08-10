import os
import time
import threading
import sys

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QFrame, QScrollArea, QStackedWidget, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor

from .config import CC_MAP, DLC_TYPES, save_config, get_currency_info, format_price
from .api import search_game_by_name, fetch_featured_games
from .sounds import BUILTIN_SOUNDS, play_notification_sound
from .widgets import GameCard, SearchResultCard, PopularSearchCard

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