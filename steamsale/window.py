import os
import sys
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSystemTrayIcon, QMenu, QAction, QApplication,
    QMessageBox, QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, QPoint
from PyQt5.QtGui import QIcon, QColor, QFont, QPixmap, QCursor, QPainter, QLinearGradient

from .config import format_price
from .styles import STEAM_STYLESHEET, slide_in_from_right, fade_in
from .sounds import play_notification_sound
from .pages import SearchPage, TrackedPage, SettingsPage, LinkSteamPage
from .checker import PriceChecker
from .updater import UpdateChecker, show_update_dialog


class MainWindow(QMainWindow):
    def __init__(self, config, start_in_tray=False):
        super().__init__()

        if sys.platform == "win32":
            import ctypes
            # without this the taskbar icon is just a generic python icon
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("steam.sale.tracker")

        self.config = config
        self.start_in_tray = start_in_tray

        app_title = "Unreal's Sale Tracker"
        self.setWindowTitle(app_title)
        # We all love unreal right guys

        if getattr(sys, 'frozen', False):
            base_path = os.path.join(sys._MEIPASS, "steamsale")
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_path, "steamsale.ico")

        self.app_icon = None
        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
        else:
            self.app_icon = self._create_default_icon()

        self.setWindowIcon(self.app_icon)

        self.setMinimumSize(960, 640)
        self.resize(1040, 700)

        central = QWidget()
        central.setObjectName("mainWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("navBar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo_wrap = QWidget()
        logo_wrap.setFixedHeight(90)
        logo_layout = QVBoxLayout(logo_wrap)
        logo_layout.setContentsMargins(24, 28, 24, 12)
        logo_layout.setSpacing(2)

        logo_icon_row = QHBoxLayout()
        logo_icon_row.setSpacing(10)
        logo_icon_row.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        logo_png = os.path.join(base_path, "Steam_icon_logo.png")
        if os.path.exists(logo_png):
            icon_label.setPixmap(QPixmap(logo_png).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif self.app_icon and not self.app_icon.isNull():
            icon_label.setPixmap(self.app_icon.pixmap(32, 32))
        else:
            icon_pixmap = QPixmap(32, 32)
            icon_pixmap.fill(Qt.transparent)
            painter = QPainter(icon_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            gradient = QLinearGradient(0, 0, 32, 32)
            gradient.setColorAt(0, QColor("#66c0f4"))
            gradient.setColorAt(1, QColor("#4a90d9"))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(0, 0, 32, 32, 8, 8)
            painter.setPen(QColor("#0f1520"))
            painter.setFont(QFont("Arial", 16, QFont.Bold))
            painter.drawText(icon_pixmap.rect(), Qt.AlignCenter, "S")
            painter.end()
            icon_label.setPixmap(icon_pixmap)
        logo_icon_row.addWidget(icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        app_name = QLabel("SALE TRACKER")
        app_name.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 800; letter-spacing: 1px;")
        text_col.addWidget(app_name)
        author = QLabel("by unrealest22")
        author.setStyleSheet("color: #3e4e62; font-size: 11px; font-weight: 500;")
        text_col.addWidget(author)
        logo_icon_row.addLayout(text_col)
        logo_icon_row.addStretch()

        logo_layout.addLayout(logo_icon_row)
        logo_layout.addStretch()
        sidebar_layout.addWidget(logo_wrap)

        nav_frame = QWidget()
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(4)

        self.nav_buttons = []
        nav_items = [
            ("Search", 0, "\U0001F50D"),
            ("Tracked Games", 1, "\u2764\uFE0F"),
            ("Settings", 2, "\u2699\uFE0F"),
            ("Link Steam Account", 3, "\U0001F517"),
        ]

        for label, idx, _icon in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFixedHeight(44)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))

            effect = QGraphicsOpacityEffect(btn)
            btn.setGraphicsEffect(effect)

            press_anim = QPropertyAnimation(effect, b"opacity", btn)
            press_anim.setDuration(80)
            press_anim.setStartValue(1.0)
            press_anim.setEndValue(0.5)
            press_anim.setEasingCurve(QEasingCurve.OutCubic)

            release_anim = QPropertyAnimation(effect, b"opacity", btn)
            release_anim.setDuration(180)
            release_anim.setStartValue(0.5)
            release_anim.setEndValue(1.0)
            release_anim.setEasingCurve(QEasingCurve.OutCubic)

            btn._press_anim = press_anim
            btn._release_anim = release_anim
            btn.pressed.connect(lambda a=press_anim: a.start())
            btn.released.connect(lambda a=release_anim: a.start())

            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_frame)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 20)
        footer_layout.setSpacing(8)

        self.status_label = QLabel("  Ready")
        self.status_label.setObjectName("statusLabel")
        footer_layout.addWidget(self.status_label)

        credits = QLabel(
            'v0.26 | <a href="https://github.com/unrealest22/Unreals-Steam-Sale-Tracker" '
            'style="color: #06b0d6; text-decoration: none;">GitHub</a>'
        )
        credits.setObjectName("creditsLabel")
        credits.setOpenExternalLinks(True)
        credits.setTextFormat(Qt.RichText)
        credits.setCursor(QCursor(Qt.PointingHandCursor))
        footer_layout.addWidget(credits)

        sidebar_layout.addWidget(footer)

        main_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.search_page = SearchPage(config)
        self.tracked_page = TrackedPage(config)
        self.settings_page = SettingsPage(config)
        self.link_steam_page = LinkSteamPage()
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.tracked_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.link_steam_page)
        main_layout.addWidget(self.stack)

        self.stack.currentChanged.connect(self._on_page_changed)

        self.search_page.game_added.connect(self._on_game_added)
        self.tracked_page.refresh_requested.connect(self._refresh_prices)
        self.settings_page.settings_changed.connect(self._on_settings_changed)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip(app_title)

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

        self.update_checker = UpdateChecker()
        self.update_checker.update_found.connect(self._on_update_found)
        self.update_checker.no_update.connect(lambda: self._update_status("Up to date."))
        self.update_checker.update_error.connect(lambda e: self._update_status("Update check failed."))
        self.update_checker.check_for_updates()

        if start_in_tray:
            self.hide()
        else:
            self.show()

    def _on_update_found(self, version, download_url, release_body):
        self._update_status(f"Update {version} available!")
        show_update_dialog(version, download_url, release_body, self)

    def _create_default_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 64, 64)
        gradient.setColorAt(0, QColor("#66c0f4"))
        gradient.setColorAt(1, QColor("#4a90d9"))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
        painter.setPen(QColor("#0f1520"))
        painter.setFont(QFont("Arial", 26, QFont.Bold))
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
            slide_in_from_right(widget, 280)
        if index == 1:
            self.tracked_page.refresh_cards()

    def _show_toast(self, message):
        toast = QLabel(message, self)
        toast.setObjectName("toastLabel")
        toast.setAlignment(Qt.AlignCenter)
        toast.setWordWrap(True)
        toast.adjustSize()
        toast.setFixedWidth(max(toast.width() + 50, 280))
        toast.setFixedHeight(toast.height() + 24)

        x = self.width() - toast.width() - 28
        y = self.height() - toast.height() - 28
        toast.move(x, y)
        toast.raise_()
        toast.show()

        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", toast)
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        QTimer.singleShot(2200, anim.start)
        anim.finished.connect(toast.deleteLater)

    def _on_game_added(self, game):
        self.tracked_page.refresh_cards()
        self._update_status(f"Now tracking: {game['name']} ({game.get('edition', 'N/A')})")
        self._show_toast(f"{game['name']} added to tracked games")
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
        body = f'"{name}" ({edition}) is {discount}% off!\nNow: {format_price(final_price, symbol)}'
        self.tray_icon.showMessage(title, body, self.app_icon, 10000)
        play_notification_sound(self.config)
        self._update_status(f"SALE: {name} ({edition}) -{discount}%")
        self._show_toast(f"SALE: {name} — {discount}% off!")

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
            self.tray_icon.showMessage(
                "Unreal's Sale Tracker",
                "Running in background. Click the tray icon to reopen.",
                self.app_icon, 3000
            )
        else:
            self._quit_app()

    def _quit_app(self):
        self.checker.stop()
        self.tray_icon.hide()
        QApplication.quit()
