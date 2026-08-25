import time
import threading
import urllib.request

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint, QSize
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
            except:
                # images failing to load isnt critical, just show nothing
                pass

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()


class GameCard(QFrame):
    remove_clicked = pyqtSignal(str, str)

    def __init__(self, appid, name, edition, price_info=None):
        super().__init__()
        self.appid = appid
        self.edition = edition
        self.setObjectName("gameCard")
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(4)
        left.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("gameNameLabel")
        left.addWidget(self.name_label)

        self.edition_label = QLabel(edition)
        self.edition_label.setObjectName("editionNameLabel")
        left.addWidget(self.edition_label)

        self.status_label = QLabel(f"App ID: {appid}  \u2022  Fetching price...")
        self.status_label.setObjectName("statusLabel")
        left.addWidget(self.status_label)

        left.addStretch()
        layout.addLayout(left)

        self.right_layout = QHBoxLayout()
        self.right_layout.setSpacing(16)
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        self.price_widget = None
        self._update_price_display(price_info)

        remove_btn = QPushButton("\u2715")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.setFixedSize(36, 36)
        remove_btn.setCursor(QCursor(Qt.PointingHandCursor))
        remove_btn.setToolTip("Remove from tracking")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.appid, self.edition))
        self.right_layout.addWidget(remove_btn, 0, Qt.AlignVCenter)

        layout.addLayout(self.right_layout)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def update_price(self, price_info):
        self._update_price_display(price_info)
        status_text = f"App ID: {self.appid}"
        if price_info and not price_info.get("error"):
            if price_info.get("is_free"):
                status_text += "  \u2022  Free to Play"
            elif price_info.get("on_sale"):
                status_text += "  \u2022  On Sale"
            else:
                status_text += f"  \u2022  {format_price(price_info.get('price_final', 0), price_info.get('symbol', '$'))}"
        elif price_info and price_info.get("error"):
            status_text += "  \u2022  Price Unavailable"
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
        container_layout.setSpacing(10)

        symbol = price_info.get("symbol", "$")
        price_final = price_info.get("price_final", 0)
        price_original = price_info.get("price_original", 0)
        discount_pct = price_info.get("discount_pct", 0)

        if price_info.get("is_free"):
            free = QLabel("FREE")
            free.setObjectName("discountLabel")
            free.setAlignment(Qt.AlignCenter)
            free.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 13px; font-weight: 800; padding: 4px 10px; border-radius: 4px;")
            container_layout.addWidget(free)
        elif price_info.get("on_sale"):
            disc = QLabel(f"-{discount_pct}%")
            disc.setObjectName("discountLabel")
            disc.setAlignment(Qt.AlignCenter)
            disc.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 13px; font-weight: 800; padding: 4px 10px; border-radius: 4px;")
            container_layout.addWidget(disc)
            orig = QLabel(format_price(price_original, symbol))
            orig.setObjectName("origPriceStrikethrough")
            orig.setStyleSheet("color: #5a6a7e; font-size: 13px; text-decoration: line-through;")
            container_layout.addWidget(orig)
            final = QLabel(format_price(price_final, symbol))
            final.setObjectName("finalPriceGreen")
            final.setStyleSheet("color: #a4d65e; font-size: 15px; font-weight: 700;")
            container_layout.addWidget(final)
        else:
            price = QLabel(format_price(price_final, symbol))
            price.setObjectName("priceNormal")
            price.setStyleSheet("color: #e0e6ed; font-size: 15px; font-weight: 800;")
            container_layout.addWidget(price)

        self.price_widget = container
        self.right_layout.insertWidget(0, container, 0, Qt.AlignVCenter)


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
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.editions_loaded.connect(self._on_editions_loaded)
        self.editions_failed.connect(self._on_editions_failed)
        self._build_ui()
        self._load_editions(delay)

    def _build_ui(self):
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(16, 14, 16, 14)
        self.layout_main.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self.image_label = QLabel()
        self.image_label.setFixedSize(152, 71)
        self.image_label.setStyleSheet(
            "background-color: #0b1018; border-radius: 5px; border: 1px solid #1e2e44;"
        )
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("...")
        top_row.addWidget(self.image_label, 0, Qt.AlignTop)

        self.image_loader = ImageLoader()
        self.image_loader.image_loaded.connect(self._on_image_loaded)
        header_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.appid}/header.jpg"
        self.image_loader.load(header_url, str(self.appid))

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)

        self.name_label = QLabel(self.game_name)
        self.name_label.setObjectName("gameNameLabel")
        self.name_label.setWordWrap(True)
        top.addWidget(self.name_label, 1)

        self.type_badge = QLabel()
        self.type_badge.setObjectName("typeBadgeLabel")
        self.type_badge.setVisible(False)
        top.addWidget(self.type_badge)

        top.addStretch()

        self.id_label = QLabel(f"App ID: {self.appid}")
        self.id_label.setObjectName("statusLabel")
        self.id_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        top.addWidget(self.id_label)

        self.loading_label = QLabel("Loading editions...")
        self.loading_label.setObjectName("loadingLabel")
        self.loading_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        top.addWidget(self.loading_label)

        self._dot_count = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_loading_text)
        self._spinner_timer.start(500)

        text_col.addLayout(top)

        self.editions_container = QVBoxLayout()
        self.editions_container.setSpacing(6)
        self.editions_container.setContentsMargins(0, 0, 0, 0)
        text_col.addLayout(self.editions_container)

        top_row.addLayout(text_col, 1)
        self.layout_main.addLayout(top_row)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _on_image_loaded(self, appid, pixmap):
        if str(appid) == str(self.appid) and not pixmap.isNull():
            scaled = pixmap.scaled(152, 71, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

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
            no_ed.setStyleSheet("color: #5a6a7e; font-size: 12px;")
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
        err_layout.setContentsMargins(14, 8, 14, 8)
        err_label = QLabel(f"Failed to load: {error_msg}")
        err_label.setStyleSheet("color: #ef5350; font-size: 12px;")
        err_layout.addWidget(err_label)
        err_layout.addStretch()

        retry_btn = QPushButton("Retry")
        retry_btn.setObjectName("trackBtn")
        retry_btn.setCursor(QCursor(Qt.PointingHandCursor))
        retry_btn.setFixedWidth(90)
        retry_btn.setFixedHeight(32)
        retry_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 6px 16px; font-size: 13px; font-weight: bold; min-width: 70px; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
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
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 6, 12, 6)
        row_layout.setSpacing(8)

        ed_name = QLabel(edition["name"])
        ed_name.setStyleSheet("color: #c7d5e0; font-size: 12px; font-weight: 600; qproperty-elideMode: ElideRight;")
        ed_name.setToolTip(edition["name"])
        ed_name.setMinimumWidth(60)
        row_layout.addWidget(ed_name, 1)

        currency, symbol = get_currency_info(self.cc)

        price_info = QHBoxLayout()
        price_info.setSpacing(6)

        if edition.get("is_free"):
            price_label = QLabel("FREE")
            price_label.setAlignment(Qt.AlignCenter)
            price_label.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px;")
            price_info.addWidget(price_label)
        elif edition["discount_pct"] > 0:
            disc = QLabel(f"-{edition['discount_pct']}%")
            disc.setAlignment(Qt.AlignCenter)
            disc.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px;")
            price_info.addWidget(disc)
            orig = QLabel(format_price(edition["price_original"], symbol))
            orig.setStyleSheet("color: #5a6a7e; font-size: 12px; text-decoration: line-through;")
            price_info.addWidget(orig)
            final = QLabel(format_price(edition["price_final"], symbol))
            final.setStyleSheet("color: #a4d65e; font-size: 14px; font-weight: 700;")
            price_info.addWidget(final)
        else:
            price = QLabel(format_price(edition["price_final"], symbol))
            price.setStyleSheet("color: #7a8a9e; font-size: 13px;")
            price_info.addWidget(price)

        price_widget = QWidget()
        price_widget.setLayout(price_info)
        price_widget.setFixedWidth(price_widget.sizeHint().width())
        row_layout.addWidget(price_widget, 0, Qt.AlignVCenter)

        track_btn = QPushButton("Track")
        track_btn.setObjectName("trackBtn")
        track_btn.setCursor(QCursor(Qt.PointingHandCursor))
        track_btn.setFixedWidth(74)
        track_btn.setFixedHeight(28)
        track_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 4px 12px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        track_btn.clicked.connect(
            lambda checked, a=self.appid, n=self.game_name, ed=edition["name"]:
                self.track_clicked.emit(a, n, ed)
        )
        row_layout.addWidget(track_btn, 0, Qt.AlignVCenter)
        self.editions_container.addWidget(row)


