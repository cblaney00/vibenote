import QtQuick
import QtQuick.Window
import QtQuick.Effects

// The mini player in Silk (his ask, 2026-11-12: "update the lando minimal version"; his pick:
// rebuild it in the Silk look). The same as the Tk one: the good-time dot, the two usage bars
// and one tip, then Notes › (the whole Silk app), Usage › and Tips ›. Under a strip of the
// living city, on touchable silk. "Open small like this" is the setting every VibeNote has.
Window {
    id: win
    width: 370
    height: col.height + 150
    minimumWidth: 370
    maximumWidth: 370
    visible: true
    title: "VibeNote"
    color: C.sidebar

    property real t: 0
    property point mouse: Qt.point(width * 0.5, height * 0.4)
    property real smx: width * 0.5
    property real smy: height * 0.4
    property var ripples: [Qt.vector4d(0, 0, -10, 0), Qt.vector4d(0, 0, -10, 0),
                           Qt.vector4d(0, 0, -10, 0), Qt.vector4d(0, 0, -10, 0)]
    property int nextRipple: 0
    readonly property bool awake: visibility !== Window.Minimized
                                  && visibility !== Window.Hidden
                                  && (active || hover.hovered)
    readonly property string serif: "Georgia"

    function ripple(x, y, strength) {
        var r = ripples.slice()
        r[nextRipple] = Qt.vector4d(x, y, t, strength === undefined ? 1.0 : strength)
        ripples = r
        nextRipple = (nextRipple + 1) % 4
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

    Shortcut { sequence: "Escape"; onActivated: win.close() }

    Item {
        id: root
        anchors.fill: parent
        HoverHandler { id: hover; onPointChanged: win.mouse = point.position }

        Silk { anchors.fill: parent; level: 0.8 }
        MouseArea {
            anchors.fill: parent
            onPressed: (m) => win.ripple(m.x, m.y, 1.0)
        }

        Horizon {
            id: city
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 112
        }
        Text {
            x: 22
            y: 26
            text: "VibeNote"
            color: C.accent
            font { family: win.serif; pixelSize: 26; bold: true; italic: true }
            style: Text.Raised
            styleColor: "#020504"
        }
        Text {  // the whole app
            anchors { right: parent.right; rightMargin: 18; top: parent.top; topMargin: 30 }
            text: "◳"
            color: bigArea.containsMouse ? C.peach : C.faded
            font.pixelSize: 20
            MouseArea {
                id: bigArea
                anchors.fill: parent
                anchors.margins: -6
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: bridge.open("notes")
            }
        }

        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: city.bottom }
            anchors { leftMargin: 22; rightMargin: 22; topMargin: 4 }
            spacing: 10

            // the good-time sign, its dot breathing slowly
            Row {
                spacing: 10
                Rectangle {
                    id: dot
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12; height: 12; radius: 6
                    color: bridge.sign.level === "good" ? C.jade : C.accent
                    layer.enabled: true
                    layer.effect: MultiEffect {
                        shadowEnabled: true
                        shadowColor: dot.color
                        shadowBlur: 1.0
                        shadowOpacity: 0.5 + 0.4 * Math.sin(win.t * 1.4)
                        shadowHorizontalOffset: 0
                        shadowVerticalOffset: 0
                    }
                }
                Text {
                    text: bridge.sign.level === "good" ? "Good time for Claude" : "Busy hours for Claude"
                    color: dot.color
                    font { family: win.serif; pixelSize: 19 }
                }
            }

            LiveBars { width: parent.width }

            // the tip, on a small card of silk that lifts under the mouse
            Item {
                id: tipCard
                visible: bridge.tip !== ""
                width: parent.width
                height: tipText.height + 30
                property real lift: tipHover.hovered ? 1 : 0
                Behavior on lift { SpringAnimation { spring: 3.2; damping: 0.26; epsilon: 0.004 } }
                RectangularShadow {
                    anchors.fill: tipFace
                    offset.y: 3 + tipCard.lift * 8
                    blur: 10 + tipCard.lift * 20
                    radius: 11
                    color: Qt.rgba(0, 0, 0, 0.5)
                }
                Item {
                    id: tipFace
                    width: parent.width
                    height: parent.height
                    y: -tipCard.lift * 4
                    ShaderEffect {
                        anchors.fill: parent
                        property real time: win.t
                        property real lift: tipCard.lift
                        property size size: Qt.size(width, height)
                        property point mouse: tipHover.hovered ? tipHover.point.position : Qt.point(-400, -400)
                        property color tint: "#14301f"
                        property color edge: C.accent
                        fragmentShader: shaders + "/card.frag.qsb"
                    }
                    HoverHandler { id: tipHover }
                    Text {
                        id: tipText
                        x: 14; y: 15
                        width: parent.width - 28
                        wrapMode: Text.Wrap
                        text: "Tip: " + bridge.tip
                        color: C.ink
                        font { family: win.serif; pixelSize: 15 }
                        lineHeight: 1.1
                    }
                }
            }

            Row {
                spacing: 8
                topPadding: 4
                Repeater {
                    model: [["Notes ›", "notes"], ["Usage ›", "usage"], ["Tips ›", "tips"]]
                    delegate: Item {
                        required property var modelData
                        width: linkText.implicitWidth + 22
                        height: 32
                        property real hot: linkArea.containsMouse ? 1 : 0
                        Behavior on hot { NumberAnimation { duration: 160 } }
                        scale: linkArea.pressed ? 0.93 : 1
                        Behavior on scale { SpringAnimation { spring: 6; damping: 0.3 } }
                        Rectangle {
                            anchors.fill: parent
                            radius: 8
                            color: Qt.tint(C.field, Qt.rgba(0.75, 0.52, 0.34, parent.hot * 0.12))
                            border.color: parent.hot ? C.accent : C.rule
                            border.width: 1
                        }
                        Text {
                            id: linkText
                            anchors.centerIn: parent
                            text: modelData[0]
                            color: C.accent
                            font { family: win.serif; pixelSize: 15 }
                        }
                        MouseArea {
                            id: linkArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: bridge.open(modelData[1])
                        }
                    }
                }
            }

            // the setting every VibeNote has: open as this mini player each time
            Item {
                width: smallRow.width
                height: 26
            Row {
                id: smallRow
                spacing: 10
                anchors.verticalCenter: parent.verticalCenter
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 16; height: 16; radius: 8
                    color: bridge.startSmall ? C.accent : "transparent"
                    border.color: bridge.startSmall ? C.peach : C.faded
                    border.width: 1.5
                    Behavior on color { ColorAnimation { duration: 180 } }
                    scale: smallArea.pressed ? 0.75 : 1
                    Behavior on scale { SpringAnimation { spring: 5; damping: 0.3 } }
                }
                Text {
                    text: "Open small like this"
                    color: bridge.startSmall ? C.ink : C.faded
                    font { family: win.serif; pixelSize: 15 }
                }
            }
                MouseArea {
                    id: smallArea
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bridge.toggleSmall()
                }
            }
        }
    }
}
