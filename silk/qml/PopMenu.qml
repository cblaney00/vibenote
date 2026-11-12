import QtQuick
import QtQuick.Effects

// A small silk menu at the mouse: Later / Now / Move to another project.
Item {
    id: menu
    anchors.fill: parent
    visible: false
    z: 50
    property string noteId: ""
    property var items: []

    function openAt(id, x, y) {
        noteId = id
        items = bridge.moveTargets(id)
        if (!items.length) return
        box.x = Math.min(x, width - box.width - 8)
        var tall = items.length * 36 + 12  // the box's height before it has laid out
        box.y = y + tall > height - 8 ? Math.max(8, y - tall) : y
        visible = true
        box.scale = 0.92
        box.opacity = 0
        popIn.restart()
    }

    MouseArea {  // a click anywhere else closes it
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: menu.visible = false
    }
    RectangularShadow {
        anchors.fill: box
        offset.y: 8
        blur: 26
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.6)
        opacity: box.opacity
    }
    Rectangle {
        id: box
        width: 280
        height: col.height + 12
        radius: 10
        color: C.field
        border.color: C.rule
        transformOrigin: Item.TopLeft
        ParallelAnimation {
            id: popIn
            NumberAnimation { target: box; property: "scale"; to: 1; duration: 220; easing.type: Easing.OutBack }
            NumberAnimation { target: box; property: "opacity"; to: 1; duration: 160 }
        }
        Column {
            id: col
            y: 6
            width: parent.width
            Repeater {
                model: menu.items
                delegate: Rectangle {
                    required property var modelData
                    width: col.width
                    height: 36
                    color: ma.containsMouse ? C.picked : "transparent"
                    Text {
                        x: 16
                        width: parent.width - 28
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: modelData.label
                        color: modelData.act === "move" ? C.ink : C.peach
                        font { family: win.serif; pixelSize: 16 }
                    }
                    MouseArea {
                        id: ma
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            menu.visible = false
                            var a = modelData.act
                            if (a === "later") bridge.later(menu.noteId)
                            else if (a === "now") bridge.now(menu.noteId)
                            else bridge.moveNote(menu.noteId, modelData.slug)
                        }
                    }
                }
            }
        }
    }
}
