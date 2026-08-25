import os
import sys
import re
import json
import urllib.request
import subprocess
import tempfile
import shutil
import threading

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QMessageBox, QApplication, QDialog, QVBoxLayout, QLabel,
    QTextBrowser, QPushButton, QHBoxLayout
)

GITHUB_REPO = "unrealest22/Unreals-Steam-Sale-Tracker"
CURRENT_VERSION = "v0.26"

class UpdateChecker(QObject):
    update_found = pyqtSignal(str, str, str)
    no_update = pyqtSignal()
    update_error = pyqtSignal(str)

    def check_for_updates(self):
        def _check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "UnrealsSaleTracker"})

                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                latest_version = data.get("tag_name", "v0.0")
                if latest_version > CURRENT_VERSION:
                    download_url = None
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".exe"):
                            download_url = asset["browser_download_url"]
                            break

                    release_body = data.get("body", "")
                    if download_url:
                        self.update_found.emit(latest_version, download_url, release_body)
                    else:
                        self.no_update.emit()
                else:
                    self.no_update.emit()
            except Exception as e:
                print(f"[WARN] Update check failed: {e}")
                self.no_update.emit()

        t = threading.Thread(target=_check, daemon=True)
        t.start()

def strip_images_from_markdown(text):
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
    return text.strip()

def show_update_dialog(version, download_url, release_body, parent_window):
    dialog = QDialog(parent_window)
    dialog.setWindowTitle(f"Update Available — {version}")
    dialog.setMinimumSize(480, 400)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 20, 20, 20)

    title = QLabel(f"A new version ({version}) is available!")
    title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
    layout.addWidget(title)

    if release_body:
        clean_body = strip_images_from_markdown(release_body)
        if clean_body:
            changelog_label = QLabel("What's new:")
            changelog_label.setStyleSheet("color: #8f98a0; font-size: 13px; font-weight: bold;")
            layout.addWidget(changelog_label)

            changelog = QTextBrowser()
            changelog.setOpenExternalLinks(True)
            changelog.setMarkdown(clean_body)
            changelog.setStyleSheet(
                "background-color: #1b2838; color: #c7d5e0; border: 1px solid #2a475e; "
                "border-radius: 6px; padding: 12px; font-size: 13px;"
            )
            layout.addWidget(changelog)

    btn_row = QHBoxLayout()
    btn_row.addStretch()

    later_btn = QPushButton("Later")
    later_btn.setStyleSheet(
        "QPushButton { background-color: #2a475e; color: #c7d5e0; border: 1px solid #2a475e; "
        "border-radius: 3px; padding: 8px 24px; font-size: 13px; font-weight: bold; }"
        "QPushButton:hover { background-color: #316282; }"
    )
    later_btn.clicked.connect(dialog.reject)
    btn_row.addWidget(later_btn)

    update_btn = QPushButton("Update Now")
    update_btn.setStyleSheet(
        "QPushButton { background-color: #4c6b22; color: #ffffff; border: 1px solid #4c6b22; "
        "border-radius: 3px; padding: 8px 24px; font-size: 13px; font-weight: bold; }"
        "QPushButton:hover { background-color: #5e8a2c; }"
    )
    update_btn.clicked.connect(lambda: (dialog.accept(), download_and_install(download_url, parent_window)))
    btn_row.addWidget(update_btn)

    layout.addLayout(btn_row)
    dialog.exec_()

def download_and_install(download_url, parent_window):
    try:
        progress = QMessageBox(parent_window)
        progress.setWindowTitle("Updating")
        progress.setText("Downloading update... Please wait.")
        progress.setStandardButtons(QMessageBox.NoButton)
        progress.show()

        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            progress.close()
            QMessageBox.warning(parent_window, "Update", "Auto-update only works on the compiled .exe version.")
            return

        temp_dir = tempfile.gettempdir()
        temp_exe = os.path.join(temp_dir, "UnrealsSaleTracker_update.exe")

        req = urllib.request.Request(download_url, headers={"User-Agent": "UnrealsSaleTracker"})
        with urllib.request.urlopen(req, timeout=60) as response, open(temp_exe, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        progress.close()

        batch_path = os.path.join(temp_dir, "steam_updater.bat")
        # loop until the old exe is gone — windows holds locks on running processes
        batch_content = f"""
@echo off
:wait_loop
timeout /t 1 /nobreak >nul
del "{current_exe}" 2>nul
if exist "{current_exe}" goto wait_loop
move /y "{temp_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
        with open(batch_path, "w") as f:
            f.write(batch_content)

        subprocess.Popen(['cmd', '/c', batch_path], creationflags=subprocess.CREATE_NO_WINDOW)
        # force exit so windows releases the exe lock immediately
        os._exit(0)

    except Exception as e:
        QMessageBox.critical(parent_window, "Update Failed", f"Failed to download update:\n{e}")
