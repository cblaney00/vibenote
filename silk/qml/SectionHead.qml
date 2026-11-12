import QtQuick

// A section's title (with its token total), a copper thread drawing itself out beside it, and
// "Send" / "Work" words that tick or untick the whole section. A group heading (after
// Organize) is a quiet copper line instead.
Item {
    id: head
    property var info
    readonly property bool group: info.type === "group"
    width: ListView.view ? ListView.view.width : 600
    height: group ? 34 : info.key === "waiting" ? 34 : 54
    Text {
        id: label
        x: head.group ? 48 : 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        text: head.group ? info.title + "  ·  " + info.total
              : info.title + " · " + info.count + (info.total ? "  ·  " + info.total + " tokens" : "")
        color: head.group ? C.peach : info.key === "waiting" ? C.accent : C.faded
        opacity: head.group ? 0.8 : 1
        font { family: win.serif; pixelSize: head.group ? 14 : 15; letterSpacing: 0.4; italic: head.group }
    }
    Row {
        id: ticks
        visible: !head.group
        anchors { right: parent.right; rightMargin: 10; verticalCenter: label.verticalCenter }
        spacing: 16
        Repeater {
            model: head.group ? [] : [["Send", "send", info.send], ["Work", "work", info.work]]
            delegate: Text {
                required property var modelData
                visible: modelData[2]
                text: modelData[0]
                color: ta.containsMouse ? C.peach : modelData[1] === "send" ? C.accent : C.jade
                font { family: win.serif; pixelSize: 15 }
                MouseArea {
                    id: ta
                    anchors.fill: parent
                    anchors.margins: -5
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bridge.tickSection(head.info.key, modelData[1])
                }
            }
        }
    }
    Rectangle {
        visible: !head.group
        anchors { left: label.right; leftMargin: 14; verticalCenter: label.verticalCenter }
        height: 1
        color: C.margin
        width: 0
        NumberAnimation on width {
            to: Math.max(0, head.width - label.width - label.x - ticks.width - 50)
            duration: 900
            easing.type: Easing.OutCubic
        }
    }
}
