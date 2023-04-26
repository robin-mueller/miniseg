import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import Configuration
//import "./dummy"

Item {
    id: root

    property string name: "Name"
    property int decimals: 2
    property real realValue: control.value / Math.pow(10, decimals)
    property alias value: control.value

    implicitWidth: childrenRect.width
    implicitHeight: childrenRect.height

    Text {
        id: nameText

        text: root.name
        color: Theme.foreground
        anchors {
            verticalCenter: root.verticalCenter
            left: root.left
        }
    }

    SpinBox {
        id: control

        readonly property int buttonWidth: 22
        readonly property int buttonRadius: 8
        readonly property string buttonColor: Theme.background
        readonly property string buttonPressedColor: Theme.dark_foreground

        width: 100
        height: 25
        font.pixelSize: 14

        from: -10 * Math.pow(10, root.decimals)
        to: 10 * Math.pow(10, root.decimals)
        stepSize: 1
        editable: true

        anchors {
            left: nameText.right
            leftMargin: 8
            verticalCenter: root.verticalCenter
        }

        validator: DoubleValidator {
            bottom: Math.min(control.from, control.to)
            top: Math.max(control.from, control.to)
        }

        textFromValue: function (value) {
            return Number(value / Math.pow(10, root.decimals)).toLocaleString(control.locale, 'f', root.decimals)
        }

        valueFromText: function (text) {
            return Number.fromLocaleString(control.locale, text) * Math.pow(10, root.decimals)
        }

        contentItem: TextInput {
            id: input

            z: 2
            text: control.textFromValue(control.value)
            font: control.font
            color: Theme.background
            selectionColor: Theme.dark_foreground
            selectedTextColor: Theme.foreground
            horizontalAlignment: Qt.AlignHCenter
            verticalAlignment: Qt.AlignVCenter
            anchors {
                fill: control
                leftMargin: control.down.indicator.implicitWidth
                rightMargin: control.up.indicator.implicitWidth
            }

            readOnly: !control.editable
            validator: control.validator
            inputMethodHints: Qt.ImhFormattedNumbersOnly
        }

        down.indicator: Rectangle {
            x: 0
            height: control.height
            implicitWidth: control.buttonWidth
            color: control.down.pressed ? control.buttonPressedColor : control.buttonColor
            border.color: Theme.dark_foreground
            radius: control.buttonRadius

            Rectangle {
                height: parent.height
                color: parent.color
                anchors {
                    left: parent.right
                    leftMargin: -control.buttonRadius
                    right: parent.right
                    rightMargin: -control.background.radius
                }
            }

            Image {
                id: downIcon
                source: "qrc:/image/application/assets/minus.png"
                visible: false
                anchors.centerIn: parent
                height: 10
                width: 9
            }

            ColorOverlay {
                anchors.fill: downIcon
                source: downIcon
                color: Theme.foreground
            }
        }

        up.indicator: Rectangle {
            x: parent.width - width
            height: parent.height
            implicitWidth: control.buttonWidth
            implicitHeight: control.height
            color: control.up.pressed ? control.buttonPressedColor : control.buttonColor
            border.color: Theme.dark_foreground
            radius: control.buttonRadius

            Rectangle {
                height: parent.height
                color: parent.color
                anchors {
                    left: parent.left
                    leftMargin: -control.background.radius
                    right: parent.left
                    rightMargin: -control.buttonRadius
                }
            }

            Image {
                id: upIcon
                source: "qrc:/image/application/assets/plus.png"
                visible: false
                anchors.centerIn: parent
                height: 10
                width: 10
            }

            ColorOverlay {
                anchors.fill: upIcon
                source: upIcon
                color: Theme.foreground
            }
        }

        background: Rectangle {
            z: 1
            color: Theme.foreground
            radius: 4
            anchors.fill: input
        }
    }
}
