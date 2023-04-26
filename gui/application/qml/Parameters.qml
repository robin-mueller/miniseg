import QtQuick
import QtQuick.Layouts 6.3
import Configuration
//import "./dummy"

Item {
    id: root

    property string title
    property var names

    Text {
        id: header

        text: root.title
        font.pixelSize: 14
        font.bold: true
        font.italic: true
        color: Theme.foreground
        anchors.left: fields.left
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
            left: fields.left
            leftMargin: -2
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

        anchors {
            top: header.bottom
            topMargin: 5
            bottom: root.bottom
            horizontalCenter: root.horizontalCenter
        }

        Repeater {
            id: repeater

            model: root.names

            ParameterField {
                Layout.alignment: Qt.AlignCenter
                name: modelData
                value: backend.value[modelData]
                onValueChanged: () => {var d = {}; d[name] = value; backend.value = d}
            }
        }
    }
}
