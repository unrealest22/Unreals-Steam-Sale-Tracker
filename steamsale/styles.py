from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint

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