import QtQuick

// Claude usage (with its tips), Find and Summary: lines of text drawn from bridge.info.
// A Find result opens its project; "Change" on a refresh line lets him type a new time.
ListView {
    id: info
    clip: true
    spacing: 4
    boundsBehavior: Flickable.DragAndOvershootBounds
    model: bridge.info.lines || []
    property bool toTips: false
    property string editing: ""   // the account whose refresh time is being typed
    onCountChanged: if (toTips) Qt.callLater(goTips)
    function goTips() {
        toTips = false
        for (var i = 0; i < model.length; i++)
            if (model[i].tips) { positionViewAtIndex(i, ListView.Beginning); return }
    }
    delegate: Item {
        id: line
        required property var modelData
        required property int index
        readonly property string st: modelData.style
        width: ListView.view.width
        height: st === "copy" ? 58 : body.height + (st === "head" ? 34 : st === "group" ? 18 : st === "where" ? 12 : 4)
                + (editBox.visible ? editBox.height + 8 : 0)
        Text {
            id: body
            visible: line.st !== "copy"
            anchors.bottom: line.st === "head" || line.st === "group" || line.st === "where" ? parent.bottom : undefined
            anchors.bottomMargin: editBox.visible ? editBox.height + 10 : 2
            x: line.st === "hit" || line.st === "small" && line.modelData.note ? 18 : 6
            width: parent.width - x - 12
            wrapMode: Text.Wrap
            textFormat: line.modelData.rich ? Text.RichText : Text.PlainText
            text: line.modelData.text
            color: ({ faded: C.faded, small: C.faded, good: C.jade, warn: C.accent, head: C.accent,
                      group: C.peach, where: C.accent, link: C.faded })[line.st] || C.ink
            opacity: line.st === "group" ? 0.85 : 1
            font {
                family: win.serif
                pixelSize: ({ head: 16, small: 14, where: 14, group: 14, good: 18 })[line.st] || 16
                italic: line.st === "group"
                letterSpacing: line.st === "head" ? 0.4 : 0
            }
            lineHeight: 1.1
        }
        SilkButton {
            visible: line.st === "copy"
            y: 4
            text: line.modelData.text
            onClicked: bridge.copySummary()
        }
        Rectangle {  // typing a new refresh time
            id: editBox
            visible: info.editing !== "" && info.editing === line.modelData.email
            anchors { left: parent.left; bottom: parent.bottom; leftMargin: 6 }
            width: 260
            height: 36
            radius: 8
            color: C.field
            border.color: C.accent
            TextInput {
                id: refreshIn
                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                verticalAlignment: TextInput.AlignVCenter
                color: C.ink
                font { family: win.serif; pixelSize: 16 }
                onAccepted: { win.say(bridge.setRefresh(line.modelData.email, text)); info.editing = "" }
                Keys.onEscapePressed: info.editing = ""
            }
            onVisibleChanged: if (visible) {
                refreshIn.text = ""
                refreshIn.forceActiveFocus()
                win.say("Type the day and time, like “Thu 11pm”, and press Enter.")
            }
        }
        MouseArea {
            anchors.fill: body
            enabled: line.modelData.slug !== undefined || line.st === "link"
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: body.opacity = 0.75
            onExited: body.opacity = 1
            onClicked: {
                if (line.st === "link") info.editing = line.modelData.email
                else { bridge.pick(line.modelData.slug); win.gotoNote(line.modelData.note) }
            }
        }
    }
}
