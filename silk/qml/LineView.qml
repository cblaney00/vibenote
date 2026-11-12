import QtQuick

// Timeline (a diary, newest day first) and Compact (one cut-to-fit line per note under
// status headings). Clicking a line opens the note in List.
ListView {
    id: lines
    property bool diary: true
    clip: true
    spacing: 0
    boundsBehavior: Flickable.DragAndOvershootBounds
    readonly property var marks: ({ waiting: "○", later: "◦", sent: "→", worked: "◐", review: "✓", done: "✓" })
    readonly property var words: ({ waiting: "waiting", later: "later", sent: "sent", worked: "worked on",
                                    review: "with Lando", done: "done" })
    readonly property var heads: ({ waiting: "WAITING", later: "LATER", sent: "SENT", worked: "WORKED ON",
                                    review: "WITH LANDO", done: "DONE" })
    model: {
        var all = bridge.everyNote.slice(), rows = [], last = null
        if (diary) all.sort(function (a, b) { return a.day < b.day ? 1 : a.day > b.day ? -1 : 0 })
        var count = {}
        all.forEach(function (n) { count[n.kind] = (count[n.kind] || 0) + 1 })
        for (var i = 0; i < all.length; i++) {
            var n = all[i], key = diary ? n.dayTitle : n.kind
            if (key !== last) rows.push({ head: diary ? key : heads[n.kind] + " · " + count[n.kind] })
            last = key
            rows.push({ note: n })
        }
        return rows
    }
    footer: Text {
        visible: lines.count === 0
        text: "Nothing yet. Write a note above."
        color: C.faded
        font { family: win.serif; pixelSize: 14 }
    }
    delegate: Loader {
        required property var modelData
        width: ListView.view.width
        sourceComponent: modelData.head !== undefined ? headC : lineC
        Component {
            id: headC
            Text {
                topPadding: 18
                bottomPadding: 6
                leftPadding: 6
                text: modelData.head
                color: C.accent
                font { family: win.serif; pixelSize: lines.diary ? 17 : 14; bold: !lines.diary; letterSpacing: lines.diary ? 0.3 : 1.1 }
            }
        }
        Component {
            id: lineC
            Item {
                id: line
                readonly property var n: modelData.note
                readonly property bool open: ["waiting", "sent", "worked"].indexOf(n.kind) >= 0
                height: lines.diary ? Math.max(28, body.height + 8) : 26
                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: C.picked
                    opacity: lh.hovered ? 0.5 : 0
                    Behavior on opacity { NumberAnimation { duration: 140 } }
                }
                HoverHandler { id: lh }
                Text {
                    id: mark
                    x: 10; y: 4
                    width: 22
                    text: lines.marks[line.n.kind]
                    color: line.n.kind === "worked" || line.n.kind === "review" ? C.jade
                           : line.n.kind === "waiting" || line.n.kind === "done" ? C.accent : C.faded
                    font { family: win.serif; pixelSize: 16 }
                }
                Text {
                    id: size
                    visible: !lines.diary
                    x: 36; y: 5
                    width: 56
                    text: line.n.tokens
                    color: C.faded
                    font { family: win.serif; pixelSize: 13 }
                }
                Text {
                    id: body
                    x: lines.diary ? 38 : 96
                    y: 4
                    width: parent.width - x - (lines.diary ? tag.width + 20 : 10)
                    text: line.n.text
                    wrapMode: lines.diary ? Text.Wrap : Text.NoWrap
                    elide: lines.diary ? Text.ElideNone : Text.ElideRight
                    color: lh.hovered ? C.peach : line.open ? C.ink : C.faded
                    font { family: win.serif; pixelSize: 16 }
                }
                Text {
                    id: tag
                    visible: lines.diary
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    y: 6
                    text: lines.words[line.n.kind]
                    color: C.faded
                    font { family: win.serif; pixelSize: 13 }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (m) => {
                        if (m.button === Qt.RightButton && line.open) {
                            var at = mapToItem(root, m.x, m.y)
                            win.menuFor(line.n.id, at.x, at.y)
                        } else win.gotoNote(line.n.id)
                    }
                }
            }
        }
    }
}
