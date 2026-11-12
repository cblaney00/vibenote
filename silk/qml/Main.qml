import QtQuick
import QtQuick.Window

// VibeNote on the graphics card (his ask, 2026-11-12: "textured and tangible", "more lively
// and interactive"). Everything that moves is drawn by the graphics card each frame; time
// stops while the window is minimised, or not in use with the mouse elsewhere.
Window {
    id: win
    width: 1120
    height: 780
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    title: "VibeNote"
    color: C.paper

    property real t: 0
    property point mouse: Qt.point(width * 0.6, height * 0.3)
    // the light and the city follow the mouse smoothly, never jumping
    property real smx: width * 0.6
    property real smy: height * 0.3
    property var ripples: [Qt.vector4d(0, 0, -10, 0), Qt.vector4d(0, 0, -10, 0),
                           Qt.vector4d(0, 0, -10, 0), Qt.vector4d(0, 0, -10, 0)]
    property int nextRipple: 0
    readonly property bool awake: visibility !== Window.Minimized
                                  && visibility !== Window.Hidden
                                  && (active || hover.hovered)
    readonly property string serif: "Georgia"

    // a ripple through the silk where he clicked
    function ripple(x, y, strength) {
        var r = ripples.slice()
        r[nextRipple] = Qt.vector4d(x, y, t, strength === undefined ? 1.0 : strength)
        ripples = r
        nextRipple = (nextRipple + 1) % 4
    }

    function say(text) {
        status.text = text
        status.opacity = 1
        statusFade.restart()
    }

    Connections {
        target: bridge
        function onSaid(text) { win.say(text) }
    }

    FrameAnimation {
        running: win.awake
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            win.t += dt
            var k = Math.min(1, dt * 7)
            win.smx += (win.mouse.x - win.smx) * k
            win.smy += (win.mouse.y - win.smy) * k
        }
    }

    Item {
        id: root
        anchors.fill: parent

        HoverHandler {
            id: hover
            onPointChanged: win.mouse = point.position
        }

        Silk {
            anchors.fill: parent
        }
        // clicking the bare silk sends a ripple through it
        MouseArea {
            anchors.fill: parent
            onPressed: (m) => win.ripple(m.x, m.y, 1.0)
        }

        Sidebar {
            id: side
            width: Math.max(220, Math.min(310, win.width * 0.27))
            anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
        }

        Item {
            id: page
            anchors { left: side.right; right: parent.right; top: parent.top; bottom: parent.bottom }
            readonly property real pad: width > 720 ? 48 : 24

            Horizon {
                id: horizon
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: 236
                scroll: notes.contentY
            }

            Text {
                id: title
                x: page.pad
                y: 56
                width: parent.width - page.pad * 2 - tabsSpace
                readonly property real tabsSpace: 0
                text: bridge.page.title
                color: C.ink
                elide: Text.ElideRight
                font { family: win.serif; pixelSize: 38; bold: true }
                style: Text.Raised
                styleColor: "#020504"
                // the title eases in when the project changes
                onTextChanged: { titleIn.restart() }
                NumberAnimation on opacity { id: titleIn; from: 0.2; to: 1; duration: 500; easing.type: Easing.OutCubic }
            }

            Row {
                x: page.pad
                y: horizon.height - 40
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: bridge.page.counts
                    color: C.faded
                    font { family: win.serif; pixelSize: 16 }
                }
            }

            // the margin: a copper thread with a glint running down it now and then
            Rectangle {
                id: thread
                x: page.pad - 22
                y: horizon.height - 8
                width: 2
                height: parent.height - y
                color: C.margin
                clip: true
                Rectangle {
                    width: 2
                    height: 140
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: C.peach }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                    opacity: 0.7
                    SequentialAnimation on y {
                        running: win.awake
                        loops: Animation.Infinite
                        NumberAnimation { from: -140; to: thread.height; duration: 4200; easing.type: Easing.InOutSine }
                        PauseAnimation { duration: 5000 }
                    }
                }
            }

            NoteEntry {
                id: entry
                anchors { left: parent.left; right: parent.right; top: horizon.bottom }
                anchors { leftMargin: page.pad; rightMargin: page.pad; topMargin: 6 }
            }

            ListView {
                id: notes
                anchors { left: parent.left; right: parent.right; top: entry.bottom; bottom: bar.top }
                anchors { leftMargin: page.pad - 6; rightMargin: page.pad - 6; topMargin: 14; bottomMargin: 8 }
                clip: true
                spacing: 6
                cacheBuffer: 600
                maximumFlickVelocity: 4000
                flickDeceleration: 2200
                boundsBehavior: Flickable.DragAndOvershootBounds
                model: []
                property string shownTitle: ""
                property bool fresh: false
                Timer { id: freshEnd; interval: 700; onTriggered: notes.fresh = false }
                delegate: Loader {
                    id: slot
                    width: ListView.view.width
                    // the drift up into place moves only the picture, never the layout
                    property real rise: 0
                    transform: Translate { y: rise }
                    // cards drift up into place when a project opens, one after another
                    SequentialAnimation {
                        id: driftIn
                        PropertyAction { target: slot; property: "opacity"; value: 0 }
                        PauseAnimation { duration: Math.min(slot.index, 14) * 30 }
                        ParallelAnimation {
                            NumberAnimation { target: slot; property: "opacity"; to: 1; duration: 420; easing.type: Easing.OutCubic }
                            NumberAnimation { target: slot; property: "rise"; from: 30; to: 0; duration: 650; easing.type: Easing.OutBack }
                        }
                    }
                    Component.onCompleted: if (ListView.view.fresh) driftIn.start()
                    required property var modelData
                    required property int index
                    sourceComponent: modelData.type === "head" ? headRow
                                     : modelData.note.kind === "done" ? doneRow : noteCard
                    Component { id: headRow; SectionHead { info: modelData } }
                    Component { id: doneRow; DoneRow { note: modelData.note } }
                    Component { id: noteCard; NoteCard { note: modelData.note } }
                }
                function rebuild() {
                    var p = bridge.page
                    var rows = []
                    for (var i = 0; i < p.sections.length; i++) {
                        var s = p.sections[i]
                        rows.push({ type: "head", title: s.title, count: s.count, key: s.key })
                        for (var j = 0; j < s.notes.length; j++)
                            rows.push({ type: "note", note: s.notes[j] })
                    }
                    var same = shownTitle === p.title
                    var keep = contentY
                    shownTitle = p.title
                    fresh = !same
                    freshEnd.restart()
                    model = rows
                    if (same) Qt.callLater(function() { notes.contentY = keep })
                }
                Component.onCompleted: rebuild()
                Connections {
                    target: bridge
                    function onPageChanged() { notes.rebuild() }
                }

                // a thin copper scroll thread
                Rectangle {
                    visible: notes.contentHeight > notes.height
                    x: notes.width - 3
                    width: 3
                    radius: 1.5
                    color: C.accent
                    opacity: notes.moving ? 0.6 : 0.18
                    Behavior on opacity { NumberAnimation { duration: 300 } }
                    height: Math.max(30, notes.height * notes.height / Math.max(notes.contentHeight, 1))
                    y: (notes.height - height) * Math.min(1, Math.max(0, notes.contentY / Math.max(1, notes.contentHeight - notes.height)))
                }
            }

            Item {
                id: bar
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                anchors { leftMargin: page.pad; rightMargin: page.pad; bottomMargin: 16 }
                height: 46
                Text {
                    id: status
                    anchors { left: parent.left; right: sendBtn.left; verticalCenter: parent.verticalCenter; rightMargin: 12 }
                    color: C.faded
                    elide: Text.ElideRight
                    font { family: win.serif; pixelSize: 16 }
                    Behavior on opacity { NumberAnimation { duration: 900 } }
                    Timer { id: statusFade; interval: 6000; onTriggered: status.opacity = 0 }
                }
                SilkButton {
                    id: sendBtn
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    text: bridge.sendCount ? "Send " + bridge.sendCount + " ticked" : "Send"
                    enabled: bridge.sendCount > 0
                    main: true
                    onClicked: bridge.send()
                }
            }
        }
    }
}
