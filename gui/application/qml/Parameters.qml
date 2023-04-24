import QtQuick
import QtQuick.Layouts 6.3

Item {
    id: root

    property var names: ["k1", "k2", "k3", "k4"]

    ColumnLayout {
        anchors.fill: root

        Repeater {
            model: root.names.length

            ParameterField {
                Layout.alignment: Qt.AlignCenter
                name: root.names[index]
            }
        }
    }
}
