import os
import sys
import threading

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QSystemTrayIcon, QMenu, QAction, QApplication, QMessageBox,
    QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QColor, QFont, QPixmap, QCursor, QPainter

from .config import format_price
from .styles import STEAM_STYLESHEET, slide_in_from_right
from .sounds import play_notification_sound
from .pages import SearchPage, TrackedPage, SettingsPage
from .checker import PriceChecker
from .updater import UpdateChecker, download_and_install

class MainWindow(QMainWindow):
    def __init__(self, config, start_in_tray=False):
        super().__init__()
        
        # ── Windows Taskbar Fix ──
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("steam.sale.tracker")
        
        self.config = config
        self.start_in_tray = start_in_tray
        
        app_title = "Unreal's Sale Tracker"
        self.setWindowTitle(app_title)
        
        # ── Load Custom Icon (steamsale.ico) ──
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
        
        # ── Credits ──
        credits_label = QLabel(
            'Unreal\'s Sale Tracker v0.2<br>'
            'Original repo: <a href="https://github.com/unrealest22/Unreals-Steam-Sale-Tracker" style="color: #66c0f4;">GitHub</a>'
        )
        credits_label.setOpenExternalLinks(True)
        credits_label.setTextFormat(Qt.RichText)
        credits_label.setObjectName("statusLabel")
        credits_label.setStyleSheet("padding: 0px 16px 16px 16px;")
        credits_label.setWordWrap(True)
        credits_label.setCursor(QCursor(Qt.PointingHandCursor))
        nav_layout.addWidget(credits_label)
        
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
        
        # ── Check for updates on startup ──
        self.update_checker = UpdateChecker()
        self.update_checker.update_found.connect(self._on_update_found)
        self.update_checker.no_update.connect(lambda: self._update_status("Up to date."))
        self.update_checker.update_error.connect(lambda e: self._update_status("Update check failed."))
        self.update_checker.check_for_updates()
        
        if start_in_tray:
            self.hide()
        else:
            self.show()

    def _on_update_found(self, version, download_url):
        self._update_status(f"Update {version} available!")
        reply = QMessageBox.question(self, 'Update Available',
            f"A new version ({version}) is available!\n\nWould you like to update now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            download_and_install(download_url, self)

    def _create_default_icon(self):
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

    def _show_toast(self, message):
        """Shows a temporary fading notification in the bottom right."""
        toast = QLabel(message, self)
        toast.setObjectName("toastLabel")
        toast.setAlignment(Qt.AlignCenter)
        toast.setWordWrap(True)
        
        # Size and position
        toast.adjustSize()
        toast.setFixedWidth(toast.width() + 40)
        toast.setFixedHeight(toast.height() + 20)
        x = self.width() - toast.width() - 30
        y = self.height() - toast.height() - 30
        toast.move(x, y)
        toast.raise_()
        toast.show()
        
        # Fade out animation
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", toast)
        anim.setDuration(500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # Wait 2 seconds, then fade out, then delete
        QTimer.singleShot(2000, anim.start)
        anim.finished.connect(toast.deleteLater)

    def _on_game_added(self, game):
        self.tracked_page.refresh_cards()
        self._update_status(f"Now tracking: {game['name']} ({game.get('edition', 'N/A')})")
        self._show_toast(f"{game['name']} has been added to Tracked Games!")
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
        self.tray_icon.showMessage(title, body, self.app_icon, 10000)
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
            self.tray_icon.showMessage("Unreal's Sale Tracker", "Running in background. Click the tray icon to reopen.", self.app_icon, 3000)
        else:
            self._quit_app()

    def _quit_app(self):
        self.checker.stop()
        self.tray_icon.hide()
        QApplication.quit()