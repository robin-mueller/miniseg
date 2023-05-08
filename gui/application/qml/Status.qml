import QtQuick 2.5
import QtQuick.Controls
import QtQuick.Layouts 1.1
import Configuration
//import "./dummy"

GridLayout {
    id: root

    columns: 2
    columnSpacing: 15
    anchors.fill: parent

    readonly property int leftWidth: 150
    readonly property int titleSize: 14
    readonly property int textSize: 12

    property alias control_state: controller_switch.checked

    Item {
        Layout.preferredWidth: root.leftWidth
        Layout.fillHeight: true

        Text {
            text: "Bluetooth"
            font.pixelSize: root.titleSize
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        readonly property var messages: {
            "0": "Not Connected",
            "1": "Connecting ...",
            "2": "Connected"
        }

        Text {
            text: parent.messages[Number(backend.connection_state).toLocaleString()]
            font.pixelSize: root.textSize
            color: backend.connection_state === 2 ? Theme.primary : Theme.foreground
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: root.leftWidth
        Layout.fillHeight: true

        Text {
            text: "IMU Calibration"
            font.pixelSize: root.titleSize
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        readonly property var messages: {
            "0": "Not Calibrated",
            "1": "Calibrating ...",
            "2": "Calibrated"
        }

        Text {
            text: parent.messages[Number(backend.calibration_state).toLocaleString()]
            font.pixelSize: root.textSize
            color: backend.calibration_state === 2 ? Theme.primary : Theme.foreground
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: root.leftWidth
        Layout.fillHeight: true

        Text {
            text: "Controller"
            font.pixelSize: root.titleSize
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
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
            font.pixelSize: root.textSize
            horizontalAlignment: Text.AlignHCenter
            color: controller_switch.checked ? Theme.primary : Theme.foreground
            anchors {
                left: controller_switch.right
                leftMargin: root.columnSpacing
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.preferredWidth: root.leftWidth
        Layout.fillHeight: true

        Text {
            text: "Parameters"
            font.pixelSize: root.titleSize
            font.bold: true
            color: Theme.foreground
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        readonly property var messages: {
            "0": " | Not sent yet",
            "1": " | Sent"
        }

        Text {
            text: backend.param_file_name + parent.messages[Number(backend.loaded_param_state).toLocaleString()]
            font.pixelSize: root.textSize
            color: backend.loaded_param_state === 1 ? Theme.primary : Theme.foreground
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }
    }

}