class PopularSearchCard(QFrame):
    track_clicked = pyqtSignal(str, str, str)

    def __init__(self, appid, name, discount, final_price, original_price, image_url, cc):
        super().__init__()
        self.appid = appid
        self.game_name = name
        self.cc = cc
        self.setObjectName("popularCard")
        self.setFixedHeight(150)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(18)

        self.image_label = QLabel()
        self.image_label.setFixedSize(252, 118)
        self.image_label.setStyleSheet(
            "background-color: #0b1018; border-radius: 6px; border: 1px solid #1e2e44;"
        )
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("...")
        layout.addWidget(self.image_label, 0, Qt.AlignVCenter)

        self.image_loader = ImageLoader()
        self.image_loader.image_loaded.connect(self._on_image_loaded)
        self.image_loader.load(image_url, appid)

        info = QVBoxLayout()
        info.setSpacing(6)
        info.setContentsMargins(0, 0, 0, 0)

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
            disc_label.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px;")
            price_row.addWidget(disc_label)
            orig_label = QLabel(format_price(original_price, symbol))
            orig_label.setObjectName("popularOrigLabel")
            orig_label.setStyleSheet("color: #5a6a7e; font-size: 11px; text-decoration: line-through;")
            price_row.addWidget(orig_label)
            final_label = QLabel(format_price(final_price, symbol))
            final_label.setObjectName("finalPriceGreen")
            final_label.setStyleSheet("color: #a4d65e; font-size: 15px; font-weight: 700;")
            price_row.addWidget(final_label)
        elif final_price == 0:
            free_label = QLabel("FREE")
            free_label.setObjectName("discountLabelSmall")
            free_label.setAlignment(Qt.AlignCenter)
            free_label.setStyleSheet("color: #1a3a1a; background-color: #a4d65e; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px;")
            price_row.addWidget(free_label)
        else:
            final_label = QLabel(format_price(final_price, symbol))
            final_label.setObjectName("priceNormal")
            final_label.setStyleSheet("color: #e0e6ed; font-size: 15px; font-weight: 800;")
            price_row.addWidget(final_label)

        price_row.addStretch()
        info.addLayout(price_row)
        info.addStretch()

        layout.addLayout(info, 1)

        track_btn = QPushButton("Track")
        track_btn.setObjectName("trackBtn")
        track_btn.setCursor(QCursor(Qt.PointingHandCursor))
        track_btn.setFixedWidth(74)
        track_btn.setFixedHeight(30)
        track_btn.setStyleSheet(
            "QPushButton { background-color: #a4d65e; color: #0f1520; border: 1px solid #a4d65e; "
            "border-radius: 3px; padding: 4px 12px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #b4e66e; border-color: #b4e66e; }"
            "QPushButton:pressed { background-color: #94c64e; border-color: #94c64e; }"
        )
        track_btn.clicked.connect(
            lambda checked, a=self.appid, n=self.game_name:
                self.track_clicked.emit(a, n, "Standard Edition")
        )
        layout.addWidget(track_btn, 0, Qt.AlignVCenter)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def _on_image_loaded(self, appid, pixmap):
        if appid == self.appid and not pixmap.isNull():
            scaled = pixmap.scaled(252, 118, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
