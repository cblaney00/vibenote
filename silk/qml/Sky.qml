import QtQuick

// Sky (his pick, 2026-11-12): the notes as cards hanging in the night in perspective:
// waiting ones nearest, then sent and worked on, Later, and done far off (newer nearer).
// The wheel flies through them, the mouse tilts the view, a click opens the note in List.
Item {
    id: sky
    clip: true
    property var notes: bridge.everyNote.slice(0, 90)
    property real cam: 0
    property real camTo: 0
    Behavior on cam { SpringAnimation { spring: 2.2; damping: 0.4 } }
    property real most: 1
    property var hovered: null
    readonly property real tiltX: (win.smx / Math.max(win.width, 1) - 0.5)
    readonly property real tiltY: (win.smy / Math.max(win.height, 1) - 0.5)
    readonly property real cx: width / 2 - tiltX * 60
    readonly property real cy: height * 0.44 - tiltY * 40
    readonly property real spreadW: width * 0.42

    // where each kind hangs: its first card's depth, and the step between cards
    readonly property var depth: ({ waiting: 0.9, sent: 1.5, worked: 1.5, later: 2.0, review: 2.3, done: 2.5 })
    function place(list) {
        var seen = {}, out = [], far = 1
        for (var i = 0; i < list.length; i++) {
            var n = list[i], k = n.kind
            var j = seen[k] || 0
            seen[k] = j + 1
            // a steady scatter from the note's id, so a card keeps its place
            var h = 0
            for (var c = 0; c < n.id.length; c++) h = (h * 31 + n.id.charCodeAt(c)) % 100003
            var r1 = (h % 1000) / 1000, r2 = (Math.floor(h / 1000) % 100) / 100
            var z = depth[k] + j * (k === "done" ? 0.12 : 0.22)
            var spread = 0.55 + 0.45 * z
            out.push({ note: n, z: z, x: (r1 * 2.2 - 1.1) * spread, y: (r2 * 1.2 - 0.7) * spread,
                       ph: r1 * 6.28 })
            far = Math.max(far, z)
        }
        most = far
        return out
    }
    property var placed: place(notes)

    WheelHandler {
        onWheel: (e) => {
            sky.camTo = Math.max(-0.8, Math.min(sky.most - 0.6, sky.camTo + e.angleDelta.y / 120 * 0.22))
            sky.cam = sky.camTo
        }
    }

    // the floor: lines running to the vanishing point
    Repeater {
        model: 13
        delegate: Rectangle {
            required property int index
            readonly property real fx: (index - 6) / 6
            x: sky.cx
            y: sky.cy + 90
            width: 1
            height: Math.hypot(sky.width, sky.height)
            color: C.margin
            opacity: 0.25
            transformOrigin: Item.Top
            rotation: -Math.atan2(fx * sky.width * 1.6, sky.height) * 180 / Math.PI
        }
    }

    Repeater {
        model: sky.placed
        delegate: Item {
            id: hang
            required property var modelData
            required property int index
            readonly property real d: modelData.z - sky.cam
            readonly property real f: 1 / Math.max(d, 0.05)
            readonly property real bob: Math.sin(win.t * 0.5 + modelData.ph) * 6
            visible: d > 0.3 && opacity > 0.02
            z: -d
            width: 300
            height: face.height
            x: sky.cx + modelData.x * sky.spreadW * f - width / 2
            y: sky.cy + modelData.y * sky.spreadW * f * 0.8 - height / 2 + bob * f
            scale: Math.min(1.6, f * 0.95) * (sky.hovered === modelData.note ? 1.06 : 1)
            opacity: Math.min(1, (d - 0.3) * 3) * Math.max(0.3, Math.min(1, 2.2 / d))
            Rectangle {
                id: face
                width: parent.width
                height: words.height + 24
                radius: 12
                color: ({ waiting: "#163327", sent: "#12271f", worked: "#143027" })[hang.modelData.note.kind] || "#0f201a"
                border.width: sky.hovered === hang.modelData.note ? 2 : 1
                border.color: ({ waiting: C.accent, sent: C.faded, worked: C.jade, review: C.jade })[hang.modelData.note.kind] || C.rule
                Text {
                    id: words
                    x: 14; y: 12
                    width: parent.width - 28
                    text: hang.modelData.note.text
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                    color: ["waiting", "sent", "worked"].indexOf(hang.modelData.note.kind) >= 0 ? C.ink : C.faded
                    font { family: win.serif; pixelSize: 16 }
                }
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: sky.hovered = hang.modelData.note
                onExited: if (sky.hovered === hang.modelData.note) sky.hovered = null
                onClicked: win.gotoNote(hang.modelData.note.id)
            }
        }
    }

    Text {
        x: 8; y: 4
        text: sky.placed.length ? "Near: waiting · then sent · far off: done. Scroll to fly through."
                                : "No notes yet. Write one above."
        color: C.faded
        font { family: win.serif; pixelSize: 14 }
    }
    // the whole note under the mouse, at the bottom
    Rectangle {
        visible: sky.hovered !== null
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 10 }
        height: whole.height + 20
        radius: 10
        color: C.field
        border.color: C.accent
        Text {
            id: whole
            x: 14; y: 10
            width: parent.width - 28
            wrapMode: Text.Wrap
            text: sky.hovered ? sky.hovered.text + (sky.hovered.when ? "   ·   " + sky.hovered.when : "") : ""
            color: C.ink
            font { family: win.serif; pixelSize: 16 }
        }
    }
}
