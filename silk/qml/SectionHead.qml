import QtQuick

// A section's title, with a copper thread drawing itself out beside it.
Item {
    property var info
    width: ListView.view ? ListView.view.width : 600
    height: info.key === "waiting" ? 34 : 54
    Text {
        id: label
        x: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        text: info.title + " · " + info.count
        color: info.key === "waiting" ? C.accent : C.faded
        font { family: win.serif; pixelSize: 15; letterSpacing: 0.4 }
    }
    Rectangle {
        anchors { left: label.right; leftMargin: 14; verticalCenter: label.verticalCenter }
        height: 1
        color: C.margin
        width: 0
        NumberAnimation on width {
            to: Math.max(0, parent.width - label.width - 40)
            duration: 900
            easing.type: Easing.OutCubic
        }
    }
}
