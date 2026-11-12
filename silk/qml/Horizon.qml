import QtQuick

// The living night city (city.frag). The layers slide with the mouse, and a little as the
// notes scroll, for depth.
ShaderEffect {
    property real scroll: 0
    property real time: win.t
    property real par: (win.smx / Math.max(win.width, 1) - 0.5) * 2 + scroll * 0.004
    property size size: Qt.size(width, height)
    property color paper: C.paper
    fragmentShader: shaders + "/city.frag.qsb"
}
