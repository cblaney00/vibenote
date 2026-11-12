import QtQuick
import QtQuick.Effects

// A button of copper-edged silk that presses in on a spring.
Item {
    id: btn
    property string text
    property bool main: false
    property bool work: false  // the green Work button
    signal clicked()
    width: label.implicitWidth + 44
    height: 44
    property real hot: (area.containsMouse && enabled) ? 1 : 0
    Behavior on hot { NumberAnimation { duration: 180 } }
    scale: area.pressed ? 0.94 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.3 } }
    opacity: enabled ? 1 : 0.45
    RectangularShadow {
        anchors.fill: face
        offset.y: 3 + btn.hot * 3
        blur: 12 + btn.hot * 10
        radius: 10
        color: Qt.rgba(0, 0, 0, 0.5)
    }
    Rectangle {
        id: face
        anchors.fill: parent
        radius: 10
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.tint("#173a2d", Qt.rgba(0.75, 0.52, 0.34, btn.hot * 0.12)) }
            GradientStop { position: 1; color: "#0f251c" }
        }
        border.width: 1.5
        border.color: btn.main ? Qt.tint(C.accent, Qt.rgba(0.84, 0.6, 0.45, btn.hot * 0.6))
                      : btn.work ? C.jade : C.rule
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: btn.text
        color: btn.main ? Qt.tint(C.accent, Qt.rgba(0.84, 0.6, 0.45, btn.hot * 0.6))
               : btn.work ? C.jade : C.ink
        font { family: win.serif; pixelSize: 18; bold: true }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        enabled: btn.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            var at = btn.mapToItem(root, btn.width / 2, btn.height / 2)
            win.ripple(at.x, at.y, 0.8)
            btn.clicked()
        }
    }
}
