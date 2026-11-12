import QtQuick
import QtQuick.Effects

// A note as a card of silk with weight (his pick, 2026-11-12: "notes with weight"): it lifts
// towards him with a deepening shadow under the mouse, tilts a little after the mouse, and
// settles back on a spring. A waiting note edits on click; the tick sends it.
Item {
    id: card
    property var note
    readonly property bool waiting: note.kind === "waiting"
    property bool editing: false
    property bool sendOn: note.send
    property bool workOn: note.work
    readonly property bool workable: !bridge.isLando && (note.kind === "waiting" || note.kind === "sent"
                                                         || note.kind === "worked")
    property real lift: (hh.hovered || editing || win.flashId === note.id) ? 1 : 0
    Behavior on lift { SpringAnimation { spring: 3.2; damping: 0.26; epsilon: 0.004 } }
    property real press: 0
    Behavior on press { SpringAnimation { spring: 6; damping: 0.4 } }

    height: body.height + 14
    width: ListView.view ? ListView.view.width : 600

    readonly property color tint: ({ waiting: "#163327", sent: "#12271f", worked: "#143027",
                                     later: "#0f201a", review: "#10221b" })[note.kind] || C.card
    readonly property color edge: ({ waiting: C.accent, sent: C.faded, worked: C.jade,
                                     later: C.rule, review: C.jade })[note.kind] || C.rule

    RectangularShadow {
        anchors.fill: body
        anchors.margins: 2
        offset.y: 3 + card.lift * 10 - card.press * 3
        blur: 10 + card.lift * 26
        spread: -2
        radius: 11
        color: Qt.rgba(0, 0, 0, 0.5 + card.lift * 0.2)
    }

    Item {
        id: body
        x: 6
        y: 6 - card.lift * 5 + card.press * 3
        width: parent.width - 12
        height: content.height + 26
        property point local: hh.point.position
        transform: [
            Rotation {
                origin.x: body.width / 2; origin.y: body.height / 2
                axis { x: 0; y: 1; z: 0 }
                angle: card.lift * (body.local.x / Math.max(body.width, 1) - 0.5) * 4
            },
            Rotation {
                origin.x: body.width / 2; origin.y: body.height / 2
                axis { x: 1; y: 0; z: 0 }
                angle: -card.lift * (body.local.y / Math.max(body.height, 1) - 0.5) * 7
            },
            Scale {
                origin.x: body.width / 2; origin.y: body.height / 2
                xScale: 1 + card.lift * 0.012 - card.press * 0.01
                yScale: xScale
            }
        ]

        ShaderEffect {
            anchors.fill: parent
            property real time: win.t
            property real lift: card.lift
            property size size: Qt.size(width, height)
            property point mouse: hh.hovered ? body.local : Qt.point(-400, -400)
            property color tint: card.tint
            property color edge: card.edge
            fragmentShader: shaders + "/card.frag.qsb"
        }

        HoverHandler { id: hh }
        // right-click: Later / Now / Move to another project
        TapHandler {
            acceptedButtons: Qt.RightButton
            enabled: card.note.kind !== "done" && card.note.kind !== "review"
            onTapped: (ev) => {
                var at = body.mapToItem(root, ev.position.x, ev.position.y)
                win.menuFor(card.note.id, at.x, at.y)
            }
        }

        Item {
            id: content
            x: 14
            y: 13
            width: parent.width - 28
            height: Math.max(textCol.height, 26)

            // the Send tick: a copper bead, or the note's mark once it has gone
            Item {
                id: mark
                width: 30
                height: 26
                Rectangle {
                    visible: card.waiting
                    anchors.centerIn: parent
                    width: 18; height: 18; radius: 9
                    color: card.sendOn ? C.accent : "transparent"
                    border.color: card.sendOn ? C.peach : C.faded
                    border.width: 1.5
                    scale: tickArea.pressed ? 0.75 : 1
                    Behavior on scale { SpringAnimation { spring: 5; damping: 0.3 } }
                    Behavior on color { ColorAnimation { duration: 180 } }
                    Text {
                        anchors.centerIn: parent
                        visible: card.sendOn
                        text: "✓"
                        color: C.paper
                        font { pixelSize: 12; bold: true }
                    }
                }
                Text {
                    visible: !card.waiting
                    anchors.centerIn: parent
                    text: ({ sent: "→", worked: "◐", later: "◦", review: "✓" })[card.note.kind] || ""
                    color: card.note.kind === "worked" || card.note.kind === "review" ? C.jade : C.faded
                    font { family: win.serif; pixelSize: 18 }
                }
                MouseArea {
                    id: tickArea
                    anchors.fill: parent
                    enabled: card.waiting
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        card.sendOn = !card.sendOn
                        bridge.tick(card.note.id, "send")
                    }
                }
            }

            // the Work tick: a jade bead (the green Work column of the Tk app)
            Item {
                id: workMark
                x: mark.width
                width: card.workable ? 30 : 0
                height: 26
                visible: card.workable
                Rectangle {
                    anchors.centerIn: parent
                    width: 18; height: 18; radius: 5
                    color: card.workOn ? C.jade : "transparent"
                    border.color: card.workOn ? C.jade : C.faded
                    border.width: 1.5
                    scale: workArea.pressed ? 0.75 : 1
                    Behavior on scale { SpringAnimation { spring: 5; damping: 0.3 } }
                    Behavior on color { ColorAnimation { duration: 180 } }
                    Text {
                        anchors.centerIn: parent
                        visible: card.workOn
                        text: "✓"
                        color: C.paper
                        font { pixelSize: 12; bold: true }
                    }
                }
                MouseArea {
                    id: workArea
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        card.workOn = !card.workOn
                        bridge.tick(card.note.id, "work")
                    }
                }
            }

            Column {
                id: textCol
                x: mark.width + workMark.width + 8
                width: parent.width - x - side.width - 10
                spacing: 4
                Text {
                    id: label
                    visible: !card.editing
                    width: parent.width
                    text: card.note.text
                    wrapMode: Text.Wrap
                    color: card.note.kind === "later" || card.note.kind === "review" ? C.faded : C.ink
                    font { family: win.serif; pixelSize: card.waiting ? 19 : 17 }
                    lineHeight: 1.12
                }
                TextEdit {
                    id: editor
                    visible: card.editing
                    width: parent.width
                    wrapMode: TextEdit.Wrap
                    color: C.ink
                    selectionColor: C.picked
                    selectedTextColor: C.ink
                    font: label.font
                    Keys.onPressed: (e) => {
                        if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !(e.modifiers & Qt.ShiftModifier)) {
                            card.finishEdit(true); e.accepted = true
                        } else if (e.key === Qt.Key_Escape) {
                            card.finishEdit(false); e.accepted = true
                        }
                    }
                    onActiveFocusChanged: if (!activeFocus && card.editing) card.finishEdit(true)
                }
                // the date unfolds under the note while the mouse is on it
                Item {
                    width: parent.width
                    height: whenText.implicitHeight * card.lift
                    clip: true
                    visible: card.note.when !== ""
                    Text {
                        id: whenText
                        width: parent.width
                        elide: Text.ElideRight
                        text: (card.note.kind === "waiting" ? "written " : "") + card.note.when
                              + (card.note.snap !== "" ? "   ·   " + card.note.snap : "")
                        opacity: card.lift
                        color: card.note.kind === "worked" ? C.jade : C.faded
                        font { family: win.serif; pixelSize: 14 }
                    }
                }
            }
            MouseArea {
                anchors.fill: textCol
                enabled: card.waiting && !card.editing
                cursorShape: card.waiting ? Qt.IBeamCursor : Qt.ArrowCursor
                onPressed: (m) => { card.press = 1 }
                onReleased: card.press = 0
                onCanceled: card.press = 0
                onClicked: (m) => {
                    var at = mapToItem(root, m.x, m.y)
                    win.ripple(at.x, at.y, 0.5)
                    card.startEdit()
                }
            }

            // the words that show under the mouse
            Row {
                id: side
                anchors.right: parent.right
                y: 2
                spacing: 12
                Repeater {
                    model: ({ waiting: [["Later", "later"], ["Move", "move"], ["×", "delete"]],
                              sent: [["Later", "later"]],
                              worked: [["Finished", "finish"], ["Later", "later"]],
                              later: [["Now", "now"], ["Move", "move"], ["×", "delete"]],
                              review: [] })[card.note.kind] || []
                    delegate: Text {
                        required property var modelData
                        text: modelData[0]
                        opacity: card.lift
                        visible: opacity > 0.02
                        color: act.containsMouse ? C.peach : C.faded
                        font { family: win.serif; pixelSize: text === "×" ? 20 : 15 }
                        MouseArea {
                            id: act
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (m) => {
                                var a = modelData[1], id = card.note.id
                                if (a === "move") {
                                    var at = mapToItem(root, m.x, m.y)
                                    win.menuFor(id, at.x, at.y)
                                }
                                if (a === "later") bridge.later(id)
                                else if (a === "delete") bridge.deleteNote(id)
                                else if (a === "finish") bridge.finish(id)
                                else if (a === "now") bridge.now(id)
                            }
                        }
                    }
                }
                Text {
                    visible: card.note.kind === "review"
                    text: "with Lando"
                    color: C.jade
                    font { family: win.serif; pixelSize: 15 }
                }
                Text {
                    visible: card.note.tokens !== ""
                    text: card.note.tokens
                    color: card.note.size >= 6 ? C.accent : card.note.size >= 3 ? C.faded : C.jade
                    font { family: win.serif; pixelSize: 15 }
                }
            }
        }
    }

    function startEdit() {
        editor.text = note.text
        editing = true
        bridge.setEditing(true)
        editor.forceActiveFocus()
        editor.cursorPosition = editor.length
    }
    function finishEdit(save) {
        if (!editing) return
        editing = false
        bridge.setEditing(false)
        if (save && editor.text !== note.text) bridge.editNote(note.id, editor.text)
    }
}
