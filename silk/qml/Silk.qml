import QtQuick

// The silk (silk.frag): woven, folding slowly, lit by a light that follows the mouse,
// rippling where he clicks.
ShaderEffect {
    property real level: 1.0
    property real time: win.t
    property size size: Qt.size(width, height)
    property point mouse: Qt.point(win.smx - offset.x, win.smy - offset.y)
    property point offset: Qt.point(0, 0)
    property vector4d r0: win.ripples[0]
    property vector4d r1: win.ripples[1]
    property vector4d r2: win.ripples[2]
    property vector4d r3: win.ripples[3]
    fragmentShader: shaders + "/silk.frag.qsb"
}
