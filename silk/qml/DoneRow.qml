import QtQuick

// A finished note: no card, just a line of copper-ticked thread, brightening under the mouse.
Item {
    id: row
    property var note
    width: ListView.view ? ListView.view.width : 600
    height: label.height + 10
    HoverHandler { id: hh }
    property real glow: (hh.hovered || win.flashId === note.id) ? 1 : 0
    Behavior on glow { NumberAnimation { duration: 220 } }
    Text {
        id: tick
        x: 18
        y: 4
        text: "✓"
        color: C.accent
        font { family: win.serif; pixelSize: 16 }
    }
    Text {
        id: label
        x: 46 + row.glow * 4
        y: 4
        width: parent.width - x - when.width - 24
        text: row.note.text
        wrapMode: Text.Wrap
        color: Qt.tint(C.faded, Qt.rgba(0.86, 0.80, 0.70, row.glow * 0.5))
        font { family: win.serif; pixelSize: 16 }
    }
    Text {
        id: when
        anchors.right: parent.right
        anchors.rightMargin: 12
        y: 5
        text: row.note.when
        color: C.faded
        opacity: 0.4 + row.glow * 0.6
        font { family: win.serif; pixelSize: 14 }
    }
}
