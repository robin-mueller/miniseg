import QtQuick
import QtQuick.Controls 6.2
import Configuration

//import "./dummy"
Item {
    SpinBox {
        id: control

        property int decimals: 2
        property real realValue: value / 100

        from: -10 * Math.pow(10, decimals)
        to: 10 * Math.pow(10, decimals)
        stepSize: 1 * Math.pow(10, decimals)
        editable: true

        anchors.centerIn: parent
        width: 208
        height: 66

        validator: DoubleValidator {
            bottom: Math.min(control.from, control.to)
            top: Math.max(control.from, control.to)
        }

        textFromValue: function (value, locale) {
            return Number(value / Math.pow(10,
                                           control.decimals)).toLocaleString(
                        locale, 'f', control.decimals)
        }

        valueFromText: function (text, locale) {
            return Number.fromLocaleString(locale,
                                           text) * Math.pow(10,
                                                            control.decimals)
        }

        contentItem: TextInput {
            z: 2
            text: control.textFromValue(control.value, control.locale)

            font: control.font
            color: "#21be2b"
            selectionColor: "#21be2b"
            selectedTextColor: "#ffffff"
            horizontalAlignment: Qt.AlignHCenter
            verticalAlignment: Qt.AlignVCenter

            readOnly: !control.editable
            validator: control.validator
            inputMethodHints: Qt.ImhFormattedNumbersOnly
        }

        up.indicator: Rectangle {
            x: control.mirrored ? 0 : parent.width - width
            height: parent.height
            implicitWidth: 40
            implicitHeight: 40
            color: control.up.pressed ? "#e4e4e4" : "#f6f6f6"
            border.color: enabled ? "#21be2b" : "#bdbebf"

            Text {
                text: "+"
                font.pixelSize: control.font.pixelSize * 2
                color: "#21be2b"
                anchors.fill: parent
                fontSizeMode: Text.Fit
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        down.indicator: Rectangle {
            x: control.mirrored ? parent.width - width : 0
            height: parent.height
            implicitWidth: 40
            implicitHeight: 40
            color: control.down.pressed ? "#e4e4e4" : "#f6f6f6"
            border.color: enabled ? "#21be2b" : "#bdbebf"

            Text {
                text: "-"
                font.pixelSize: control.font.pixelSize * 2
                color: "#21be2b"
                anchors.fill: parent
                fontSizeMode: Text.Fit
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        background: Rectangle {
            implicitWidth: 140
            border.color: "#bdbebf"
        }
    }
}
