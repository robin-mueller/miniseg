from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtCore import Qt, Signal, QObject, Property, QUrl
from PySide6.QtWidgets import QFrame, QVBoxLayout


class QMLWidget(QObject):
    SOURCE: str

    def __init__(self, widget_frame: QFrame):
        """
        Helper class to initialize quick widget objects from QML file.

        :param widget_frame: The frame that the referred quick widget centers in.
        """
        super().__init__()
        self.widget = QQuickWidget(widget_frame)
        self.widget.rootContext().setContextProperty("backend", self)
        self.widget.setSource(self.SOURCE)
        # noinspection PyUnresolvedReferences
        self.widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.widget.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.widget.setAttribute(Qt.WA_TranslucentBackground)
        self.widget.setClearColor(Qt.transparent)
        layout = QVBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)


class SetpointSlider(QMLWidget):
    SOURCE = "qrc:/include/qml/SetpointSlider.qml"
    value_changed = Signal(int)

    def __init__(self, widget_frame: QFrame):
        super().__init__(widget_frame)
        self._value = self.initial_value

    @Property(int, constant=True)
    def initial_value(self):
        return 0

    @Property(int, notify=value_changed)
    def value(self):
        return self._value

    @value.setter
    def value(self, val: int):
        self._value = val
        self.value_changed.emit(val)
      
        
class ParameterSection(QMLWidget):
    SOURCE = "qrc:/include/qml/Parameters.qml"
        
