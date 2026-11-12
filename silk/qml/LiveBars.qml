import QtQuick

// The two bars Claude's /usage shows (5 hours, this week), filling smoothly, with a slow
// shimmer along the filled part.
Column {
    id: bars
    spacing: 6
    Text {
        text: bridge.live.bars.length ? bridge.live.name + " now" : "Live usage shows after Claude's next reply."
        color: C.faded
        width: parent.width
        wrapMode: Text.Wrap
        font { family: win.serif; pixelSize: 13; bold: true }
    }
    Repeater {
        model: bridge.live.bars
        delegate: Column {
            required property var modelData
            width: bars.width
            spacing: 4
            Item {
                width: parent.width
                height: 20
                Text {
                    text: modelData.title
                    color: C.ink
                    font { family: win.serif; pixelSize: 15 }
                }
                Text {
                    anchors.right: parent.right
                    text: Math.round(modelData.percent) + "%"
                    color: modelData.percent < 50 ? C.jade : modelData.percent < 80 ? C.ink : C.accent
                    font { family: win.serif; pixelSize: 15 }
                }
            }
            Rectangle {
                width: parent.width
                height: 8
                radius: 4
                color: C.rule
                clip: true
                Rectangle {
                    id: fill
                    height: parent.height
                    radius: 4
                    width: Math.max(4, bars.width * modelData.percent / 100)
                    Behavior on width { NumberAnimation { duration: 1100; easing.type: Easing.OutCubic } }
                    color: modelData.percent < 50 ? C.jade : modelData.percent < 80 ? C.faded : C.accent
                    // a slow shimmer running along the filled part
                    Rectangle {
                        width: 40
                        height: parent.height
                        opacity: 0.35
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: "transparent" }
                            GradientStop { position: 0.5; color: C.ink }
                            GradientStop { position: 1; color: "transparent" }
                        }
                        x: ((win.t * 40) % (fill.width + 160)) - 80
                    }
                }
            }
            Text {
                text: modelData.resets
                color: C.faded
                font { family: win.serif; pixelSize: 13 }
                bottomPadding: 4
            }
        }
    }
}
