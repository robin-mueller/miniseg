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
        
        
class HeaderSection(QMLWidget):
    SOURCE = "qrc:/include/qml/Header.qml"
    controller_switch_state_changed = Signal(bool)
    
    def __init__(self, widget_frame: QFrame):
        self._controller_switch_state = False
        super().__init__(widget_frame)
    
    @Property(bool, notify=controller_switch_state_changed)
    def controller_switch_state(self):
        return self._controller_switch_state
    
    @controller_switch_state.setter
    def controller_switch_state(self, val: bool):
        self._controller_switch_state = val
        self.controller_switch_state_changed.emit(val)
    

class ParameterSection(QMLWidget):
    SOURCE = "qrc:/include/qml/Parameters.qml"


class SetpointSlider(QMLWidget):
    SOURCE = "qrc:/include/qml/SetpointSlider.qml"
    value_changed = Signal(int)

    def __init__(self, widget_frame: QFrame):
        self._value = 10
        super().__init__(widget_frame)

    @Property(int, notify=value_changed)
    def value(self):
        return self._value

    @value.setter
    def value(self, val: int):
        self._value = val
        self.value_changed.emit(val)
        
