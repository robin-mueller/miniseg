import QtQuick
import QtQuick.Controls
import Configuration

//import "./dummy"
Rectangle {

    border.color: Theme.border
    radius: 10
    color: "transparent"

    Label {
        text: "Position [cm]"
        color: Theme.foreground
        font {
            pixelSize: 16
            bold: true
        }
        anchors {
            centerIn: parent
            verticalCenterOffset: -(handle.height / 2 + (parent.height / 2 - handle.height / 2) / 2)
        }
    }

    Item {
        id: tickScale

        property int rangeCentiMeter: 60
        property int minorInterval: 5
        property int majorInterval: 3
        property int majorTickWidth: 4
        property int minorTickWidth: majorTickWidth - 2
        property int majorTickHeight: 16
        property int minorTickHeight: majorTickHeight - 5
        property int majorLabelFontSize: 16
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
                color: Theme.foreground
                transform: Translate {
                    x: index * tickScale.pixPerTick
                }

                Label {
                    text: (index - (tickScale.totalTicks - 1) / 2) * tickScale.minorInterval
                    font.pixelSize: tick.major ? 14 : 12
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

        readonly property int sideMargin: 20

        value: backend.initial_value
        anchors.fill: parent
        stepSize: 1
        from: -tickScale.rangeCentiMeter / 2
        to: tickScale.rangeCentiMeter / 2
        anchors.leftMargin: sideMargin
        anchors.rightMargin: sideMargin

        onValueChanged: backend.value = value

        background: Rectangle {
            x: control.leftPadding
            y: control.topPadding + control.availableHeight / 2 - height / 2
            anchors.centerIn: parent
            width: control.availableWidth - handle.width
            height: 4
            color: Theme.foreground
            border.color: Theme.foreground
        }

        handle: Rectangle {
            id: handle
            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            implicitWidth: 12
            implicitHeight: 60
            radius: 5
            color: control.pressed ? Theme.primary : Theme.foreground
        }
    }
}
