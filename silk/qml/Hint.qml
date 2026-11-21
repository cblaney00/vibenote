import QtQuick

// Says what a control that is only a symbol does, after a moment of hovering over it. Put it
// inside the control and bind `hovered`; the words show in the window's one hint box.
Item {
    id: h
    property string text
    property bool hovered: false
    anchors.fill: parent
    Timer { id: wait; interval: 550; onTriggered: if (h.text) win.showHint(h.text, h.parent) }
    onHoveredChanged: {
        if (hovered) wait.restart()
        else { wait.stop(); win.hideHint(h.parent) }
    }
    onTextChanged: if (hovered && wait.running === false) win.showHint(h.text, h.parent)
    Component.onDestruction: win.hideHint(h.parent)
}
