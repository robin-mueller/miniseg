import QtQuick
import QtQuick.Layouts 6.3
import Configuration
//import "./dummy"

// There will be context properties set from the backend: param_names, title

Item {
    id: root

    height: childrenRect.height
    width: childrenRect.width

    Text {
        id: header

        text: title
        font.pixelSize: 14
        font.bold: true
        font.italic: true
        color: Theme.foreground
        anchors {
            top: root.top
            left: fields.left
        }
    }

    Rectangle {
        id: bracket

        color: Theme.background
        border {
            color: Theme.foreground
            width: 2
        }

        radius: 18
        anchors {
            top: header.bottom
            bottom: fields.bottom
            bottomMargin: -fields.spacing
            left: root.left
            right: fields.right
            rightMargin: -12
        }

        Rectangle {
            color: Theme.background
            anchors {
                top: parent.bottom
                topMargin: -parent.radius
                left: parent.horizontalCenter
                right: parent.right
                bottom: parent.bottom
            }
        }

        Rectangle {
            color: Theme.foreground
            width: parent.border.width
            anchors {
                top: parent.bottom
                topMargin: -parent.radius
                bottom: parent.bottom
                right: parent.right
            }
        }

        Rectangle {
            color: Theme.background
            anchors {
                top: parent.top
                left: parent.left
                right: parent.horizontalCenter
                bottom: parent.bottom
            }
        }

        Rectangle {
            color: parent.border.color
            height: parent.border.width
            anchors {
                top: parent.top
                left: parent.left
                right: parent.horizontalCenter
            }
        }
    }

    ColumnLayout {
        id: fields
        spacing: 12

        anchors {
            top: header.bottom
            topMargin: spacing
            left: root.left
            leftMargin: 4
        }

        Repeater {
            id: repeater

            model: param_names

            ParameterField {
                Layout.alignment: Qt.AlignCenter
                name: modelData

                value: backend.loaded[title][name] * Math.pow(10, decimals)
                onValueChanged: () => {var d = {}; d[title] = {}; d[title][name] = value / Math.pow(10, decimals); backend.last_change = d}
            }
        }
    }
}
