import time
import threading
import urllib.request

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import QPixmap, QCursor, QColor

from .config import DLC_TYPES, get_currency_info, format_price
from .api import get_editions

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