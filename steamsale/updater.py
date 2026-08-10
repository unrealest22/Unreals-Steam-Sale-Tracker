import os
import sys
import json
import urllib.request
import subprocess
import tempfile
import shutil
import threading

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QApplication

# Repo details
GITHUB_REPO = "unrealest22/Unreals-Steam-Sale-Tracker"
CURRENT_VERSION = "v0.2"

class UpdateChecker(QObject):
    update_found = pyqtSignal(str, str)  # version, download_url
    no_update = pyqtSignal()
    update_error = pyqtSignal(str)

    def check_for_updates(self):
        def _check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "SteamSaleTracker"})
                
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                
                latest_version = data.get("tag_name", "v0.0")
                if latest_version > CURRENT_VERSION:
                    # Find the exe asset
                    download_url = None
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".exe"):
                            download_url = asset["browser_download_url"]
                            break
                    
                    if download_url:
                        self.update_found.emit(latest_version, download_url)
                    else:
                        self.no_update.emit()
                else:
                    self.no_update.emit()
            except Exception as e:
                # Silently fail or emit error. We don't want to crash the app.
                print(f"[WARN] Update check failed: {e}")
                self.no_update.emit() # Emit no_update so the UI just says "Up to date" instead of erroring
        
        # Use standard threading instead of QThread to avoid GC issues
        t = threading.Thread(target=_check, daemon=True)
        t.start()

def download_and_install(download_url, parent_window):
    """Downloads the new exe and triggers a batch script to swap it."""
    try:
        # Show a simple progress message
        progress = QMessageBox(parent_window)
        progress.setWindowTitle("Updating")
        progress.setText("Downloading update... Please wait.")
        progress.setStandardButtons(QMessageBox.NoButton)
        progress.show()

        # Get current exe path
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            progress.close()
            QMessageBox.warning(parent_window, "Update", "Auto-update only works on the compiled .exe version.")
            return

        # Download to temp file
        temp_dir = tempfile.gettempdir()
        temp_exe = os.path.join(temp_dir, "SteamSaleTracker_update.exe")
        
        req = urllib.request.Request(download_url, headers={"User-Agent": "SteamSaleTracker"})
        with urllib.request.urlopen(req, timeout=60) as response, open(temp_exe, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        progress.close()

        # Create a batch script to replace the exe
        # It waits for the current app to close, deletes the old exe, renames the new one, and starts it.
        batch_path = os.path.join(temp_dir, "steam_updater.bat")
        batch_content = f"""
@echo off
timeout /t 2 /nobreak >nul
del "{current_exe}"
move /y "{temp_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
        with open(batch_path, "w") as f:
            f.write(batch_content)

        # Execute the batch script silently and quit the app
        subprocess.Popen(['cmd', '/c', batch_path], creationflags=subprocess.CREATE_NO_WINDOW)
        QApplication.quit()

    except Exception as e:
        QMessageBox.critical(parent_window, "Update Failed", f"Failed to download update:\n{e}")