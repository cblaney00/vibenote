import QtQuick
import QtQuick.Effects

// Board (his pick, 2026-11-12): four columns of silk cards. Pick a card up and toss it into
// another column: Waiting → Sent sends it, Worked on → Done ticks it finished, an open one
// → Waiting puts it in Later (a Later one comes back). Anything else springs home.
Item {
    id: board
    readonly property var cols: [
        { key: "waiting", title: "Waiting", kinds: ["waiting", "later"] },
        { key: "sent", title: "Sent", kinds: ["sent"] },
        { key: "worked", title: "Worked on", kinds: ["worked", "review"] },
        { key: "done", title: "Done", kinds: ["done"] }]
    readonly property real gap: 14
    readonly property real colW: (width - gap * 3) / 4
    property var notes: bridge.everyNote
    property string lifted: ""   // the card being carried
    property int hoverCol: -1

    function inCol(c) {
        var out = []
        for (var i = 0; i < notes.length; i++)
            if (cols[c].kinds.indexOf(notes[i].kind) >= 0) out.push(notes[i])
        return out
    }
    function colAt(x) { return Math.max(0, Math.min(3, Math.floor(x / (colW + gap)))) }

    Repeater {
        model: 4
        delegate: Item {
            id: column
            required property int index
            readonly property var items: board.inCol(index)
            x: index * (board.colW + board.gap)
            width: board.colW
            height: board.height
            Rectangle {  // the column lights up while a card is carried over it
                anchors.fill: parent
                radius: 14
                color: C.picked
                opacity: board.lifted !== "" && board.hoverCol === column.index ? 0.35 : 0.0
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }
            Text {
                id: head
                x: 8
                y: 4
                text: board.cols[column.index].title + " · " + column.items.length
                color: C.accent
                font { family: win.serif; pixelSize: 16; letterSpacing: 0.4 }
            }
            ListView {
                id: lv
                readonly property Item boardItem: board
                anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 8 }
                clip: true
                spacing: 8
                interactive: board.lifted === ""
                model: column.items.slice(0, 30)
                footer: Text {
                    width: lv.width
                    visible: column.items.length > 30 || column.items.length === 0
                    text: column.items.length === 0 ? "Nothing here" : "… more in List"
                    color: C.faded
                    topPadding: 6
                    leftPadding: 8
                    font { family: win.serif; pixelSize: 14 }
                }
                delegate: BoardCard {
                    required property var modelData
                    note: modelData
                    width: lv.width
                    board: lv.boardItem
                }
            }
        }
    }

    // the carried card, above everything, following the mouse on a spring
    Item {
        id: ghost
        z: 10
        visible: board.lifted !== ""
        width: board.colW
        height: ghostCard.height
        property var note: ({ id: "", text: "", kind: "waiting", tokens: "", size: 0, when: "" })
        property real tx: 0
        property real ty: 0
        x: tx
        y: ty
        Behavior on x { SpringAnimation { spring: 5; damping: 0.32 } }
        Behavior on y { SpringAnimation { spring: 5; damping: 0.32 } }
        rotation: Math.max(-6, Math.min(6, (tx - x) * 0.05))
        RectangularShadow {
            anchors.fill: ghostCard
            offset.y: 18
            blur: 36
            radius: 11
            color: Qt.rgba(0, 0, 0, 0.65)
        }
        BoardCard {
            id: ghostCard
            note: ghost.note
            width: ghost.width
            board: null
            carried: true
        }
    }

    function pickUp(note, item, mx, my) {
        var at = item.mapToItem(board, 0, 0)
        ghost.note = note
        ghost.x = at.x; ghost.y = at.y
        ghost.tx = at.x; ghost.ty = at.y
        grab.dx = mx; grab.dy = my
        lifted = note.id
    }
    QtObject { id: grab; property real dx: 0; property real dy: 0 }
    function carry(item, mx, my) {
        var at = item.mapToItem(board, mx, my)
        ghost.tx = at.x - grab.dx
        ghost.ty = at.y - grab.dy
        hoverCol = colAt(at.x)
    }
    function drop(item, mx, my, vx) {
        var at = item.mapToItem(board, mx, my)
        // a toss carries on a little in the direction it was thrown
        var col = colAt(at.x + vx * 0.18)
        var id = lifted
        var home = cols.findIndex(function (c) { return c.kinds.indexOf(ghost.note.kind) >= 0 })
        ghost.tx = col * (colW + gap)
        var at2 = mapToItem(root, at.x, at.y)
        win.ripple(at2.x, at2.y, 0.9)
        landing.col = col
        landing.home = home
        landing.id = id
        landing.start()
    }
    Timer {
        id: landing
        interval: 260
        property int col: 0
        property int home: 0
        property string id: ""
        onTriggered: {
            board.lifted = ""
            board.hoverCol = -1
            if (col !== home) bridge.boardDrop(id, board.cols[col].key)
        }
    }
}
