Unreal's Steam Sale Tracker
A desktop application that tracks Steam game prices and sends notifications when games go on sale.

--Features--

• Tracks specific game editions (Standard, Deluxe, Ultimate, etc.)
• Regional pricing support (USD, PHP, GBP, etc.)
• Desktop notifications with custom sounds (You can upload your own! file format supports mp3 and wav)
• System tray background mode (Can be disabled in settings)
• Run on startup (Also can be disabled in settings)
• Popular searches feed

--How to run from source--
1. Install Python 3.8+
2. Install requirements: pip install PyQt5
3. Run the app: "python -m steamsale.main"

How to build the .exe
Make sure PyInstaller is installed (pip install pyinstaller), then run:

``
python -m PyInstaller --noconfirm --onefile --windowed --name "SteamSaleTracker" --icon "steamsale/steamsale.ico" --add-data "steamsale/steamsale.ico;steamsale" --add-data "steamsale/fartsound.mp3;steamsale" --add-data "steamsale/ButterflyDing.mp3;steamsale" --add-data "steamsale/barkfart.mp3;steamsale" run.py
``
