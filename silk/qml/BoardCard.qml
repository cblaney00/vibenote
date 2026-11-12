import QtQuick
import QtQuick.Effects

// A card on the Board: silk with weight. Press and move to pick it up; a click on a waiting
// card edits it in List, others open there.
Item {
    id: card
    property var note
    property var board
    property bool carried: false
    height: body.height + 8
    readonly property bool away: board !== null && board.lifted === note.id
    opacity: away ? 0.25 : 1
    Behavior on opacity { NumberAnimation { duration: 160 } }
    property real lift: (hh.hovered || carried) ? 1 : 0
    Behavior on lift { SpringAnimation { spring: 3.2; damping: 0.26; epsilon: 0.004 } }
    readonly property color tint: ({ waiting: "#163327", sent: "#12271f", worked: "#143027",
                                     later: "#0f201a", review: "#10221b", done: "#0e1d17" })[note.kind] || C.card
    readonly property color edge: ({ waiting: C.accent, sent: C.faded, worked: C.jade,
                                     later: C.rule, review: C.jade, done: C.rule })[note.kind] || C.rule
    RectangularShadow {
        visible: !card.carried
        anchors.fill: body
        offset.y: 2 + card.lift * 7
        blur: 8 + card.lift * 16
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.45)
    }
    Item {
        id: body
        y: 4 - card.lift * 3
        width: parent.width
        height: words.height + (foot.visible ? foot.height + 6 : 0) + 22
        ShaderEffect {
            anchors.fill: parent
            property real time: win.t
            property real lift: card.lift
            property size size: Qt.size(width, height)
            property point mouse: hh.hovered ? hh.point.position : Qt.point(-400, -400)
            property color tint: card.tint
            property color edge: card.edge
            fragmentShader: shaders + "/card.frag.qsb"
        }
        HoverHandler { id: hh }
        Text {
            id: words
            x: 12; y: 11
            width: parent.width - 24
            text: card.note.text
            wrapMode: Text.Wrap
            maximumLineCount: 7
            elide: Text.ElideRight
            color: card.note.kind === "done" || card.note.kind === "later" || card.note.kind === "review" ? C.faded : C.ink
            font { family: win.serif; pixelSize: 15 }
        }
        Row {
            id: foot
            x: 12
            anchors.top: words.bottom
            anchors.topMargin: 6
            spacing: 10
            visible: card.note.tokens !== "" || card.note.kind === "later" || card.note.kind === "review"
            Text {
                visible: card.note.kind === "later" || card.note.kind === "review"
                text: card.note.kind === "later" ? "later" : "with Lando"
                color: card.note.kind === "review" ? C.jade : C.faded
                font { family: win.serif; pixelSize: 13; italic: true }
            }
            Text {
                visible: card.note.tokens !== ""
                text: card.note.tokens
                color: card.note.size >= 6 ? C.accent : card.note.size >= 3 ? C.faded : C.jade
                font { family: win.serif; pixelSize: 13 }
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: card.board !== null
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: card.away ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point start
            property bool moving: false
            property real lastX: 0
            property real vx: 0
            property double lastT: 0
            onPressed: (m) => {
                if (m.button === Qt.RightButton) {
                    var at = mapToItem(root, m.x, m.y)
                    win.menuFor(card.note.id, at.x, at.y)
                    return
                }
                start = Qt.point(m.x, m.y); moving = false; lastX = m.x; vx = 0; lastT = Date.now()
            }
            onPositionChanged: (m) => {
                if (!(m.buttons & Qt.LeftButton)) return
                if (!moving && Math.abs(m.x - start.x) + Math.abs(m.y - start.y) > 8) {
                    moving = true
                    card.board.pickUp(card.note, card, start.x, start.y)
                }
                if (moving) {
                    var now = Date.now(), dt = Math.max(1, now - lastT)
                    vx = vx * 0.6 + (m.x - lastX) / dt * 1000 * 0.4
                    lastX = m.x; lastT = now
                    card.board.carry(card, m.x, m.y)
                }
            }
            onReleased: (m) => {
                if (m.button !== Qt.LeftButton) return
                if (moving) card.board.drop(card, m.x, m.y, vx)
                else win.gotoNote(card.note.id)
                moving = false
            }
        }
    }
}
