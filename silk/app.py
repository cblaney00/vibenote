"""VibeNote's Silk window: the same notes, drawn on the graphics card with Qt Quick.

Run: ./run-silk.sh (from the project folder). See docs/silk-rebuild.md.
"""

import json
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

import sender  # noqa: E402
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


def hypr_size():
    """This window's size as his desktop has it, or None."""
    try:
        out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, timeout=3,
                             text=True).stdout
        for c in json.loads(out or "[]"):
            if c.get("pid") == os.getpid():
                return tuple(c["size"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    return None


def place(size, tries=8):
    """Float at w x h in the middle of the screen. His desktop places a new window itself a
    moment after it appears, and otherwise reuses the last floating size (the whole app's,
    which kept the mini big: his catch, 2026-11-12), so check again until it sticks."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return
    w, h = size()  # read each time: the mini's height settles once its bars are in
    now = hypr_size()
    if now != (w, h):
        me = f"pid:{os.getpid()}"
        for args in (["setfloating", me], ["resizewindowpixel", f"exact {w} {h},{me}"],
                     ["centerwindow"]):
            try:
                subprocess.run(["hyprctl", "dispatch", *args], capture_output=True, timeout=3)
            except (OSError, subprocess.SubprocessError):
                return
    if tries > 1:  # keep checking: his desktop may put back a remembered size a moment later
        QTimer.singleShot(400, lambda: place(size, tries - 1))


def main():
    # Qt's own messages (and console.log from the QML) go to the terminal
    qInstallMessageHandler(lambda kind, where, text: print(text, file=sys.stderr))
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("VibeNote")
    app.setDesktopFileName("vibenote")
    icon = HERE.parent / "assets" / "icon.svg"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    engine = QQmlApplicationEngine()
    for d in qml_dirs():
        engine.addImportPath(d)
    sender.close_other_copies()  # one VibeNote at a time (his catch, 2026-11-02)
    bridge = Bridge(lando="--lando" in sys.argv or sender.LANDO)
    if os.environ.get("VIBENOTE_OPEN"):  # for testing: open on this project
        bridge.pick(os.environ["VIBENOTE_OPEN"])
    ctx = engine.rootContext()
    ctx.setContextProperty("bridge", bridge)
    ctx.setContextProperty("C", COLOURS)
    ctx.setContextProperty("shaders", QUrl.fromLocalFile(str(HERE / "shaders")).toString())
    engine.warnings.connect(lambda ws: [print("QML:", w.toString(), file=sys.stderr)
                                        for w in ws])
    shown = []
    # VibeNote quits when he closes its window, not when one window hands over to the other
    app.setQuitOnLastWindowClosed(False)
    switching = [False]

    def show(which):
        """The mini player and the whole app hand over to each other; "usage" and "tips"
        open the whole app on the usage page."""
        if which in ("usage", "tips"):
            bridge.setView("usage")
        name = "Mini.qml" if which == "mini" else "Main.qml"
        before = list(engine.rootObjects())
        engine.load(QUrl.fromLocalFile(str(HERE / "qml" / name)))
        shown[:] = [o for o in engine.rootObjects() if o not in before]
        for new in shown:
            new.closing.connect(lambda _e: switching[0] or app.quit())
        switching[0] = True
        for old in before:  # the new one is open first, so there is always a window
            old.close()
            old.deleteLater()
        switching[0] = False
        if which == "mini" and shown:
            mini = shown[0]

            def size():
                return 370, int(mini.property("wantHeight"))

            # the desktop decides a window's size, and puts back one it remembers a moment after
            # the window appears: tell it again whenever the two differ (a few times at most)
            fixes = [0]

            def drifted(*_):
                if (mini.width(), mini.height()) != size() and fixes[0] < 10:
                    fixes[0] += 1
                    QTimer.singleShot(80, lambda: place(size, 3))

            mini.wantHeightChanged.connect(drifted)
            mini.heightChanged.connect(drifted)
            mini.widthChanged.connect(drifted)
        else:
            def size():
                return 1120, 780
        QTimer.singleShot(200, lambda: place(size))

    bridge.wantWindow.connect(show)
    small = ("--mini" in sys.argv or bridge.startSmall) and "--full" not in sys.argv
    view = sys.argv[sys.argv.index("--view") + 1] if "--view" in sys.argv[:-1] else None
    if view in ("usage", "tips") and not small:
        bridge.setView("usage")
    show("mini" if small else "notes")
    if not engine.rootObjects():
        sys.exit(1)
    shot = os.environ.get("VIBENOTE_SHOT")  # for testing: "file.png,seconds"
    if shot:
        path, wait = (shot.split(",") + ["4"])[:2]
        def grab():
            shown[0].grabWindow().save(path)
            app.quit()

        QTimer.singleShot(int(float(wait) * 1000), grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
