import QtQuick

// The box for a new note: it grows with the note; Enter adds it (and sends a ripple).
Item {
    id: entry
    height: Math.max(54, input.contentHeight + 30)
    Behavior on height { SpringAnimation { spring: 4; damping: 0.35 } }
    Rectangle {
        anchors.fill: parent
        radius: 12
        color: Qt.rgba(0.04, 0.09, 0.07, 0.78)
        border.width: 1
        border.color: input.activeFocus ? C.accent : C.rule
        Behavior on border.color { ColorAnimation { duration: 260 } }
    }
    TextEdit {
        id: input
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
        anchors { leftMargin: 18; rightMargin: 18 }
        wrapMode: TextEdit.Wrap
        color: C.ink
        selectionColor: C.picked
        selectedTextColor: C.ink
        font { family: win.serif; pixelSize: 19 }
        Keys.onPressed: (e) => {
            if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !(e.modifiers & Qt.ShiftModifier)) {
                if (input.text.trim() !== "") {
                    bridge.addNote(input.text)
                    var at = entry.mapToItem(root, entry.width / 2, entry.height / 2)
                    win.ripple(at.x, at.y, 1.2)
                    input.text = ""
                }
                e.accepted = true
            }
        }
    }
    Text {
        anchors { left: input.left; verticalCenter: parent.verticalCenter }
        visible: input.text === "" && !input.activeFocus
        text: "Write a note and press Enter…"
        color: C.faded
        font: input.font
    }
    MouseArea {
        anchors.fill: parent
        z: -1
        cursorShape: Qt.IBeamCursor
        onPressed: input.forceActiveFocus()
    }
}
