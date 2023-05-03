import QtQuick 2.5
import QtQuick.Controls
import QtQuick.Layouts 1.1
import Configuration
//import "./dummy"

GridLayout {
    id: grid

    rows: 3
    columns: 2
    columnSpacing: 15
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

        readonly property var messages: {
            "0": "Not Connected",
            "1": "Connecting ...",
            "2": "Connected"
        }

        Text {
            text: parent.messages[Number(backend.connection_state).toLocaleString()]
            font.pixelSize: 12
            color: backend.connection_state === 2 ? Theme.primary : Theme.foreground
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }
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

        readonly property var messages: {
            "0": "Not Calibrated",
            "1": "Calibrating ...",
            "2": "Calibrated"
        }

        Text {
            text: parent.messages[Number(backend.calibration_state).toLocaleString()]
            font.pixelSize: 12
            color: backend.calibration_state === 2 ? Theme.primary : Theme.foreground
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }
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

            checked: backend.control_switch_state
            onToggled: backend.control_switch_state = checked

            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
            height: indicator.height
            width: indicator.width

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
                leftMargin: grid.columnSpacing
                verticalCenter: parent.verticalCenter
            }
        }
    }

}
