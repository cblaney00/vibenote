import QtQuick
import QtQuick.Effects

// The sidebar: a darker fold of the same silk, his projects (pinned first), the "good time?"
// sign and the two live usage bars at the bottom.
Item {
    id: side

    Silk {
        anchors.fill: parent
        level: 0.7
    }
    Rectangle {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 1
        color: C.rule
    }

    Text {
        id: brand
        x: 22
        y: 20
        text: "VibeNote"
        color: C.accent
        font { family: win.serif; pixelSize: 30; bold: true; italic: true }
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#c08457"
            shadowBlur: 0.8
            shadowOpacity: 0.35 + 0.15 * Math.sin(win.t * 0.8)
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }
    }

    Text {  // shrink to the mini player (his ask, 2026-11-12)
        anchors { right: parent.right; rightMargin: 18; verticalCenter: brand.verticalCenter }
        text: "◱"
        color: smallArea.containsMouse ? C.peach : C.faded
        font.pixelSize: 20
        MouseArea {
            id: smallArea
            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: bridge.open("mini")
        }
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: brand.bottom; bottom: foot.top }
        anchors { topMargin: 16; bottomMargin: 10 }
        clip: true
        spacing: 2
        boundsBehavior: Flickable.DragAndOvershootBounds
        model: {
            var all = bridge.projectList, rows = []
            var pinned = all.filter(function (p) { return p.pinned })
            var rest = all.filter(function (p) { return !p.pinned })
            if (pinned.length) rows.push({ head: "PINNED" })
            rows = rows.concat(pinned)
            rows.push({ head: "PROJECTS" })
            return rows.concat(rest)
        }
        delegate: Loader {
            required property var modelData
            width: ListView.view.width
            sourceComponent: modelData.head ? headC : rowC
            Component {
                id: headC
                Item {
                    height: 34
                    Text {
                        x: 22
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 6
                        text: modelData.head
                        color: C.faded
                        font { family: win.serif; pixelSize: 13; bold: true; letterSpacing: 1.2 }
                    }
                }
            }
            Component {
                id: rowC
                Item {
                    id: row
                    height: 38
                    property bool picked: modelData.current
                    property real hot: rh.hovered ? 1 : 0
                    Behavior on hot { SpringAnimation { spring: 4; damping: 0.3 } }
                    HoverHandler { id: rh }
                    Rectangle {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        radius: 8
                        color: C.picked
                        opacity: row.picked ? 0.85 : row.hot * 0.4
                        Behavior on opacity { NumberAnimation { duration: 200 } }
                    }
                    Rectangle {  // a copper thread marks the open project
                        x: 8
                        width: 3
                        radius: 1.5
                        color: C.accent
                        anchors.verticalCenter: parent.verticalCenter
                        height: row.picked ? 22 : 0
                        Behavior on height { SpringAnimation { spring: 4; damping: 0.3 } }
                    }
                    Text {
                        x: 22 + row.hot * 6
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - x - 44
                        elide: Text.ElideRight
                        text: modelData.title
                        color: C.ink
                        font { family: win.serif; pixelSize: 18; bold: row.picked }
                    }
                    Text {
                        anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                        visible: modelData.waiting > 0
                        text: modelData.waiting
                        color: C.accent
                        font { family: win.serif; pixelSize: 16; bold: true }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (m) => {
                            var at = mapToItem(root, m.x, m.y)
                            win.ripple(at.x, at.y, 0.6)
                            bridge.pick(modelData.slug)
                        }
                    }
                }
            }
        }
    }

    Column {
        id: foot
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        anchors { leftMargin: 22; rightMargin: 22; bottomMargin: 20 }
        spacing: 6
        Rectangle { width: parent.width; height: 1; color: C.rule }
        Item { width: 1; height: 6 }
        Text {
            width: parent.width
            text: bridge.sign.level === "good" ? "● Good time for Claude"
                  : bridge.sign.level === "bad" ? "● Not a great time" : "● Okay time for Claude"
            color: bridge.sign.level === "good" ? C.jade : C.accent
            font { family: win.serif; pixelSize: 18 }
        }
        Text {
            width: parent.width
            wrapMode: Text.Wrap
            text: bridge.sign.why
            color: C.faded
            font { family: win.serif; pixelSize: 14 }
        }
        Item { width: 1; height: 6 }
        LiveBars { width: parent.width }
    }
}
