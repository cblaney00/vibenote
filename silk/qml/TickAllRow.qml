import QtQuick

// One place to tick everything (his ask, 2026-11-02): every waiting note for Send,
// everything open for Work, or untick it all.
Item {
    width: ListView.view ? ListView.view.width : 600
    height: 34
    Row {
        x: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 18
        Text {
            text: "Tick all:"
            color: C.faded
            font { family: win.serif; pixelSize: 15 }
        }
        Repeater {
            model: [["Send", "send", C.accent], ["Work", "work", C.jade], ["Untick all", "none", C.faded]]
                   .filter(function (m) { return !(bridge.isLando && m[1] === "work") })
            delegate: Rectangle {
                required property var modelData
                width: t.implicitWidth + 20
                height: 26
                radius: 7
                color: a.containsMouse ? C.picked : "transparent"
                border.color: a.containsMouse ? modelData[2] : C.rule
                Text {
                    id: t
                    anchors.centerIn: parent
                    text: modelData[0]
                    color: modelData[2]
                    font { family: win.serif; pixelSize: 15 }
                }
                MouseArea {
                    id: a
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bridge.tickAll(modelData[1])
                }
            }
        }
    }
}
