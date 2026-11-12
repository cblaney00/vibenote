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

    Text {  // the motion switch: ✦ moving, ✧ still (his pick, 2026-11-12)
        anchors { right: smallBtn.left; rightMargin: 14; verticalCenter: brand.verticalCenter }
        text: bridge.motion ? "✦" : "✧"
        color: motionArea.containsMouse ? C.peach : bridge.motion ? C.accent : C.faded
        font.pixelSize: 19
        MouseArea {
            id: motionArea
            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: bridge.toggleMotion()
        }
    }
    Text {  // shrink to the mini player (his ask, 2026-11-12)
        id: smallBtn
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

    // His order, with a Pinned box on top (his ask, 2026-11-06): drag a row anywhere by its
    // grip (⠿); dropping it in the other box pins or unpins it. The flag (⚑ pinned, ⚐ not)
    // and a right-click pin too. The rows are a ListModel, so a drag only moves them.
    ListModel { id: rows }
    property bool dragging: false
    property bool stale: false
    function fill() {
        if (dragging) { stale = true; return }
        var all = bridge.projectList
        rows.clear()
        rows.append({ head: "PINNED", slug: "", title: "", waiting: 0, pinned: true, current: false })
        all.filter(function (p) { return p.pinned }).forEach(function (p) { rows.append(Object.assign({ head: "" }, p)) })
        rows.append({ head: "PROJECTS", slug: "", title: "", waiting: 0, pinned: false, current: false })
        all.filter(function (p) { return !p.pinned }).forEach(function (p) { rows.append(Object.assign({ head: "" }, p)) })
    }
    Connections {
        target: bridge
        function onProjectsChanged() { side.fill() }
    }
    Component.onCompleted: fill()
    function rowAt(y) {  // the model row under a height in the list's content
        var top = 0
        for (var i = 0; i < rows.count; i++) {
            var h = rows.get(i).head ? 34 : 38
            if (y < top + h / 2) return i
            top += h + list.spacing
        }
        return rows.count - 1
    }
    function save() {
        var order = [], pinned = [], inPinned = false
        for (var i = 0; i < rows.count; i++) {
            var r = rows.get(i)
            if (r.head) { inPinned = r.head === "PINNED"; continue }
            order.push(r.slug)
            if (inPinned) pinned.push(r.slug)
        }
        bridge.setOrder(order, pinned)
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: brand.bottom; bottom: foot.top }
        anchors { topMargin: 16; bottomMargin: 10 }
        clip: true
        spacing: 2
        interactive: !side.dragging
        boundsBehavior: Flickable.DragAndOvershootBounds
        model: rows
        moveDisplaced: Transition { NumberAnimation { properties: "y"; duration: 180; easing.type: Easing.OutCubic } }
        delegate: Item {
            id: slot
            required property int index
            required property string head
            required property string slug
            required property string title
            required property int waiting
            required property bool pinned
            required property bool current
            width: ListView.view.width
            height: head ? 34 : 38
            z: grabbed ? 5 : 0
            property bool grabbed: false
            Text {
                visible: slot.head !== ""
                x: 22
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 6
                text: slot.head
                color: C.faded
                font { family: win.serif; pixelSize: 13; bold: true; letterSpacing: 1.2 }
            }
            Text {  // an empty Pinned box says how to fill it
                visible: slot.head === "PINNED" && (slot.index + 1 >= rows.count || rows.get(slot.index + 1).head !== "")
                anchors { right: parent.right; rightMargin: 18; bottom: parent.bottom; bottomMargin: 7 }
                text: "drag one here"
                color: C.faded
                opacity: 0.6
                font { family: win.serif; pixelSize: 12; italic: true }
            }
            Item {
                id: row
                visible: slot.head === ""
                anchors.fill: parent
                property bool picked: slot.current
                property real hot: rh.hovered || slot.grabbed ? 1 : 0
                Behavior on hot { SpringAnimation { spring: 4; damping: 0.3 } }
                scale: slot.grabbed ? 1.04 : 1
                Behavior on scale { SpringAnimation { spring: 5; damping: 0.35 } }
                HoverHandler { id: rh }
                Rectangle {
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    radius: 8
                    color: slot.grabbed ? C.rule : C.picked
                    opacity: slot.grabbed ? 0.95 : row.picked ? 0.85 : row.hot * 0.4
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
                Text {  // the grip
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: "⠿"
                    color: C.faded
                    opacity: 0.3 + row.hot * 0.6
                    font.pixelSize: 15
                }
                Text {
                    x: 30 + row.hot * 4
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - x - 70
                    elide: Text.ElideRight
                    text: slot.title
                    color: C.ink
                    font { family: win.serif; pixelSize: 18; bold: row.picked }
                }
                Text {
                    anchors { right: flag.left; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    visible: slot.waiting > 0
                    text: slot.waiting
                    color: C.accent
                    font { family: win.serif; pixelSize: 16; bold: true }
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: slot.grabbed ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                    property real startY: 0
                    property bool moved: false
                    onPressed: (m) => { startY = m.y; moved = false }
                    onPositionChanged: (m) => {
                        if (!(m.buttons & Qt.LeftButton)) return
                        if (!moved && Math.abs(m.y - startY) < 6) return
                        if (!moved) { moved = true; slot.grabbed = true; side.dragging = true }
                        var y = mapToItem(list.contentItem, m.x, m.y).y
                        var to = Math.max(1, side.rowAt(y))  // never above the Pinned title
                        if (to !== slot.index) rows.move(slot.index, to, 1)
                    }
                    onReleased: (m) => {
                        if (m.button === Qt.RightButton) { bridge.togglePin(slot.slug); return }
                        if (moved) {
                            slot.grabbed = false
                            side.dragging = false
                            side.save()
                            if (side.stale) { side.stale = false; side.fill() }
                            return
                        }
                        var at = mapToItem(root, m.x, m.y)
                        win.ripple(at.x, at.y, 0.6)
                        bridge.pick(slot.slug)
                    }
                }
                Text {
                    id: flag
                    anchors { right: parent.right; rightMargin: 18; verticalCenter: parent.verticalCenter }
                    text: slot.pinned ? "⚑" : "⚐"
                    color: fa.containsMouse ? C.peach : slot.pinned ? C.accent : C.faded
                    opacity: slot.pinned ? 0.9 : 0.25 + row.hot * 0.6
                    font.pixelSize: 16
                    MouseArea {
                        id: fa
                        anchors.fill: parent
                        anchors.margins: -6
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.togglePin(slot.slug)
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
        Row {  // the usage page and its tips (his picks, 2026-11-02 and 11-04)
            spacing: 16
            Repeater {
                model: [["Claude usage ›", false], ["Tips ›", true]]
                delegate: Text {
                    required property var modelData
                    text: modelData[0]
                    color: ua.containsMouse ? C.peach : C.accent
                    font { family: win.serif; pixelSize: 15 }
                    MouseArea {
                        id: ua
                        anchors.fill: parent
                        anchors.margins: -5
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.showUsage(modelData[1])
                    }
                }
            }
        }
        Item { width: 1; height: 6 }
        LiveBars { width: parent.width }
    }
}
