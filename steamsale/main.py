import sys
from PyQt5.QtWidgets import QApplication

from .config import load_config
from .styles import STEAM_STYLESHEET
from .window import MainWindow

def main():
    start_in_tray = "--tray" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("Steam Sale Tracker")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STEAM_STYLESHEET)
    config = load_config()
    window = MainWindow(config, start_in_tray=start_in_tray)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()