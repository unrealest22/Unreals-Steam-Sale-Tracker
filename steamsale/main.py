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

    server_name = "UnrealsSaleTracker"
    # this whole block is so two instances of the app dont run at the same time
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    
    if socket.waitForConnected(100):
        socket.write(b"show")
        socket.waitForBytesWritten(100)
        sys.exit(0)
        
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.listen(server_name)
    
    config = load_config()
    window = MainWindow(config, start_in_tray=start_in_tray)
    
    def _on_new_connection():
        server.nextPendingConnection()
        window._show_from_tray()
        
    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()