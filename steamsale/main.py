import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QLocalSocket, QLocalServer

from .config import load_config
from .styles import STEAM_STYLESHEET
from .window import MainWindow

def main():
    start_in_tray = "--tray" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("Steam Sale Tracker")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STEAM_STYLESHEET)

    # ── Single Instance Lock ──
    server_name = "UnrealsSteamSaleTracker"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    
    if socket.waitForConnected(100):
        # Another instance is already running. Tell it to show itself.
        socket.write(b"show")
        socket.waitForBytesWritten(100)
        sys.exit(0)
        
    # No other instance running. Start the local server to listen for future attempts.
    QLocalServer.removeServer(server_name) # Clean up if it crashed previously
    server = QLocalServer()
    server.listen(server_name)
    
    config = load_config()
    window = MainWindow(config, start_in_tray=start_in_tray)
    
    # When a second instance tries to open, it sends a "show" message. 
    # We catch it here and bring the window to the front.
    def _on_new_connection():
        server.nextPendingConnection()
        window._show_from_tray()
        
    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()