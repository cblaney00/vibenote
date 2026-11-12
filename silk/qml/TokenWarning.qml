import QtQuick
import QtQuick.Effects

// Asks him to agree before Work uses his Claude tokens (his ask, 2026-10-30). It is part of
// the window, so it always sits in the middle of VibeNote.
Item {
    id: warn
    anchors.fill: parent
    visible: false
    z: 60
    property var info: ({})

    function ask() {
        info = bridge.workAsk()
        if (!info.text) return
        visible = true
        sheet.opacity = 0
        sheet.scale = 0.94
        popIn.restart()
        cancel.forceActiveFocus()
    }
    function close() { visible = false }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.01, 0.03, 0.02, 0.62)
        MouseArea { anchors.fill: parent; onClicked: warn.close() }
    }
    RectangularShadow {
        anchors.fill: sheet
        offset.y: 14
        blur: 40
        radius: 16
        color: Qt.rgba(0, 0, 0, 0.7)
        opacity: sheet.opacity
    }
    Rectangle {
        id: sheet
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 60)
        height: body.height + 56
        radius: 16
        color: C.paper
        border.color: C.accent
        border.width: 1
        ParallelAnimation {
            id: popIn
            NumberAnimation { target: sheet; property: "opacity"; to: 1; duration: 220 }
            NumberAnimation { target: sheet; property: "scale"; to: 1; duration: 320; easing.type: Easing.OutBack }
        }
        MouseArea { anchors.fill: parent }  // clicks on the sheet stay on it
        Column {
            id: body
            x: 28
            y: 26
            width: parent.width - 56
            spacing: 12
            Text {
                text: "⚠  This will use your Claude tokens"
                color: C.accent
                font { family: win.serif; pixelSize: 21; bold: true }
            }
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: warn.info.text || ""
                color: C.ink
                font { family: win.serif; pixelSize: 16 }
                lineHeight: 1.1
            }
            Text {
                width: parent.width
                visible: text !== ""
                wrapMode: Text.Wrap
                text: warn.info.cost || ""
                color: C.accent
                font { family: win.serif; pixelSize: 16 }
            }
            Text {
                width: parent.width
                visible: text !== ""
                wrapMode: Text.Wrap
                text: warn.info.usage || ""
                color: C.faded
                font { family: win.serif; pixelSize: 14 }
                lineHeight: 1.1
            }
            Item { width: 1; height: 4 }
            Row {
                anchors.right: parent.right
                spacing: 12
                SilkButton {
                    id: cancel
                    text: "Cancel"
                    focus: true
                    Keys.onEscapePressed: warn.close()
                    onClicked: warn.close()
                }
                SilkButton {
                    text: "I agree, start work"
                    main: true
                    onClicked: { warn.close(); bridge.workGo() }
                }
            }
        }
    }
}
