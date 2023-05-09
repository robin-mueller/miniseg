import QtQuick
import QtQuick.Controls.Fusion  // Use linux style
import Qt5Compat.GraphicalEffects
import Configuration
//import "./dummy"

Item {
    id: root

    property string name: "Name"
    property real from: -999
    property real to: 999
    property int decimals: 2
    property real stepsize: 1.0
    property alias value: control.value  // Very important to use alias here since introducing another property will lead to binding conflicts

    width: nameText.width + control.anchors.leftMargin + control.width
    height: control.height

    readonly property var locale: Qt.locale("en_US")

    Text {
        id: nameText

        text: root.name
        font.pixelSize: 12
        color: Theme.foreground
        anchors {
            verticalCenter: root.verticalCenter
            left: root.left
        }
    }

    SpinBox {
        id: control

        readonly property int buttonWidth: 20
        readonly property int buttonRadius: 8
        readonly property string buttonColor: Theme.background
        readonly property string buttonPressedColor: Theme.dark_foreground

        width: 110
        height: 24
        font {
            pixelSize: 14
            family: Theme.number_font_family
        }
        from: root.from * Math.pow(10, root.decimals)
        to: root.to * Math.pow(10, root.decimals)
        stepSize: root.stepsize * Math.pow(10, root.decimals)
        editable: true

        anchors {
            left: nameText.right
            leftMargin: 8
            verticalCenter: root.verticalCenter
        }

        validator: DoubleValidator {
            bottom: Math.min(control.from, control.to)
            top: Math.max(control.from, control.to)
            locale: root.locale.name
        }

        textFromValue: function (value) {
            return Number(value / Math.pow(10, root.decimals)).toLocaleString(root.locale, 'f', root.decimals)
        }

        valueFromText: function (text) {
            return Number.fromLocaleString(root.locale, text) * Math.pow(10, root.decimals)
        }

        contentItem: TextInput {
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
                height: 8
                width: 7
            }

            ColorOverlay {
                anchors.fill: downIcon
                source: downIcon
                color: Theme.foreground
            }
        }

        up.indicator: Rectangle {
            x: control.width - width
            height: control.height
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
                height: 8
                width: 8
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
            anchors.fill: control.contentItem
        }
    }
}
