import QtQuick
import QtQuick.Controls 6.2

import Configuration

//import "./dummy"
Item {
    Switch {
        id: controller_switch

        checked: backend.controller_switch_state
        onToggled: backend.controller_switch_state = checked

        width: 120
        anchors {
            left: parent.left
            verticalCenter: parent.verticalCenter
            leftMargin: 15
        }

        indicator: Rectangle {
            implicitWidth: 60
            implicitHeight: 25
            radius: implicitHeight / 2
            color: controller_switch.checked ? Theme.primary : Theme.foreground
            border.color: Theme.border
            anchors.centerIn: parent

            Rectangle {
                x: controller_switch.checked ? parent.width - width : 0
                width: parent.implicitHeight
                height: parent.implicitHeight
                radius: parent.radius
                color: controller_switch.down ? Theme.dark_foreground : Theme.foreground
                border.color: Theme.border
            }
        }

        contentItem: Text {
            text: controller_switch.checked ? "Controller ON" : "Controller OFF"
            font.pixelSize: 14
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            color: controller_switch.checked ? Theme.primary : Theme.foreground
            anchors {
                bottom: controller_switch.top
                horizontalCenter: controller_switch.horizontalCenter
            }
        }
    }
}
