import QtQuick

// List · Board · Sky · Timeline · Compact (his ask, 2026-11-12), over the sky.
Row {
    spacing: 4
    Repeater {
        model: [["list", "List"], ["board", "Board"], ["sky", "Sky"], ["timeline", "Timeline"], ["compact", "Compact"]]
        delegate: Item {
            required property var modelData
            readonly property bool lit: bridge.layout === modelData[0]
            width: t.implicitWidth + 18
            height: 30
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: Qt.rgba(0.03, 0.08, 0.06, 0.6)
                border.color: parent.lit ? C.accent : a.containsMouse ? C.rule : "transparent"
            }
            Text {
                id: t
                anchors.centerIn: parent
                text: modelData[1]
                color: parent.lit ? C.peach : a.containsMouse ? C.ink : C.faded
                font { family: win.serif; pixelSize: 15 }
            }
            MouseArea {
                id: a
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: bridge.setLayout(modelData[0])
            }
        }
    }
}
