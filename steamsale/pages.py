import os
import time
import threading
import sys

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QFrame, QScrollArea, QStackedWidget, QFileDialog,
    QSizePolicy, QSpacerItem, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor, QColor

from .config import CC_MAP, DLC_TYPES, save_config, get_currency_info, format_price
from .api import search_game_by_name, fetch_featured_games
from .sounds import BUILTIN_SOUNDS, play_notification_sound
from .widgets import GameCard, SearchResultCard, PopularSearchCard
from .wishlist import normalize_wishlist_profile, fetch_wishlist


class SearchPage(QWidget):
    game_added = pyqtSignal(dict)
    popular_loaded = pyqtSignal(list)
    popular_failed = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        # If you see this, you're gay
        self.popular_games = []
        self.has_searched = False
        self.popular_loaded.connect(self._on_popular_loaded)
        self.popular_failed.connect(self._on_popular_failed)
        self._build_ui()
        self._load_popular()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 30)
        layout.setSpacing(0)

        title = QLabel("Track a Game")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Search by name or Steam App ID  \u2022  Editions load automatically")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        layout.addSpacing(28)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search games... (e.g. Minecraft or something, Elden Ring)")
        self.search_input.setMinimumHeight(48)
        self.search_input.returnPressed.connect(self._do_search)
        self.search_input.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self.search_input)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("primaryBtn")
        search_btn.setCursor(QCursor(Qt.PointingHandCursor))
        search_btn.setFixedHeight(48)
        search_btn.setFixedWidth(110)
        search_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 10px 28px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        layout.addSpacing(24)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setSpacing(16)
        self.results_layout.setContentsMargins(0, 0, 0, 0)

        self.search_section_widget = QWidget()
        self.search_section_layout = QVBoxLayout(self.search_section_widget)
        self.search_section_layout.setSpacing(12)
        self.search_section_layout.setContentsMargins(0, 0, 0, 0)

        self.games_label = QLabel("GAMES")
        self.games_label.setObjectName("sectionLabel")
        self.search_section_layout.addWidget(self.games_label)

        self.games_container = QVBoxLayout()
        self.games_container.setSpacing(12)
        self.search_section_layout.addLayout(self.games_container)

        self.dlc_section_widget = QWidget()
        self.dlc_section_layout = QVBoxLayout(self.dlc_section_widget)
        self.dlc_section_layout.setSpacing(10)
        self.dlc_section_layout.setContentsMargins(0, 0, 0, 0)

        dlc_sep = QFrame()
        dlc_sep.setObjectName("separator")
        dlc_sep.setFixedHeight(1)
        self.dlc_section_layout.addWidget(dlc_sep)

        self.dlc_label = QLabel("DOWNLOADABLE CONTENT")
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
        self.popular_section_layout.setSpacing(12)
        self.popular_section_layout.setContentsMargins(0, 0, 0, 0)

        popular_header = QHBoxLayout()
        popular_header.setSpacing(12)
        self.popular_label = QLabel("FEATURED & ON SALE")
        self.popular_label.setObjectName("sectionLabel")
        popular_header.addWidget(self.popular_label)
        popular_header.addStretch()

        self.refresh_popular_btn = QPushButton("Refresh")
        self.refresh_popular_btn.setObjectName("trackBtn")
        self.refresh_popular_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.refresh_popular_btn.setFixedWidth(90)
        self.refresh_popular_btn.setFixedHeight(32)
        self.refresh_popular_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 6px 16px; font-size: 13px; font-weight: bold; min-width: 70px; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
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
                self._add_search_result_card(result["appid"], result["name"], i * 0.5, image_url=result.get("tiny_image", ""))

    def _add_search_result_card(self, appid, name, delay=0, image_url=""):
        cc = self.config.get("cc", "US")
        card = SearchResultCard(appid, name, cc, delay=delay, image_url=image_url)
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
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(16)
        header.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("Tracked Games")
        title.setObjectName("titleLabel")
        title_col.addWidget(title)
        self.count_label = QLabel("0 games tracked")
        self.count_label.setObjectName("subtitleLabel")
        title_col.addWidget(self.count_label)
        header.addLayout(title_col)

        header.addStretch()

        refresh_btn = QPushButton("  Refresh Prices")
        refresh_btn.setObjectName("primaryBtn")
        refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        refresh_btn.setFixedHeight(44)
        refresh_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 10px 28px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(refresh_btn)

        layout.addLayout(header)
        layout.addSpacing(28)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)

    def refresh_cards(self):
        self._card_map.clear()
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        games = [game for game in self.config.get("tracked_games", []) if game.get("source") != "wishlist"]
        self.count_label.setText(f"{len(games)} game{'s' if len(games) != 1 else ''} tracked")

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
            empty = QLabel("No games tracked yet.\nGo to Search to add some games.")
            empty.setObjectName("statusLabel")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #3e4e62; font-size: 14px; padding: 60px 0;")
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
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(32)

        title = QLabel("Settings")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Configure your tracker preferences")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        region_card = self._make_card("Region", "Your country determines the currency for all game prices.")
        region_row = QHBoxLayout()
        region_row.setSpacing(16)
        region_label = QLabel("Country / Region")
        region_label.setObjectName("settingLabel")
        region_label.setMinimumWidth(180)
        region_row.addWidget(region_label)

        self.country_combo = QComboBox()
        self.country_combo.setMinimumHeight(40)
        self.country_combo.setStyleSheet(
            "QComboBox { background-color: #1a2236; color: #ffffff; border: 2px solid #1e2e44; "
            "border-radius: 10px; padding: 10px 16px; min-width: 180px; font-size: 13px; }"
            "QComboBox:hover { border-color: rgba(102, 192, 244, 0.4); }"
            "QComboBox:focus { border-color: #66c0f4; }"
            "QComboBox::drop-down { border: none; width: 30px; }"
            "QComboBox::down-arrow { image: none; border-left: 5px solid transparent; "
            "border-right: 5px solid transparent; border-top: 6px solid #66c0f4; margin-right: 10px; }"
            "QComboBox QAbstractItemView { background-color: #1e2e44; color: #c7d5e0; "
            "border: 1px solid #2a3e58; selection-background-color: #2a475e; selection-color: #ffffff; "
            "outline: none; padding: 6px; }"
        )
        for cc in sorted(CC_MAP.keys()):
            currency, symbol = CC_MAP[cc]
            self.country_combo.addItem(f"{cc}  \u2014  {currency} ({symbol})", cc)
        idx = self.country_combo.findData(self.config.get("cc", "US"))
        if idx >= 0:
            self.country_combo.setCurrentIndex(idx)
        self.country_combo.currentIndexChanged.connect(self._save_region)
        region_row.addWidget(self.country_combo, 1)
        region_card.layout().addLayout(region_row)
        layout.addWidget(region_card)

        app_card = self._make_card("Application", "Background behavior and startup options.")

        self.bg_checkbox = QCheckBox("Run in Background (minimize to system tray when closed)")
        self.bg_checkbox.setChecked(self.config.get("run_in_background", True))
        self.bg_checkbox.setMinimumHeight(32)
        self.bg_checkbox.stateChanged.connect(self._save_background)
        app_card.layout().addWidget(self.bg_checkbox)

        self.startup_checkbox = QCheckBox("Run on Startup (launch silently in tray on boot)")
        self.startup_checkbox.setChecked(self.config.get("run_on_startup", False))
        self.startup_checkbox.setMinimumHeight(32)
        self.startup_checkbox.stateChanged.connect(self._save_startup)
        app_card.layout().addWidget(self.startup_checkbox)
        layout.addWidget(app_card)

        interval_card = self._make_card("Check Interval", "How often to check for price changes on tracked games.")
        interval_row = QHBoxLayout()
        interval_row.setSpacing(16)
        interval_label = QLabel("Check every")
        interval_label.setObjectName("settingLabel")
        interval_label.setMinimumWidth(180)
        interval_row.addWidget(interval_label)

        self.interval_combo = QComboBox()
        self.interval_combo.setMinimumHeight(40)
        self.interval_combo.setStyleSheet(
            "QComboBox { background-color: #1a2236; color: #ffffff; border: 2px solid #1e2e44; "
            "border-radius: 10px; padding: 10px 16px; min-width: 180px; font-size: 13px; }"
            "QComboBox:hover { border-color: rgba(102, 192, 244, 0.4); }"
            "QComboBox:focus { border-color: #66c0f4; }"
            "QComboBox::drop-down { border: none; width: 30px; }"
            "QComboBox::down-arrow { image: none; border-left: 5px solid transparent; "
            "border-right: 5px solid transparent; border-top: 6px solid #66c0f4; margin-right: 10px; }"
            "QComboBox QAbstractItemView { background-color: #1e2e44; color: #c7d5e0; "
            "border: 1px solid #2a3e58; selection-background-color: #2a475e; selection-color: #ffffff; "
            "outline: none; padding: 6px; }"
        )
        intervals = [
            ("1 minute", 60), ("5 minutes", 300), ("15 minutes", 900),
            ("30 minutes", 1800), ("1 hour", 3600)
        ]
        for label, val in intervals:
            self.interval_combo.addItem(label, val)
        idx = self.interval_combo.findData(self.config.get("check_interval", 300))
        if idx >= 0:
            self.interval_combo.setCurrentIndex(idx)
        self.interval_combo.currentIndexChanged.connect(self._save_interval)
        interval_row.addWidget(self.interval_combo, 1)
        interval_card.layout().addLayout(interval_row)
        layout.addWidget(interval_card)

        sound_card = self._make_card("Notification Sound", "Sound played when a tracked game goes on sale.")
        sound_row = QHBoxLayout()
        sound_row.setSpacing(12)

        self.sound_combo = QComboBox()
        self.sound_combo.setMinimumHeight(40)
        self.sound_combo.setStyleSheet(
            "QComboBox { background-color: #1a2236; color: #ffffff; border: 2px solid #1e2e44; "
            "border-radius: 10px; padding: 10px 16px; min-width: 180px; font-size: 13px; }"
            "QComboBox:hover { border-color: rgba(102, 192, 244, 0.4); }"
            "QComboBox:focus { border-color: #66c0f4; }"
            "QComboBox::drop-down { border: none; width: 30px; }"
            "QComboBox::down-arrow { image: none; border-left: 5px solid transparent; "
            "border-right: 5px solid transparent; border-top: 6px solid #66c0f4; margin-right: 10px; }"
            "QComboBox QAbstractItemView { background-color: #1e2e44; color: #c7d5e0; "
            "border: 1px solid #2a3e58; selection-background-color: #2a475e; selection-color: #ffffff; "
            "outline: none; padding: 6px; }"
        )
        self._populate_sound_combo()
        sound_row.addWidget(self.sound_combo, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("browseBtn")
        browse_btn.setCursor(QCursor(Qt.PointingHandCursor))
        browse_btn.setFixedHeight(40)
        browse_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 6px; padding: 8px 22px; font-size: 12px; font-weight: 700; min-width: 80px; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        browse_btn.clicked.connect(self._browse_sound)
        sound_row.addWidget(browse_btn)

        test_btn = QPushButton("Test")
        test_btn.setObjectName("testBtn")
        test_btn.setCursor(QCursor(Qt.PointingHandCursor))
        test_btn.setFixedHeight(40)
        test_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 6px; padding: 8px 22px; font-size: 12px; font-weight: 700; min-width: 80px; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        test_btn.clicked.connect(self._test_sound)
        sound_row.addWidget(test_btn)

        sound_card.layout().addLayout(sound_row)

        self.custom_sound_label = QLabel("")
        self.custom_sound_label.setObjectName("statusLabel")
        current_sound = self.config.get("notification_sound", "builtin:coin")
        if current_sound.startswith("builtin:"):
            name = current_sound[8:]
            self.custom_sound_label.setText(f"Current: {BUILTIN_SOUNDS.get(name, name)}")
        elif current_sound == "none":
            self.custom_sound_label.setText("Current: None (Silent)")
        else:
            self.custom_sound_label.setText(f"Current: {os.path.basename(current_sound)}")
        sound_card.layout().addWidget(self.custom_sound_label)

        layout.addWidget(sound_card)
        layout.addStretch()

        self.scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll)

    def _make_card(self, title, description):
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 24)
        card_layout.setSpacing(16)

        header = QLabel(title)
        header.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700;")
        card_layout.addWidget(header)

        desc = QLabel(description)
        desc.setObjectName("subtitleLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        return card

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
        # this whole function is different per OS, its kinda ugly but it works
        if sys.platform == "win32":
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "UnrealsSaleTracker"
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


class LinkSteamPage(QWidget):
    wishlist_synced = pyqtSignal(list)
    wishlist_tracking_changed = pyqtSignal(list)
    account_changed = pyqtSignal(bool)
    sync_finished = pyqtSignal(str, object, str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.syncing = False
        self._card_map = {}
        self.unlink_overlay = None
        self.unlink_overlay_host = None
        self.sync_finished.connect(self._on_sync_finished)
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(30 * 60 * 1000)
        self.sync_timer.timeout.connect(self.sync_wishlist)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(16)

        header = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("titleLabel")
        self.title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        header.addWidget(self.title)
        header.addStretch()

        self.unlink_button = QPushButton("Unlink account")
        self.unlink_button.setObjectName("unlinkBtn")
        self.unlink_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.unlink_button.clicked.connect(self._confirm_unlink)
        header.addWidget(self.unlink_button)
        layout.addLayout(header)

        self.subtitle = QLabel()
        self.subtitle.setObjectName("subtitleLabel")
        self.subtitle.setWordWrap(True)
        self.subtitle.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.subtitle)

        self.link_panel = QWidget()
        self.link_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        link_layout = QVBoxLayout(self.link_panel)
        link_layout.setContentsMargins(0, 20, 0, 0)
        link_layout.setSpacing(12)

        details = QLabel("Enter your public Steam profile URL or SteamID64. Your wishlist must be visible to everyone.")
        details.setObjectName("statusLabel")
        details.setWordWrap(True)
        details.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        link_layout.addWidget(details)

        self.profile_input = QLineEdit()
        self.profile_input.setPlaceholderText("Steam profile URL or SteamID64")
        self.profile_input.setMinimumHeight(46)
        self.profile_input.returnPressed.connect(self._link_account)
        link_layout.addWidget(self.profile_input)

        self.link_button = QPushButton("Link Steam Wishlist")
        self.link_button.setObjectName("primaryBtn")
        self.link_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.link_button.setFixedHeight(42)
        self.link_button.clicked.connect(self._link_account)
        link_layout.addWidget(self.link_button, alignment=Qt.AlignLeft)
        layout.addWidget(self.link_panel)

        self.wishlist_summary = QLabel()
        self.wishlist_summary.setObjectName("statusLabel")
        self.wishlist_summary.setWordWrap(True)
        self.wishlist_summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.wishlist_summary)

        self.sync_button = QPushButton("Sync Wishlist")
        self.sync_button.setObjectName("trackBtn")
        self.sync_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.sync_button.setFixedHeight(38)
        self.sync_button.clicked.connect(self.sync_wishlist)
        layout.addWidget(self.sync_button, alignment=Qt.AlignLeft)

        self.link_spacer = QWidget()
        self.link_spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addWidget(self.link_spacer, 1)

        self.games_label = QLabel("WISHLIST GAMES")
        self.games_label.setObjectName("sectionLabel")
        self.games_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.games_label)

        self.games_scroll = QScrollArea()
        self.games_scroll.setWidgetResizable(True)
        self.games_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.games_widget = QWidget()
        self.games_layout = QVBoxLayout(self.games_widget)
        self.games_layout.setSpacing(12)
        self.games_layout.setContentsMargins(0, 0, 0, 0)
        self.games_layout.addStretch()
        self.games_scroll.setWidget(self.games_widget)
        self.games_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.games_scroll, 1)

        self._show_linked_state(bool(self.config.get("steam_wishlist")))
        if self.config.get("steam_wishlist"):
            self.sync_timer.start()
            QTimer.singleShot(1200, self.sync_wishlist)

    def _show_linked_state(self, linked):
        self.title.setText("Wishlist" if linked else "Link Steam Wishlist")
        self.subtitle.setText("Track your steam wishlist here!" if linked else "Connect your public Steam wishlist to track sales automatically.")
        self.link_panel.setVisible(not linked)
        self.link_spacer.setVisible(not linked)
        self.wishlist_summary.setVisible(linked)
        self.sync_button.setVisible(linked)
        self.unlink_button.setVisible(linked)
        self.games_label.setVisible(linked)
        self.games_scroll.setVisible(linked)
        if linked:
            wishlist = self.config.get("steam_wishlist", {})
            total = len(wishlist.get("appids", []))
            selected = len(self._selected_wishlist_appids())
            self.wishlist_summary.setText(f"Tracking {selected} of {total} wishlist games.")
        self.refresh_wishlist_games()

    def _selected_wishlist_appids(self):
        wishlist = self.config.get("steam_wishlist", {})
        appids = {str(appid) for appid in wishlist.get("appids", [])}
        selected = wishlist.get("tracked_appids")
        if selected is None:
            return appids
        return appids.intersection(str(appid) for appid in selected)

    def refresh_wishlist_games(self):
        self._card_map.clear()
        while self.games_layout.count() > 1:
            item = self.games_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cc = self.config.get("cc", "US")
        last_prices = self.config.get("last_prices", {})
        tracked_games = {str(game.get("appid")): game for game in self.config.get("tracked_games", [])}
        wishlist = self.config.get("steam_wishlist", {})
        saved_games = {str(game.get("appid")): game for game in wishlist.get("games", [])}
        appids = wishlist.get("appids", [])
        selected_appids = self._selected_wishlist_appids()
        for appid in appids:
            game = tracked_games.get(str(appid), {})
            saved_game = saved_games.get(str(appid), {})
            edition = game.get("edition", "Standard Edition")
            key = f"{appid}_{edition}_{cc}"
            card = GameCard(
                appid, self._wishlist_game_name(appid, saved_game.get("name"), game.get("name")), edition,
                last_prices.get(key), removable=False, trackable=True,
                tracking_enabled=str(appid) in selected_appids
            )
            card.tracking_toggled.connect(self._set_wishlist_tracking)
            self.games_layout.insertWidget(self.games_layout.count() - 1, card)
            self._card_map[(appid, edition)] = card

        if not appids:
            empty = QLabel("Your wishlist games will appear here after syncing.")
            empty.setObjectName("statusLabel")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #5a6a7e; font-size: 14px; padding: 32px 0;")
            self.games_layout.insertWidget(0, empty)

    @staticmethod
    def _is_fallback_game_name(name):
        return not name or name.lower().startswith("steam app ")

    @classmethod
    def _wishlist_game_name(cls, appid, *names):
        for name in names:
            if name and not cls._is_fallback_game_name(name):
                return name
        for name in names:
            if name:
                return name
        return f"Steam App {appid}"

    def update_card_price(self, appid, edition, price_info):
        card = self._card_map.get((appid, edition))
        if card:
            card.update_price(price_info)

    def _set_wishlist_tracking(self, appid, enabled):
        wishlist = self.config.get("steam_wishlist", {})
        appids = {str(value) for value in wishlist.get("appids", [])}
        selected = self._selected_wishlist_appids()
        if enabled:
            selected.add(str(appid))
        else:
            selected.discard(str(appid))

        added = []
        if not enabled:
            self.config["tracked_games"] = [
                game for game in self.config.get("tracked_games", [])
                if not (game.get("source") == "wishlist" and str(game.get("appid")) == str(appid))
            ]
        else:
            entry = next(
                (game for game in self.config.get("tracked_games", [])
                 if str(game.get("appid")) == str(appid)),
                None
            )
            if not entry:
                card = self._card_map.get((str(appid), "Standard Edition"))
                name = card.name_label.text() if card else f"Steam App {appid}"
                entry = {"appid": str(appid), "name": name, "edition": "Standard Edition", "source": "wishlist"}
                self.config.setdefault("tracked_games", []).append(entry)
                added.append(entry)

        wishlist["tracked_appids"] = sorted(appids.intersection(selected))
        save_config(self.config)
        total = len(appids)
        count = len(wishlist["tracked_appids"])
        self.wishlist_summary.setText(f"Tracking {count} of {total} wishlist games.")
        self.wishlist_tracking_changed.emit(added)

    def _link_account(self):
        profile = normalize_wishlist_profile(self.profile_input.text())
        if not profile:
            self.wishlist_summary.setText("Enter a valid Steam profile URL or SteamID64.")
            self.wishlist_summary.setVisible(True)
            return
        self._start_sync(profile)

    def sync_wishlist(self):
        wishlist = self.config.get("steam_wishlist")
        if wishlist:
            self._start_sync(wishlist.get("profile", ""))

    def _start_sync(self, profile):
        if self.syncing or not profile:
            return
        self.syncing = True
        self.link_button.setEnabled(False)
        self.sync_button.setEnabled(False)
        self.unlink_button.setEnabled(False)
        self.wishlist_summary.setVisible(True)
        self.wishlist_summary.setText("Loading your Steam wishlist...")

        def _fetch():
            try:
                games = fetch_wishlist(profile, self.config.get("cc", "US"))
                self.sync_finished.emit(profile, games, "")
            except Exception as error:
                message = str(error) or "Could not read this wishlist. Make sure it is public and try again."
                self.sync_finished.emit(profile, None, message)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_sync_finished(self, profile, games, error):
        self.syncing = False
        self.link_button.setEnabled(True)
        self.sync_button.setEnabled(True)
        self.unlink_button.setEnabled(True)
        if error:
            self.wishlist_summary.setText(error)
            self.wishlist_summary.setVisible(True)
            self.wishlist_synced.emit([])
            return

        previous = self.config.get("steam_wishlist", {})
        was_linked = bool(previous)
        saved_names = {
            str(game.get("appid")): game.get("name")
            for game in previous.get("games", [])
        }
        tracked_names = {
            str(game.get("appid")): game.get("name")
            for game in self.config.get("tracked_games", [])
        }
        for game in games:
            appid = str(game["appid"])
            if self._is_fallback_game_name(game.get("name")):
                game["name"] = self._wishlist_game_name(
                    appid, saved_names.get(appid), tracked_names.get(appid)
                )
        current_appids = {str(game["appid"]) for game in games}
        previous_selected = previous.get("tracked_appids")
        selected_appids = (
            {str(appid) for appid in previous_selected}.intersection(current_appids)
            if previous_selected is not None
            else set()
        )
        removed_appids = {
            str(game.get("appid")) for game in self.config.get("tracked_games", [])
            if game.get("source") == "wishlist" and str(game.get("appid")) not in selected_appids
        }
        removed_games = [
            game for game in self.config.get("tracked_games", [])
            if game.get("source") == "wishlist" and str(game.get("appid")) in removed_appids
        ]
        self.config["tracked_games"] = [
            game for game in self.config.get("tracked_games", [])
            if not (game.get("source") == "wishlist" and str(game.get("appid")) in removed_appids)
        ]
        for game in removed_games:
            edition = game.get("edition", "Standard Edition")
            self.config.get("last_prices", {}).pop(f"{game['appid']}_{edition}_{self.config.get('cc', 'US')}", None)

        added = []
        for game in games:
            appid = str(game["appid"])
            if appid not in selected_appids:
                continue
            entry = next((item for item in self.config["tracked_games"] if item.get("appid") == appid and item.get("edition", "Standard Edition") == "Standard Edition"), None)
            if entry:
                if entry.get("source") == "wishlist":
                    entry["name"] = game["name"]
                continue
            entry = {"appid": appid, "name": game["name"], "edition": "Standard Edition", "source": "wishlist"}
            self.config["tracked_games"].append(entry)
            added.append(entry)

        self.config["steam_wishlist"] = {
            "profile": profile,
            "appids": sorted(current_appids),
            "tracked_appids": sorted(selected_appids),
            "games": [{"appid": str(game["appid"]), "name": game["name"]} for game in games],
        }
        save_config(self.config)
        self._show_linked_state(True)
        self.wishlist_summary.setText(f"Tracking {len(selected_appids)} of {len(current_appids)} wishlist games.")
        self.refresh_wishlist_games()
        self.sync_timer.start()
        if not was_linked:
            self.account_changed.emit(True)
        self.wishlist_synced.emit(added)

    def _confirm_unlink(self):
        if self.unlink_overlay:
            return

        host = self.window().centralWidget()
        if not host:
            host = self
        host.installEventFilter(self)

        overlay = QWidget(host)
        overlay.setObjectName("unlinkConfirmOverlay")
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        overlay.setGeometry(host.rect())

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch()

        card = QFrame()
        card.setObjectName("unlinkConfirmPanel")
        card.setFixedWidth(min(500, max(320, self.width() - 48)))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)

        title = QLabel("Unlink Steam Wishlist?")
        title.setObjectName("unlinkConfirmTitle")
        card_layout.addWidget(title)

        message = QLabel("Are you sure you want to unlink your steam account, your wishlist won't be tracked anymore")
        message.setObjectName("unlinkConfirmText")
        message.setWordWrap(True)
        card_layout.addWidget(message)

        buttons = QHBoxLayout()
        buttons.addStretch()

        yes_button = QPushButton("Yes")
        yes_button.setObjectName("confirmUnlinkYes")
        yes_button.setCursor(QCursor(Qt.PointingHandCursor))
        yes_button.setFixedSize(88, 38)
        yes_button.clicked.connect(self._unlink_account)
        buttons.addWidget(yes_button)

        no_button = QPushButton("No")
        no_button.setObjectName("confirmUnlinkNo")
        no_button.setCursor(QCursor(Qt.PointingHandCursor))
        no_button.setFixedSize(88, 38)
        no_button.clicked.connect(self._cancel_unlink)
        buttons.addWidget(no_button)
        card_layout.addLayout(buttons)

        yes_glow = QGraphicsDropShadowEffect(yes_button)
        yes_glow.setColor(QColor("#8ed34a"))
        yes_glow.setBlurRadius(18)
        yes_glow.setOffset(0, 0)
        yes_button.setGraphicsEffect(yes_glow)

        no_glow = QGraphicsDropShadowEffect(no_button)
        no_glow.setColor(QColor("#df535b"))
        no_glow.setBlurRadius(18)
        no_glow.setOffset(0, 0)
        no_button.setGraphicsEffect(no_glow)

        overlay_layout.addWidget(card, 0, Qt.AlignHCenter)
        overlay_layout.addStretch()

        overlay.show()
        overlay.raise_()
        self.unlink_overlay = overlay
        self.unlink_overlay_host = host

    def _cancel_unlink(self):
        self._dismiss_unlink_confirmation()

    def _dismiss_unlink_confirmation(self):
        if self.unlink_overlay:
            self.unlink_overlay.hide()
            self.unlink_overlay.deleteLater()
            self.unlink_overlay = None
            if self.unlink_overlay_host:
                self.unlink_overlay_host.removeEventFilter(self)
                self.unlink_overlay_host = None

    def _unlink_account(self):
        self._dismiss_unlink_confirmation()
        self.sync_timer.stop()
        removed = [game for game in self.config.get("tracked_games", []) if game.get("source") == "wishlist"]
        self.config["tracked_games"] = [game for game in self.config.get("tracked_games", []) if game.get("source") != "wishlist"]
        for game in removed:
            edition = game.get("edition", "Standard Edition")
            self.config.get("last_prices", {}).pop(f"{game['appid']}_{edition}_{self.config.get('cc', 'US')}", None)
        self.config.pop("steam_wishlist", None)
        save_config(self.config)
        self._show_linked_state(False)
        self.account_changed.emit(False)
        self.wishlist_synced.emit([])

    def eventFilter(self, watched, event):
        if watched is self.unlink_overlay_host and event.type() == QEvent.Resize and self.unlink_overlay:
            self.unlink_overlay.setGeometry(watched.rect())
            self.unlink_overlay.raise_()
        return super().eventFilter(watched, event)
