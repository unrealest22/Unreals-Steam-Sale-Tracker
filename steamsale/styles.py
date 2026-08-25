from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QAbstractAnimation
from PyQt5.QtWidgets import QGraphicsOpacityEffect

# i know this stylesheet is massive but qt styling is just like that
# i finally learned how to make a decent UI wit no vibecode, ggezzzz dud
STEAM_STYLESHEET = """
QWidget {
    background-color: #0f1520;
    color: #c7d5e0;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget#mainWidget {
    background-color: #0f1520;
}

QLabel {
    color: #c7d5e0;
    background: transparent;
}

QLabel#titleLabel {
    color: #ffffff;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
}

QLabel#subtitleLabel {
    color: #5a6a7e;
    font-size: 13px;
    font-weight: 400;
}

QLabel#sectionLabel {
    color: #66c0f4;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

QLabel#gameNameLabel {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}

QLabel#editionNameLabel {
    color: #7a8a9e;
    font-size: 12px;
    font-style: italic;
}

QLabel#statusLabel {
    color: #5a6a7e;
    font-size: 11px;
}

QLabel#loadingLabel {
    color: #66c0f4;
    font-size: 12px;
    font-weight: 600;
}

QLabel#errorLabel {
    color: #ef5350;
    font-size: 12px;
    font-weight: 600;
}

QLabel#priceLabel {
    color: #a4d65e;
    font-size: 18px;
    font-weight: 700;
}

QLabel#discountLabel {
    color: #1a3a1a;
    background-color: #a4d65e;
    font-size: 13px;
    font-weight: 800;
    padding: 4px 10px;
    border-radius: 4px;
}

QLabel#discountLabelSmall {
    color: #1a3a1a;
    background-color: #a4d65e;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 4px;
}

QLabel#origPriceStrikethrough {
    color: #5a6a7e;
    font-size: 13px;
    text-decoration: line-through;
}

QLabel#finalPriceGreen {
    color: #a4d65e;
    font-size: 15px;
    font-weight: 700;
}

QLabel#priceNormal {
    color: #e0e6ed;
    font-size: 15px;
    font-weight: 700;
}

QLabel#settingLabel {
    color: #c7d5e0;
    font-size: 13px;
    font-weight: 500;
}

QLabel#popularNameLabel {
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
}

QLabel#popularOrigLabel {
    color: #5a6a7e;
    font-size: 11px;
}

QLabel#typeBadgeLabel {
    color: #66c0f4;
    background-color: rgba(102, 192, 244, 0.12);
    font-size: 10px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 10px;
    letter-spacing: 0.5px;
}

QLabel#toastLabel {
    background-color: #1a2640;
    color: #ffffff;
    border: 1px solid rgba(102, 192, 244, 0.4);
    border-radius: 8px;
    padding: 14px 28px;
    font-size: 13px;
    font-weight: 600;
}

QLabel#creditsLabel {
    color: #3e4e62;
    font-size: 11px;
    background: transparent;
}

QLineEdit {
    background-color: #1a2236;
    color: #ffffff;
    border: 2px solid #1e2e44;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 14px;
    selection-background-color: #66c0f4;
}

QLineEdit:focus {
    border: 2px solid #66c0f4;
    background-color: #1e2840;
}

QLineEdit::placeholder {
    color: #4a5a70;
}

QPushButton {
    background-color: #1a2640;
    color: #66c0f4;
    border: 1px solid #1e2e44;
    border-radius: 8px;
    padding: 10px 22px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #223050;
    color: #ffffff;
    border-color: rgba(102, 192, 244, 0.3);
}

QPushButton:pressed {
    background-color: #0f1a2e;
}

QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #a4d65e, stop:1 #7cb342);
    color: #0f1520;
    border: none;
    border-radius: 10px;
    padding: 12px 32px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #b4e66e, stop:1 #8cc352);
}

QPushButton#primaryBtn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #94c64e, stop:1 #6ca332);
}

QPushButton#trackBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #a4d65e, stop:1 #7cb342);
    color: #0f1520;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 700;
    min-width: 70px;
}

QPushButton#trackBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #b4e66e, stop:1 #8cc352);
}

QPushButton#trackBtn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #94c64e, stop:1 #6ca332);
}

QPushButton#browseBtn, QPushButton#testBtn {
    background-color: #4c6b22;
    color: #ffffff;
    border: 1px solid #4c6b22;
    border-radius: 6px;
    padding: 8px 22px;
    font-size: 12px;
    font-weight: 700;
    min-width: 80px;
}

QPushButton#browseBtn:hover, QPushButton#testBtn:hover {
    background-color: #5e8a2c;
    border-color: #5e8a2c;
}

QPushButton#browseBtn:pressed, QPushButton#testBtn:pressed {
    background-color: #3d5a1b;
    border-color: #3d5a1b;
}

QPushButton#navBtn {
    background-color: transparent;
    color: #5a6a7e;
    border: none;
    border-radius: 8px;
    padding: 14px 20px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
}

QPushButton#navBtn:hover {
    color: #c7d5e0;
    background-color: rgba(102, 192, 244, 0.08);
}

QPushButton#navBtn:checked {
    color: #66c0f4;
    background-color: rgba(102, 192, 244, 0.12);
    border-left: none;
}

QPushButton#dangerBtn {
    background-color: transparent;
    color: #5a6a7e;
    border: none;
    padding: 6px;
    border-radius: 6px;
}

QPushButton#dangerBtn:hover {
    background-color: rgba(239, 83, 80, 0.12);
    color: #ef5350;
}

QComboBox {
    background-color: #1a2236;
    color: #ffffff;
    border: 2px solid #1e2e44;
    border-radius: 10px;
    padding: 10px 16px;
    min-width: 180px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: rgba(102, 192, 244, 0.4);
}

QComboBox:focus {
    border-color: #66c0f4;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #66c0f4;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #1e2e44;
    color: #c7d5e0;
    border: 1px solid #2a3e58;
    selection-background-color: #2a475e;
    selection-color: #ffffff;
    outline: none;
    padding: 6px;
    border-radius: 8px;
}

QCheckBox {
    color: #c7d5e0;
    font-size: 13px;
    spacing: 12px;
    padding: 8px 0;
    background: transparent;
}

QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 2px solid #1e2e44;
    border-radius: 6px;
    background: transparent;
}

QCheckBox::indicator:hover {
    border-color: #66c0f4;
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #a4d65e, stop:1 #7cb342);
    border: 2px solid #a4d65e;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    border: none;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #1e2e44;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #2a3e58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
    border: none;
}

QScrollBar:horizontal {
    height: 0px;
    background: none;
    border: none;
}

QFrame#gameCard {
    background-color: #151e30;
    border: 1px solid #1e2e44;
    border-radius: 12px;
}

QFrame#gameCard QWidget {
    background: transparent;
}

QFrame#gameCard:hover {
    border-color: rgba(102, 192, 244, 0.3);
    background-color: #182238;
}

QFrame#editionCard {
    background-color: rgba(15, 21, 32, 0.6);
    border: 1px solid #1e2e44;
    border-radius: 8px;
}

QFrame#editionCard:hover {
    border-color: rgba(102, 192, 244, 0.25);
}

QFrame#popularCard {
    background-color: #151e30;
    border: 1px solid #1e2e44;
    border-radius: 12px;
}

QFrame#popularCard:hover {
    border-color: rgba(102, 192, 244, 0.3);
    background-color: #182238;
}

QFrame#settingsCard {
    background-color: #151e30;
    border: 1px solid #1e2e44;
    border-radius: 12px;
    padding: 24px;
}

QFrame#settingsCard QWidget {
    background: transparent;
}

QFrame#settingsCard:hover {
    border-color: rgba(102, 192, 244, 0.2);
}

QFrame#separator {
    background-color: #1e2e44;
    max-height: 1px;
    min-height: 1px;
}

QFrame#navBar {
    background-color: #0b1018;
    border-right: 1px solid #1a2436;
}

QMenu {
    background-color: #1a2236;
    border: 1px solid #1e2e44;
    color: #c7d5e0;
    padding: 8px;
    border-radius: 8px;
}

QMenu::item {
    padding: 10px 32px 10px 16px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #223050;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #1e2e44;
    margin: 4px 8px;
}
"""


def slide_in_from_right(widget, duration=300):
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    target_pos = widget.pos()
    anim.setStartValue(target_pos + QPoint(40, 0))
    anim.setEndValue(target_pos)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def fade_in(widget, duration=400):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return anim


def fade_out(widget, duration=300):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return anim
