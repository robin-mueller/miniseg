import QtQuick
import QtQuick.Controls.Fusion
import Configuration
//import "./dummy"

Item {
    Label {
        text: "Position Setpoint [cm]"
        color: Theme.foreground
        font.pixelSize: 14
        anchors {
            centerIn: parent
            verticalCenterOffset: -(handle.height / 2 + (parent.height / 2 - handle.height / 2) / 2)
        }
    }

    Item {
        id: tickScale

        property int rangeCentiMeter: 90
        property int minorInterval: 5
        property int majorInterval: 3
        property int majorTickWidth: 4
        property int minorTickWidth: majorTickWidth - 2
        property int majorTickHeight: 16
        property int minorTickHeight: majorTickHeight - 6
        property int majorLabelFontSize: 17
        property int minorLabelFontSize: majorLabelFontSize - 5
        property int labelMargin: handle.height / 2 + (parent.height / 2 - handle.height / 2) / 2

        readonly property int totalTicks: rangeCentiMeter / minorInterval + 1
        readonly property double pixPerTick: width / (totalTicks - 1)

        width: control.width - handle.width
        height: parent.height
        anchors.centerIn: parent

        Repeater {
            model: tickScale.totalTicks

            Rectangle {
                id: tick

                readonly property bool major: index % tickScale.majorInterval == 0

                anchors.verticalCenter: tickScale.verticalCenter
                anchors.horizontalCenter: tickScale.left
                implicitWidth: major ? tickScale.majorTickWidth : tickScale.minorTickWidth
                implicitHeight: major ? tickScale.majorTickHeight : tickScale.minorTickHeight
                radius: 2
                color: Theme.dark_foreground
                transform: Translate {
                    x: index * tickScale.pixPerTick
                }

                Label {
                    text: (index - (tickScale.totalTicks - 1) / 2) * tickScale.minorInterval
                    font {
                        pixelSize: tick.major ? 14 : 11
                        family: Theme.number_font_family
                    }
                    color: tick.major ? Theme.primary : Theme.foreground
                    anchors {
                        centerIn: tick
                        verticalCenterOffset: tickScale.labelMargin
                    }
                }
            }
        }
    }

    Slider {
        id: control

        readonly property int sideMargin: 35

        value: backend.value
        onValueChanged: backend.value = value

        live: false
        anchors.fill: parent
        stepSize: 1
        from: -tickScale.rangeCentiMeter / 2
        to: tickScale.rangeCentiMeter / 2
        anchors.leftMargin: sideMargin
        anchors.rightMargin: sideMargin

        background: Rectangle {
            x: control.leftPadding
            y: control.topPadding + control.availableHeight / 2 - height / 2
            anchors.centerIn: parent
            width: control.availableWidth - handle.width
            height: 4
            color: Theme.dark_foreground
        }

        handle: Rectangle {
            id: handle

            implicitWidth: 12
            implicitHeight: 42
            radius: 4
            border.color: Theme.border

            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            color: control.pressed ? Theme.dark_foreground : Theme.foreground
        }
    }
}
