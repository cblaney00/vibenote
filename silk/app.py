"""VibeNote's Silk window: the same notes, drawn on the graphics card with Qt Quick.

Run: ./run-silk.sh (from the project folder). See docs/silk-rebuild.md.
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # store.py, projects.py, sender.py

from PyQt6 import QtQuick, QtQuick3D  # noqa: E402,F401  (loads Qt Quick's libraries)
from PyQt6.QtCore import QTimer, QUrl, qInstallMessageHandler  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PyQt6.QtQml import QQmlApplicationEngine  # noqa: E402

from bridge import Bridge  # noqa: E402

# Colours, the same as the Tk app's (emerald silk, copper and peach; dim for his eyes)
COLOURS = {
    "paper": "#0e1c17", "sidebar": "#0a1511", "picked": "#173027", "ink": "#dccdb2",
    "faded": "#7f8c7a", "rule": "#1f3a30", "accent": "#c08457", "peach": "#d79a74",
    "field": "#132820", "jade": "#7fb08a", "card": "#132a21", "margin": "#5a3f2c",
}


def qml_dirs():
    """Where Qt Quick's QML modules are: next to the Qt libraries this process loaded. They
    are part of PyQt6's install but not on its search path here."""
    found = []
    with open("/proc/self/maps") as maps:
        for line in maps:
            path = line.split()[-1] if "/lib/libQt6" in line else ""
            if path:
                qml = path.split("/lib/libQt6")[0] + "/lib/qt-6/qml"
                if os.path.isdir(qml) and qml not in found:
                    found.append(qml)
    return found


def float_on_hyprland():
    """His desktop tiles new windows; this one floats, like the Tk VibeNote."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return
    me = f"pid:{os.getpid()}"
    for args in (["setfloating", me], ["resizewindowpixel", f"exact 1120 780,{me}"],
                 ["centerwindow"]):
        try:
            subprocess.run(["hyprctl", "dispatch", *args], capture_output=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            return


def main():
    # Qt's own messages (and console.log from the QML) go to the terminal
    qInstallMessageHandler(lambda kind, where, text: print(text, file=sys.stderr))
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("VibeNote")
    app.setDesktopFileName("vibenote")
    app.setWindowIcon(QIcon(str(HERE.parent / "assets" / "icon.svg")))
    engine = QQmlApplicationEngine()
    for d in qml_dirs():
        engine.addImportPath(d)
    bridge = Bridge(lando="--lando" in sys.argv)
    if os.environ.get("VIBENOTE_OPEN"):  # for testing: open on this project
        bridge.pick(os.environ["VIBENOTE_OPEN"])
    ctx = engine.rootContext()
    ctx.setContextProperty("bridge", bridge)
    ctx.setContextProperty("C", COLOURS)
    ctx.setContextProperty("shaders", QUrl.fromLocalFile(str(HERE / "shaders")).toString())
    engine.warnings.connect(lambda ws: [print("QML:", w.toString(), file=sys.stderr)
                                        for w in ws])
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    QTimer.singleShot(200, float_on_hyprland)
    shot = os.environ.get("VIBENOTE_SHOT")  # for testing: "file.png,seconds"
    if shot:
        path, wait = (shot.split(",") + ["4"])[:2]
        window = engine.rootObjects()[0]

        def grab():
            window.grabWindow().save(path)
            app.quit()

        QTimer.singleShot(int(float(wait) * 1000), grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
