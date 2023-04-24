import QtQuick 2.5
import QtQuick.Controls
import QtQuick.Layouts 1.1
import Configuration
//import "./dummy"

GridLayout {
    id: grid

    rows: 3
    columns: 2
    anchors.fill: parent

    readonly property int leftStretch: 1
    readonly property int rightStretch: 1

    Item {
        Layout.preferredWidth: grid.leftStretch
        Layout.fillWidth: true
        Layout.fillHeight: true

        Text {
            text: "Bluetooth"
            font.pixelSize: 14
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: grid.rightStretch
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    Item {
        Layout.preferredWidth: grid.leftStretch
        Layout.fillWidth: true
        Layout.fillHeight: true

        Text {
            text: "IMU Calibration"
            font.pixelSize: 14
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: grid.rightStretch
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    Item {
        Layout.preferredWidth: grid.leftStretch
        Layout.fillWidth: true
        Layout.fillHeight: true

        Text {
            text: "Controller"
            font.pixelSize: 14
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: grid.rightStretch
        Layout.fillWidth: true
        Layout.fillHeight: true

        Switch {
            id: controller_switch

            checked: backend.controller_switch_state
            onToggled: backend.controller_switch_state = checked

            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
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
        }

        Text {
            text: controller_switch.checked ? "Active" : "Idle"
            font.pixelSize: 12
            horizontalAlignment: Text.AlignHCenter
            color: controller_switch.checked ? Theme.primary : Theme.foreground
            anchors {
                left: controller_switch.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

}
