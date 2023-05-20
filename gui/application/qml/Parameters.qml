import QtQuick
import QtQuick.Layouts 6.3
import QtQuick.Shapes 1.5
import Configuration
//import "./dummy"

// There will be context properties set from the backend: param_names, title

Item {
    id: root

    height: childrenRect.height
    width: childrenRect.width

    Text {
        id: header

        text: title
        font.pixelSize: 14
        font.bold: true
        color: Theme.foreground
        anchors {
            top: root.top
            left: fields.left
        }
    }

    Shape {
        id: bracket

        layer.enabled: true
        layer.samples: 4

        readonly property int radius: 18
        readonly property int borderWidth: 3

        anchors {
            top: header.bottom
            bottom: fields.bottom
            left: root.left
            right: fields.right
            rightMargin: -fields.spacing
        }

        ShapePath {
            strokeColor: Theme.border
            strokeWidth: bracket.borderWidth
            joinStyle: ShapePath.RoundJoin
            fillColor: Theme.background

            startX: 0; startY: bracket.borderWidth / 2
            PathLine { relativeX: bracket.width - bracket.radius - bracket.borderWidth / 2; relativeY: 0 }
            PathArc { relativeX: bracket.radius; relativeY: bracket.radius; radiusX: bracket.radius; radiusY: bracket.radius}
            PathLine { relativeX: 0; y: bracket.height }
        }
    }

    ColumnLayout {
        id: fields
        spacing: 12

        anchors {
            top: header.bottom
            topMargin: spacing
            left: root.left
            leftMargin: 4
        }

        Repeater {
            id: repeater

            model: param_names

            ParameterField {
                Layout.alignment: Qt.AlignRight
                name: modelData
                decimals: 3

                value: backend.loaded[title][name] * Math.pow(10, decimals)
                onValueChanged: () => {var d = {}; d[title] = {}; d[title][name] = value / Math.pow(10, decimals); backend.last_change = d}
            }
        }
    }
}
